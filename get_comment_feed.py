#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import html
import os
from datetime import datetime
import requests
import json
from clint.textui import colored, puts, indent
from pprint import pprint
import argparse
import facebook
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import fusionclient

def datestring(string):
    try:
        value = datetime.strptime(string, '%Y-%m-%d')
        return value.timestamp()
    except ValueError:
        msg = "%r is not a YYYY-MM-DD date" % string
        raise argparse.ArgumentTypeError(msg)

argp = argparse.ArgumentParser()
argp.add_argument('pagename')
argp.add_argument('fusiontable')
argp.add_argument('--since', type=datestring, help='Date in YYYY-MM-DD format')
argp.add_argument('--until', type=datestring, help='Date in YYYY-MM-DD format')

args = argp.parse_args()

fusion = fusionclient.Fusion()
graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')

params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message},likes{name},attachments{media,description}'
            }

if args.since:
    params['since'] = args.since
if args.until:
    params['until'] = args.until

feed = graph.request('/{}/feed'.format(args.pagename), params)

def htmldumps(comments):
    s = ['<ul>', ]
    for com in comments:
        s.append('<li><b>{}</b> (+{}): <i>{}</i></li>'.format(html.escape(com['from']['name']), com['like_count'], html.escape(com['message'])))
    s.append('</ul>')
    return ''.join(s)

def store_post(post):
    #print("{created_time} by {from}: {message}".format(**post))
    likes = len(post['likes']) if 'likes' in post else 0
    comments = post['comments']['data'] if 'comments' in post else []
    message = post['message'] if 'message' in post else ''
    link = post['link'] if 'link' in post else ''
    try:
        if post['type'] == 'video':
            media = post['source']
        elif post['type'] == 'photo':
            media = post['picture']
        else:
            media = ''
    except KeyError:
        media = ''
    sql = """INSERT INTO {} ('ID', 'Dato', 'Avsender', '# Likes', 'Melding', 'Link', 'Media', '# kommentarer', 'kommentarer')
             VALUES ('{}', '{}', '{}', {}, '{}', '{}', '{}', {}, '{}')""".format(args.fusiontable,
                                                                                 post['id'],
                                                                                 post['created_time'],
                                                                                 html.escape(post['from']['name']),
                                                                                 likes,
                                                                                 html.escape(message),
                                                                                 link, 
                                                                                 media,
                                                                                 len(comments),
                                                                                 htmldumps(comments))
    print(repr(sql))
    fusion.sql(sql)
    puts(colored.green(post['from']['name']) + \
            colored.blue(' @ {}'.format(post['created_time'])) + \
            colored.yellow('(+{}): '.format(likes)) + \
            colored.black(message))
    with indent(8, quote=' >'):
        for com in comments:
            puts(colored.magenta(com['from']['name']) + colored.yellow(' (+{}): '.format(com['like_count'])) + com['message'])
    puts('----------\n')
        
    

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
while True:
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        for post in feed['data']:
            store_post(post)
        # Attempt to make a request to the next page of data, if it exists.
        cont = input('=================== continue? press y =================== ')
        if cont.strip().lower() != 'y': break
        feed = requests.get(feed['paging']['next']).json()
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        raise
        break
    except KeyboardInterrupt:
        print('\n')
        break


