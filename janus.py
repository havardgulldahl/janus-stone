#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import io
import collections
import os
import argparse
import code
import logging
from clint.textui import colored, puts, indent
import html

class Janus:

    def __init__(self):
        self.fbpage = None
        self.outsinks = [func[11:] for func in dir(Janus) if callable(getattr(Janus, func)) and func.startswith("__outsink__")]
        self.enabledsinks = set()
        self.since = None # datetime.datetime
        self.until = None # datetime.datetime

    def command_set_since(self, dt):
        self.since = dt

    def command_set_until(self, dt):
        self.until = dt

    def command_set_page(self, pagename):
        self.fbpage = pagename

    def command_add_outsink(self, sinkname):
        _sink = '__outsink__{}'.format(sinkname)
        if hasattr(self, _sink): 
            self.enabledsinks.add(sinkname)

    def __outsink__file(self, post, path='./data'):
        postpath = '{}/{}'.format(path, self.fbpage)
        if not os.path.exists(postpath):
            os.makedirs(postpath)
        with io.open('{}/{}.json'.format(postpath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())

    def __outsink__fusiontables(self, post, tableid):
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
    runner = CommandRunner()
    runner.command('set_page', j.enter)
    runner.command('exit', room.exit)
    runner.command('room', room.room)
    return Console(runner).run_in_main(fd)




if __name__ == '__main__':
    sys.exit(main())

