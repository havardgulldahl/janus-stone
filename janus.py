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

import console

from januslib import JanusFileSink
from januslib.fb import JanusFB
from januslib.fusiontables import JanusFusiontablesSink

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

def lvl(string):
    try:
        return getattr(logging, string.upper())
    except ValueError:
        raise argparse.ArgumentTypeError('%r is not a loglevel')

argp = argparse.ArgumentParser()
argp.add_argument('--loglevel', type=lvl, default=logging.INFO, help='Set log level')
argp.add_argument('--fbpage', help='Set Facebook page name')
argp.add_argument('--add_sink', action='append', nargs='*', help='Add output sink to chain')

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
        if args.fbpage is not None:
            self.command_set_page(args.fbpage)
        logging.debug('sinks: %r', args.add_sink)
        if args.add_sink is not None:
            for s in args.add_sink:
                logging.debug('adding sink: %r, args: %r', s[0], *s[1:])
                self.command_add_outsink(s[0], *s[1:])
        self.format_prompt()

    def format_prompt(self):
        ps1 = colored.magenta('@'+self.fbpage) if self.fbpage else colored.red('FB Page unset')
        ps1 += ' -> ['
        _sinks = ['sink:{}'.format(c) for c in self.enabledsinks]
        ps1 += colored.green(', '.join(_sinks)) if _sinks else colored.red('No sinks set')
        ps1 += '] '
        ps1 += colored.yellow('({} posts in cache)'.format(self.count_cached_files()))
        ps1 += ' > '
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
        'Set the Facebook Page that we are pulling data from. Mandatory'
        self.fbpage = pagename
        self.fb = JanusFB(pagename, self.output)
        if self.since is not None:
            self.fb.set_since(self.since)
        if self.until is not None:
            self.fb.set_until(self.until)
        self.format_prompt()

    def command_add_outsink(self, sinkname, *args):
        'Add a sink to send each post to. You may add several sinks'
        logging.debug('command_add_outsink: sinkname=%r, *args=%r', sinkname, args)
        _sink = '_outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.append(getattr(self, _sink)(self, *args))
            self.format_prompt()

    def command_list_outsinks(self):
        'List all possible outsinks'
        logging.debug('self.outsinks: %r', self.outsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, getattr(self, '_outsink__'+nm).__doc__) for nm in self.outsinks ] )

    def command_list_enabled_outsinks(self):
        'List all enabled outsinks'
        logging.debug('enabledsinks: %r', self.enabledsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(sink, sink.__doc__) for sink in self.enabledsinks ] )

    def command_pull_posts(self):
        'Pull posts from current FB Page, respecting Until and Since if they are set'
        # cache receivers
        for post in self.fb: # iterate through feed
            for sink in self.enabledsinks:
                sink.push(post)

    def command_update_fusiontable(self):
        'Run through all posts in current page disk cache, and update fusiontable with any posts that are missing'

    def _outsink__file(self, path='./data'):
        'Store post JSON to a file on disk. Args: path (optional)'
        self.cachepath = '{}/{}'.format(path, self.fbpage)
        return JanusFileSink(self.cachepath, self.output)

    def count_cached_files(self):
        logging.debug('count cache: %r', self.cachepath)
        if self.cachepath is None:
            return -1
        try:
            return len(fnmatch.filter(os.listdir(self.cachepath), '*.json'))
        except FileNotFoundError:
            return -1

    def _outsink__fusiontables(self, post, tableid):
        'Push Post data to Google Fusion Tables. Args:  tableid'
        return JanusFusiontablesSink(tableid, self.output)
        
def main(fd=None):
    j = Janus()
    runner = console.CommandRunner()
    runner.command('set_page', j.command_set_page)
    runner.command('set_since', j.command_set_since)
    runner.command('set_until', j.command_set_until)
    runner.command('add_sink', j.command_add_outsink)
    runner.command('all_sinks', j.command_list_outsinks)
    runner.command('enabled_sinks', j.command_list_enabled_outsinks)
    runner.command('pull', j.command_pull_posts)
    return console.Console(runner).run_in_main(fd)

if __name__ == '__main__':
    import sys
    sys.exit(main())

