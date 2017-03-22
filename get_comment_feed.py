#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import io
import time
import html
import os
from datetime import datetime
import requests
import json
from clint.textui import colored, puts, indent
from pprint import pprint
import argparse
import dateutil.parser
import facebook
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import logging
logging.basicConfig(level=logging.INFO)

import fusionclient

def datestring(string):
    try:
        value = datetime.strptime(string, '%Y-%m-%d')
        return value.timestamp()
    except ValueError:
        try:
            value = datetime.strptime(string, '%Y-%m-%d %H:%M:%S')
            return value.timestamp()
        except ValueError:
            msg = "%r is not a YYYY-MM-DD date" % string
            raise argparse.ArgumentTypeError(msg)

argp = argparse.ArgumentParser()
argp.add_argument('pagename')
argp.add_argument('fusiontable')
argp.add_argument('--since', type=datestring, help='Date in YYYY-MM-DD [HH:MM:SS] format')
argp.add_argument('--until', type=datestring, help='Date in YYYY-MM-DD [HH:MM:SS] format')
argp.add_argument('--store', action="store_true", default=False, help='Keep a copy of the FB post in .data/ as JSON file')

args = argp.parse_args()

fusion = fusionclient.Fusion()

graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')

params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message},likes{name},shares,type,source,picture,link'
            }

if args.since:
    params['since'] = args.since
if args.until:
    params['until'] = args.until

feed = graph.request('/{}/feed'.format(args.pagename), params)

def simplify_timestamp(datestring):
    '''2016-12-31T21:56:10+0000' -> 2016-12-31 21:56:10'''
    yourdate = dateutil.parser.parse(datestring)
    return yourdate.strftime('%Y-%m-%d %H:%M:%S')

def comments_html(comments):
    'Turn a json list of comments into an html string'
    s = ['<ul>', ]
    for com in comments:
        s.append('<li><b>{}</b> (+{}): {}</li>'.format(html.escape(com['from']['name']), com['like_count'], html.escape(com['message'])))
    s.append('</ul>')
    return ''.join(s)

def store_post(post, keep_disk_copy=None):
    #pprint(post)
    if keep_disk_copy:
        with io.open('./.data/{}.json'.format(post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())
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

    kwargs = {
        'ID': post['id'],
        'Dato': simplify_timestamp(post['created_time']),
        'Avsender': html.escape(name),
        '# Likes': likes,
        'Melding': html.escape(message),
        'Link': link, 
        'Media': media,
        '# kommentarer': len(comments),
        'kommentarer': comments_html(comments),
        'Delinger': shares,
    }
    puts(colored.magenta(name) + \
         colored.blue(' @ {}'.format(post['created_time'])))
    return fusion.insertrow(args.fusiontable, kwargs)

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
cont = True
while cont == True:
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        for post in feed['data']:
            http_code, status = store_post(post, keep_disk_copy=args.store)
            if http_code > 201:
                puts(colored.red(repr(status)))
                puts('Error detected! Cooling down for a bit might work')
                cont = input('=================== Continue? press y =================== '.format(i))
                if cont.strip().lower() != 'y': 
                    cont = False
                    break
            else:
                if 'kind' in status and status['kind'] == 'fusiontables#sqlresponse':
                    luck = 'Row added. New row total is {}.'.format(status['rows'])
                else: # dont know what the format is
                    luck = repr(status)
                puts(colored.green(luck))
            time.sleep(1.7) # avoid rate limiting
        # Attempt to make a request to the next page of data, if it exists.
        feed = requests.get(feed['paging']['next']).json()
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        raise
        break
    except KeyboardInterrupt:
        print('\n')
        break


