#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from datetime import datetime
import requests
from clint.textui import colored, puts, indent
from pprint import pprint
import argparse
import facebook

JANUS_APP_ID='264804657310512'
JANUS_APP_TOKEN='441046be6a35caaa163e5e69309a587c'
JANUS_APP_TOKEN='EAACEdEose0cBAHNjPZArRvKoPZBcTNnoCSwkswOON6ZB8C2YZBjLsHRZB6vDdnU1x1X1HVR56eCcVeTZCw9EhEQ2IixAv1JeUSiu0QshElHAQzEZBxNQ6KXAGSXOtahDIYlpSC9BTCsDGkRR3eIuE5nsJzBFuVrYQMV0bPKKOgzGVB4O9xbhdFn65qaMzLw9zcZD'


def datestring(string):
    try:
        value = datetime.strptime(string, '%Y-%m-%d')
        return value.timestamp()
    except ValueError:
        msg = "%r is not a YYYY-MM-DD date" % string
        raise argparse.ArgumentTypeError(msg)

argp = argparse.ArgumentParser()
argp.add_argument('--since', type=datestring, help='Date in YYYY-MM-DD format')
argp.add_argument('--until', type=datestring, help='Date in YYYY-MM-DD format')

args = argp.parse_args()

graph = facebook.GraphAPI(access_token=JANUS_APP_TOKEN, version='2.8')

params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message},likes{name}'}

if args.since:
    params['since'] = args.since
if args.until:
    params['until'] = args.until

feed = graph.request('/dnb/feed', params)

def store_post(post):
    #pprint(post)
    #print("{created_time} by {from}: {message}".format(**post))
    likes = len(post['likes']) if 'likes' in post else 0
    comments = post['comments']['data'] if 'comments' in post else []
    message = post['message'] if 'message' in post else ''
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
        [store_post(post=post) for post in feed['data']]
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


