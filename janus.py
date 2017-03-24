#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import io
import fnmatch
import collections
import os
import argparse
import code
import logging
import datetime
from clint.textui import colored, puts, indent
import html

import console

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

args = argp.parse_args()

logging.basicConfig(level=args.loglevel)

class Janus:

    def __init__(self):
        self.fbpage = None
        self.outsinks = [func[10:] for func in dir(self) if callable(getattr(self, func)) and func.startswith("_outsink__")]
        self.enabledsinks = [] # list of tuples (cmd, *args)
        self.since = None # datetime.datetime
        self.until = None # datetime.datetime
        self.cachepath = None # where to store cached posts

    def format_prompt(self):
        ps1 = '{} '.format(self.fbpage or 'FB Page unset')
        ps1 += '-> [{}] '.format(', '.join([c[0] for c in self.enabledsinks]))
        ps1 += '({} posts in cache) > '.format(self.count_cached_files())
        sys.ps1 = ps1

    def command_set_since(self, datetimestring):
        'The datetime to start the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.since = datestring(datetimestring)

    def command_set_until(self, datetimestring):
        'The datetime to end the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.until = datestring(datetimestring)

    def command_set_page(self, pagename):
        'Set the Facebook Page that we are pulling data from. Mandatory'
        self.fbpage = pagename
        self.format_prompt()

    def command_add_outsink(self, sinkname, *args):
        'Add a sink to send each post to. You may add several sinks'
        _sink = '_outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.append((sinkname, *args))
            self.format_prompt()

    def command_list_outsinks(self):
        'List all possible outsinks'
        logging.debug('self.outsinks: %r', self.outsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, getattr(self, '_outsink__'+nm).__doc__) for nm in self.outsinks ] )

    def command_list_enabled_outsinks(self):
        'List all enabled outsinks'
        logging.debug('enabledsinks: %r', self.enabledsinks)
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, args) for (nm, args) in self.enabledsinks ] )

    def _outsink__file(self, post, path='./data'):
        'Store post JSON to a file on disk. Args: path (optional)'
        self.cachepath = '{}/{}'.format(path, self.fbpage)
        if not os.path.exists(self.cachepath):
            os.makedirs(self.cachepath)
        with io.open('{}/{}.json'.format(self.cachepath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())

    def count_cached_files(self):
        return len(fnmatch.filter(os.listdir(self.cachepath), '*.json'))

    def _outsink__fusiontables(self, post, tableid):
        'Push Post data to Google Fusion Tables. Args:  tableid'
        likes = len(post['likes']) if 'likes' in post else 0
        shares = post['shares']['count'] if 'shares' in post else 0
        comments = post['comments']['data'] if 'comments' in post else []
        message = post['message'] if 'message' in post else ''
        link = post['link'] if 'link' in post else ''
        try:
            name = post['from']['name']
        except KeyError:
            try:
                name = post['data']['name']
            except KeyError:
                name = 'Unknown'
        try:
            if post['type'] == 'video':
                media = post['source']
            elif post['type'] == 'photo':
                media = post['picture']
            else:
                media = ''
        except KeyError:
            media = ''

        kwargs = collections.OrderedDict({
            'ID': post['id'],
            'Dato': simplify_timestamp(post['created_time']),
            'Avsender': html.escape(name),
            '# Likes': likes,
            'Melding': html.escape(message.replace('\n', ' ')),
            'Link': link, 
            'Media': media,
            '# kommentarer': len(comments),
            'kommentarer': comments_html(comments),
            'Delinger': shares,
        })
        puts(colored.magenta(name) + \
            colored.blue(' @ {}'.format(post['created_time'])))
        #return fusion.insertrow(args.fusiontable, kwargs)
        return kwargs

        
def main(fd=None):
    j = Janus()
    runner = console.CommandRunner()
    runner.command('set_page', j.command_set_page)
    runner.command('set_since', j.command_set_since)
    runner.command('set_until', j.command_set_until)
    runner.command('add_sink', j.command_add_outsink)
    runner.command('all_sinks', j.command_list_outsinks)
    runner.command('enabled_sinks', j.command_list_enabled_outsinks)
    return console.Console(runner).run_in_main(fd)




if __name__ == '__main__':
    import sys
    sys.exit(main())

