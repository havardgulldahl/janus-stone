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
import logging.handlers
import colorlog  # pip install colorlog
from datetime import datetime
from clint.textui import colored, puts as clintputs, indent # pip install clint
import html
import dateutil # pip install python-dateutil
from queue import Queue

from dotenv import load_dotenv, find_dotenv, set_key

import console # TODO: replace with python-prompt-toolkit

from januslib import JanusPost, JanusException
from januslib.fb import JanusFB, JanusFBCached, fb_authenticate, fb_run_oauth_endpoint
from januslib.fusiontables import *
from januslib.filesinks import JanusFileSink, JanusCSVSink
from januslib.stats import JanusStatsSink

JANUS_CACHEDIR='./data'

def datestring(string):
    'Take a isoformatted string, Y-m-d or Y-m-d H:M:S, and return datetime.datetime'
    try:
        value = datetime.strptime(string, '%Y-%m-%d')
        return value
    except ValueError:
        try:
            value = datetime.strptime(string, '%Y-%m-%d %H:%M:%S')
            return value
        except ValueError:
            msg = "%r is not a YYYY-MM-DD [HH:MM:SS] timestamp" % string
            raise JanusException(msg)

def unixtimetoiso8601(timestamp):
    'Take a unix timestamp and return Y-m-d H:M:S'
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def fusionify_timestamp(ts):
    '''2016-12-31T21:56:10+0000' -> 2016-12-31 21:56:10'''
    yourdate = dateutil.parser.parse(ts)
    return yourdate.strftime('%Y-%m-%d %H:%M:%S')

def puts(s):
    'Print with logging'
    logger.info(s)
    clintputs(s)

def lvl(string):
    try:
        return getattr(logging, string.upper())
    except ValueError:
        raise argparse.ArgumentTypeError('%r is not a loglevel')

argp = argparse.ArgumentParser()
argp.add_argument('--loglevel', type=lvl, default=logging.INFO, help='Set log level')
#argp.add_argument('--fbpage', help='Set Facebook page name')
argp.add_argument('--cached', action='store_true', default=False, help='Use CACHED posts: Dont pull them from online, but from disk')
argp.add_argument('--add_sink', action='append', nargs='*', help='Add output sink to chain')
argp.add_argument('--since', help='Date in YYYY-MM-DD [HH:MM:SS] format')
argp.add_argument('--until', help='Date in YYYY-MM-DD [HH:MM:SS] format')

args = argp.parse_args()

logging.basicConfig(level=args.loglevel)

logger = logging.getLogger('Janus')

colorout = colorlog.StreamHandler()
colorout.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s:%(name)s:%(message)s'))
colorout.setLevel(args.loglevel)
logger.addHandler(colorout)

fileout = logging.handlers.RotatingFileHandler('/tmp/janus.log', maxBytes=5*1024*1024, backupCount=5)
fileout.setLevel(logging.DEBUG)
fileout.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(fileout)

def ask_iterator(ques, it):
    l = list(it)
    for i in range(len(l)):
        try:
            name, desc = l[i] # try to unwrap tuple
            puts('[{}]:\t{} -- {}'.format(i, name, desc))
        except TypeError:
            puts('[{}]:\t{}'.format(i, l[i]))

    puts('=======')
    puts(colored.green(ques))
    def _ask(q=None):
        if q is None: q = ques
        return int(input(q))
    idx = None
    while idx is None:
        try: 
            idx = _ask('Select from {} to {}: '.format(0, len(l)-1))
        except (ValueError, TypeError):
            continue
    return l[idx]

class Janus:
    output = sys.stdout

    def __init__(self):
        self.outsinks = [func[10:] for func in dir(self) if callable(getattr(self, func)) and func.startswith("_outsink__")]
        self.enabledsinks = [] # list of tuples (cmd, *args)
        self.since = None # unix timestamp
        self.until = None # unix timestamp
        self.cachepath = None # where to store cached posts
        self.filter = None # a filter for the source, see .set_filter()
        self.source = None
        self.errors = []

    def format_prompt(self):
        ps1 = colored.magenta(self.source)
        ps1 += ' ▶ ['
        _sinks = ['sink:{}'.format(c) for c in self.enabledsinks]
        ps1 += colored.green(', '.join(_sinks)) if _sinks else colored.red('No sinks set')
        ps1 += '] '
        if self.since or self.until:
            ps1 += '|{}↦{}| '.format(self.since.isoformat(' ') if self.since else '∞', self.until.isoformat(' ') if self.until else '∞')
        ps1 += colored.yellow('({} cached) '.format(self.count_cached_files()))
        ps1 += colored.red('*{} errors* '.format(len(self.errors)))
        ps1 += '\n > '
        sys.ps1 = ps1

    def command_set_since(self, datetimestring):
        'The datetime to start the source retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.since = datestring(datetimestring) # get datetime.datetime
        if self.source is not None:
            self.source.set_since(self.since)

    def command_set_until(self, datetimestring):
        'The datetime to end the source retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.until = datestring(datetimestring) # get datetime.datetime
        if self.source is not None:
            self.source.set_until(self.until)

    def command_set_source_filter(self, filterstring):
        'Set filter on current source. The format of filterstring is dependent on the source. Args: `filterstring`'
        self.filter = filterstring
        if self.source is not None:
            self.source.set_filter(filterstring)

    def command_set_page(self, pagename):
        'Set the Facebook Page that we are pulling data from (replacing any previous source).'
        self.source = JanusFB(pagename, self.output)
        if self.since is not None:
            self.source.set_since(self.since)
        if self.until is not None:
            self.source.set_until(self.until)
        if self.filter is not None:
            self.source.set_filter(self.filter)
        self.format_prompt()

    def command_set_page_cached(self, pagename, cachedir=None):
        'Set the Facebook Page name that we will be pulling CACHED posts from (replacing any previous source).'
        if cachedir is None:
            cachedir = JANUS_CACHEDIR
        self.source = JanusFBCached(pagename, cachedir, self.output)
        self.format_prompt()

    def command_set_source_fusiontable(self):
        'Set a fusion table as source for posts (replacing any previous source).'
        fusiontables = get_fusiontables()
        logger.debug('Got ftables: %r', fusiontables)
        table = ask_iterator('Which table as source?', fusiontables)
        logger.debug('Chose ftable: %s', table)
        self.source = JanusFusiontablesSource(table, self.output)
        if self.filter is not None:
            self.source.set_filter(self.filter)
        if self.since is not None:
            self.source.set_since(self.since)
        if self.until is not None:
            self.source.set_until(self.until)
        self.format_prompt()

    def command_add_outsink_by_name(self, sinkname, *args):
        'Add a sink to send each post to. You may add several sinks'
        logger.debug('command_add_outsink: sinkname=%r, *args=%r', sinkname, args)
        _sink = '_outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.append(getattr(self, _sink)(*args))
            self.format_prompt()
        else:
            puts(colored.red('No such sink found: {}. Use `all_sinks` to list available sinks'.format(sinkname)))
            return False

    def command_disable_outsink(self):
        'Get a list of enabled sinks and disable one of them'
        sink = ask_iterator('Choose which sink you want to disable?', self.enabledsinks)
        self.enabledsinks.remove(sink)
        self.format_prompt()

    def command_add_outsink(self, *args):
        'List all possible outsinks'
        logger.debug('self.outsinks: %r', self.outsinks)
        sinkname, desc = ask_iterator('Which sink will you add?', [ (nm, getattr(self, '_outsink__'+nm).__doc__) for nm in self.outsinks ])
        _sink = '_outsink__{}'.format(sinkname)
        self.enabledsinks.append(getattr(self, _sink)(*args))
        self.format_prompt()

    def command_list_enabled_outsinks(self):
        'List all enabled outsinks'
        logger.debug('enabledsinks: %r', self.enabledsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(sink, sink.__doc__) for sink in self.enabledsinks ] )

    def _assert_sinks(self):
        'Assert that we have sinks enabled, or display error message'
        if len(self.enabledsinks) == 0: # oh oh, no sinks set to receive
            puts(colored.red('No sinks enabled. Add one and try again.'))
            puts(colored.magenta(' ( use `all_sinks` to show all possible sinks ) '))
            return False

    def command_pull_posts(self):
        'Pull posts from current FB Page (cache or online), respecting Until and Since if they are set'
        # cache receivers
        self._assert_sinks() # make sure someone receives this
        i = 0
        self.errors = []
        stop = False
        for post in self.source: # iterate through source, get JanusPost (or derivative)
            if stop == True: break
            puts(colored.blue('Handling post # {} @ {}'.format(post.id, post.datetime_created.isoformat()), self.output))
            for sink in self.enabledsinks:
                try:
                    sink.push(post)
                except KeyboardInterrupt:
                    stop = True
                    break
                except Exception as e:
                    self.errors.append( (post, e) )
            i = i+1
        for sink in self.enabledsinks:
            sink.finished() # let sinks clean up and empty their queues
        puts(colored.blue('Finished pulling {} posts from {}'.format(i, self.source), self.output))
        self.command_show_last_errors()
        self.format_prompt()

    def command_update_fusiontable(self):
        'Run through all posts in current page disk cache, and update fusiontable with any posts that are missing'

    def _outsink__file(self, path=None):
        'Store post JSON to a file on disk. Args: path (optional, defaults to JANUS_CACHEDIR)'
        if not path:
            path = JANUS_CACHEDIR
        self.cachepath = '{}/{}'.format(path, self.source.id)
        return JanusFileSink(self.cachepath, self.output)

    def _outsink__date_count(self):
        'Create a table of posts created per date (looking at `created_date`)'
        return JanusStatsSink('date_count', self.output)

    def _outsink__date_count_field_true(self, field):
        'Create a table of posts created per date, where post.`field` is True. Args: field'
        s = JanusStatsSink('date_count', self.output)
        s.set_filter(lambda x: getattr(x, field) == True)
        return s

    def _outsink__fusiontable_update(self, columns=None):
        'Update each post in the current Fusiontable source with live data from Facebook. Args: columns (optional, comma separated list of columns)'
        if not isinstance(self.source, JanusFusiontablesSource):
            raise JanusException('Need a Fusion Table as source for this sink')
        s = JanusFusiontablesFacebookUpdateSink(self.source.table, columns, self.output)
        self.format_prompt()
        return s

    def _outsink__fusiontable_calculate(self, columns):
        'Update each post in the current Fusiontable source with live data from Facebook. Args: colum rules - <Colname>=<field>'
        if not isinstance(self.source, JanusFusiontablesSource):
            raise JanusException('Need a Fusion Table as source for this sink')
        s = JanusFusiontablesUpdateSink(self.source.table, columns, self.output)
        self.format_prompt()
        return s

    def count_cached_files(self):
        logger.debug('count cache: %r', self.cachepath)
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

    def command_show_last_errors(self):
        'Show the errors from the last operation'
        if len(self.errors) == 0:
            puts(colored.green('No errors. yay'))
        else:
            puts(colored.red('There were {} errors:'.format(len(self.errors))))
            for (post, ex) in self.errors:
                puts(colored.red('ID: {}, Date: {}, Author: {} -- {}'.format(post.id, post.datetime_created.isoformat(), post.name, str(ex))))

    def command_fb_authenticate(self):
        'Start procedure to authenticate to facebook.'
        logger.debug('Starting once off server to catch token')
        q = Queue()
        thread, httpd = fb_run_oauth_endpoint(q)
        logger.debug('Authenticate fb command')
        fb_authenticate() 
        try:
            # watch queue and wait for an item
            code = q.get()
            logger.info('Got token. length: %i', len(code))
            logger.debug('Storing token in .env')
            env = find_dotenv()
            set_key(env, 'FB_APP_TOKEN', code)
            logger.debug('Reload env')
            load_dotenv(env)


        except KeyboardInterrupt:
            #Ctrl-c
            pass
        finally:
            httpd.shutdown()

if __name__ == '__main__':
    import sys
    j = Janus()
    #if args.fbpage is not None:
    #    if not args.cached:
    #        j.command_set_page(args.fbpage)
    #    else:
    #        j.command_set_page_cached(args.fbpage)
    logger.debug('sinks: %r', args.add_sink)
    if args.add_sink is not None:
        for s in args.add_sink:
            _args = s[1:] if len(s) > 1 else []
            logger.debug('adding sink: %r, args: %r', s[0], _args)
            j.command_add_outsink(s[0], *_args)
    if args.since is not None:
        j.command_set_since(args.since)
    if args.until is not None:
        j.command_set_until(args.until)

    runner = console.CommandRunner()
    runner.command('set_page', j.command_set_page)
    runner.command('set_cached_page', j.command_set_page_cached)
    runner.command('set_fusiontable', j.command_set_source_fusiontable)
    runner.command('set_since', j.command_set_since)
    runner.command('set_until', j.command_set_until)
    runner.command('set_filter', j.command_set_source_filter)
    runner.command('show_errors', j.command_show_last_errors)
    runner.command('add_sink', j.command_add_outsink)
    runner.command('add_sink_by_name', j.command_add_outsink_by_name)
    runner.command('enabled_sinks', j.command_list_enabled_outsinks)
    runner.command('disable_sink', j.command_disable_outsink)
    runner.command('pull', j.command_pull_posts)
    runner.command('fb_auth', j.command_fb_authenticate)
    j.format_prompt()
    ex = console.Console(runner).run_in_main()
    sys.exit(ex)

