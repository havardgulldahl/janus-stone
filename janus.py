#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import io
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

class Janus:

    def __init__(self):
        self.fbpage = None
        self.outsinks = [func[11:] for func in dir(self) if callable(getattr(self, func)) and func.startswith("__outsink__")]
        self.enabledsinks = []
        self.since = None # datetime.datetime
        self.until = None # datetime.datetime

    def command_set_since(self, datetimestring):
        'The datetime to start the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.since = datestring(datetimestring)

    def command_set_until(self, datetimestring):
        'The datetime to end the Facebook Page retrieval at. Args: timestamp, format YYYY-MM-DD [HH:MM:SS]'
        self.until = datestring(datetimestring)

    def command_set_page(self, pagename):
        'Set the Facebook Page that we are pulling data from. Mandatory'
        self.fbpage = pagename

    def command_add_outsink(self, sinkname, *args):
        'Add a sink to send each post to. You may add several sinks'
        _sink = '__outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.append((sinkname, *args))

    def command_list_outsinks(self):
        'List all possible outsinks'
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, getattr(self, '__outsink__'+nm).__doc__) for nm in self.outsinks ] )

    def command_list_enabled_outsinks(self):
        'List all enabled outsinks'
        return '\n'.join( [ '{}\t:\t\t{}'.format(nm, args) for (nm, args) in self.enabledsinks ] )

    def __outsink__file(self, post, path='./data'):
        'Store post JSON to a file on disk. Args: path (optional)'
        postpath = '{}/{}'.format(path, self.fbpage)
        if not os.path.exists(postpath):
            os.makedirs(postpath)
        with io.open('{}/{}.json'.format(postpath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())

    def __outsink__fusiontables(self, post, tableid):
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

