#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import sys
import io
import fnmatch
import collections
import os
import argparse
import code
import logging
from datetime import datetime
from clint.textui import colored, puts, indent
import html
import dateutil

import console

from januslib import JanusPost
from januslib.fb import JanusFB, JanusFBCached
from januslib.fusiontables import JanusFusiontablesSink
from januslib.filesinks import JanusFileSink, JanusCSVSink
from januslib.stats import JanusStatsSink

JANUS_CACHEDIR='./data'

def datestring(string):
    try:
        value = datetime.strptime(string, '%Y-%m-%d')
        return value.timestamp()
    except ValueError:
        try:
            value = datetime.strptime(string, '%Y-%m-%d %H:%M:%S')
            return value.timestamp()
        except ValueError:
            msg = "%r is not a YYYY-MM-DD [HH:MM:SS] timestamp" % string
            raise Exception(msg)

def unixtimetoiso8601(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def fusionify_timestamp(datestring):
    '''2016-12-31T21:56:10+0000' -> 2016-12-31 21:56:10'''
    yourdate = dateutil.parser.parse(datestring)
    return yourdate.strftime('%Y-%m-%d %H:%M:%S')


def lvl(string):
    try:
        return getattr(logging, string.upper())
    except ValueError:
        raise argparse.ArgumentTypeError('%r is not a loglevel')

argp = argparse.ArgumentParser()
argp.add_argument('--loglevel', type=lvl, default=logging.INFO, help='Set log level')
argp.add_argument('--fbpage', help='Set Facebook page name')
argp.add_argument('--cached', action='store_true', default=False, help='Use CACHED posts: Dont pull them from online, but from disk')
argp.add_argument('--add_sink', action='append', nargs='*', help='Add output sink to chain')
argp.add_argument('--since', help='Date in YYYY-MM-DD [HH:MM:SS] format')
argp.add_argument('--until', help='Date in YYYY-MM-DD [HH:MM:SS] format')

args = argp.parse_args()

logging.basicConfig(level=args.loglevel)

class Janus:
    output = sys.stdout

    def __init__(self):
        self.fbpage = None
        self.fb = None
        self.outsinks = [func[10:] for func in dir(self) if callable(getattr(self, func)) and func.startswith("_outsink__")]
        self.enabledsinks = [] # list of tuples (cmd, *args)
        self.since = None # unix timestamp
        self.until = None # unix timestamp
        self.cachepath = None # where to store cached posts

    def format_prompt(self):
        ps1 = colored.magenta(self.fb) if self.fb else colored.red('FB Page unset')
        ps1 += ' ▶ ['
        _sinks = ['sink:{}'.format(c) for c in self.enabledsinks]
        ps1 += colored.green(', '.join(_sinks)) if _sinks else colored.red('No sinks set')
        ps1 += '] '
        if self.since or self.until:
            ps1 += '|{}↦{}| '.format(unixtimetoiso8601(self.since) if self.since else '∞', unixtimetoiso8601(self.until) if self.until else '∞')
        ps1 += colored.yellow('({} cached)'.format(self.count_cached_files()))
        ps1 += '\n > '
        sys.ps1 = ps1

    def command_set_since(self, datetimestring):
        'The datetime to start the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.since = datestring(datetimestring)
        if self.fb is not None:
            self.fb.set_since(self.since)

    def command_set_until(self, datetimestring):
        'The datetime to end the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.until = datestring(datetimestring)
        if self.fb is not None:
            self.fb.set_until(self.until)

    def command_set_page(self, pagename):
        'Set the Facebook Page that we are pulling data from.'
        self.fbpage = pagename
        self.fb = JanusFB(pagename, self.output)
        if self.since is not None:
            self.fb.set_since(self.since)
        if self.until is not None:
            self.fb.set_until(self.until)
        self.format_prompt()

    def command_set_page_cached(self, pagename, cachedir=None):
        'Set the Facebook Page name that we will be pulling CACHED posts from.'
        self.fbpage = pagename
        if cachedir is None:
            cachedir = JANUS_CACHEDIR
        self.fb = JanusFBCached(pagename, cachedir, self.output)
        self.format_prompt()

    def command_add_outsink(self, sinkname, *args):
        'Add a sink to send each post to. You may add several sinks'
        logging.debug('command_add_outsink: sinkname=%r, *args=%r', sinkname, args)
        _sink = '_outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.append(getattr(self, _sink)(*args))
            self.format_prompt()

    def command_disable_outsink(self, sinkid):
        'Disable a sink by its sink ID. See enabled sinks to get the id'
        if sinkid[0] == '#': sinkid = sinkid[1:]
        try:
            item = [ s for s in self.enabledsinks if s.id == sinkid][0]
            self.enabledsinks.remove(item)
            self.format_prompt()
        except IndexError: # no such sink id
            puts(colored.red('No such sink ID: {}'.format(sinkid)))
            return False

    def command_list_outsinks(self):
        'List all possible outsinks'
        logging.debug('self.outsinks: %r', self.outsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, getattr(self, '_outsink__'+nm).__doc__) for nm in self.outsinks ] )

    def command_list_enabled_outsinks(self):
        'List all enabled outsinks'
        logging.debug('enabledsinks: %r', self.enabledsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(sink, sink.__doc__) for sink in self.enabledsinks ] )

    def command_pull_posts(self):
        'Pull posts from current FB Page (cache or online), respecting Until and Since if they are set'
        # cache receivers
        i = 0
        if len(self.enabledsinks) == 0: # oh oh, no sinks set to receive
            puts(colored.red('No sinks enabled. Add one and try again.'))
            puts(colored.magenta(' ( use `all_sinks` to show all possible sinks ) '))
            return False
        for post in self.fb: # iterate through feed
            puts(colored.blue('Handling post # {} @ {}'.format(post.id, post.datetime_created.isoformat()), self.output))
            for sink in self.enabledsinks:
                sink.push(post)
            i = i+1
        for sink in self.enabledsinks:
            sink.finished() # let sinks clean up and empty their queues
        puts(colored.blue('Finished pulling {} posts from {}'.format(i, self.fb), self.output))

    def command_update_fusiontable(self):
        'Run through all posts in current page disk cache, and update fusiontable with any posts that are missing'

    def _outsink__file(self, path=None):
        'Store post JSON to a file on disk. Args: path (optional, defaults to JANUS_CACHEDIR)'
        if not path:
            path = JANUS_CACHEDIR
        self.cachepath = '{}/{}'.format(path, self.fbpage)
        return JanusFileSink(self.cachepath, self.output)

    def _outsink__date_count(self):
        'Create a table of posts created per date (looking at `created_date`)'
        return JanusStatsSink('date_count', self.output)

    def count_cached_files(self):
        logging.debug('count cache: %r', self.cachepath)
        if self.cachepath is None:
            return -1
        try:
            return len(fnmatch.filter(os.listdir(self.cachepath), '*.json'))
        except FileNotFoundError:
            return -1

    def _outsink__fusiontables(self, tableid):
        'Push Post data to Google Fusion Tables. Args:  tableid'
        return JanusFusiontablesSink(tableid, self.output)

    def _outsink__csv(self, filename, separator=None):
        'Push Post data to a CSV file. Args: filename, separator(optional, defaults to ,)'
        return JanusCSVSink(filename, separator, self.output)

    def command_set_runlog(self, logname):
        'Set up logging to file. Everything that goes to console also goes there'
        pass # TODO IMPLEMENT

    def command_fb_authenticate(self):
        'Start procedure to authenticate to facebook.'
        self.fb.authenticate() 


        
if __name__ == '__main__':
    import sys
    j = Janus()
    if args.fbpage is not None:
        if not args.cached:
            j.command_set_page(args.fbpage)
        else:
            j.command_set_page_cached(args.fbpage)
    logging.debug('sinks: %r', args.add_sink)
    if args.add_sink is not None:
        for s in args.add_sink:
            _args = s[1:] if len(s) > 1 else []
            logging.debug('adding sink: %r, args: %r', s[0], _args)
            j.command_add_outsink(s[0], *_args)
    if args.since is not None:
        j.command_set_since(args.since)
    if args.until is not None:
        j.command_set_until(args.until)

    runner = console.CommandRunner()
    runner.command('set_page', j.command_set_page)
    runner.command('set_cached_page', j.command_set_page_cached)
    runner.command('set_since', j.command_set_since)
    runner.command('set_until', j.command_set_until)
    runner.command('add_sink', j.command_add_outsink)
    runner.command('all_sinks', j.command_list_outsinks)
    runner.command('enabled_sinks', j.command_list_enabled_outsinks)
    runner.command('disable_sink', j.command_disable_outsink)
    runner.command('pull', j.command_pull_posts)
    runner.command('fb_auth', j.command_fb_authenticate)
    ex = console.Console(runner).run_in_main()
    j.format_prompt()
    sys.exit(ex)

