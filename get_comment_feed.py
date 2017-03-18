#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import facebook
import requests

JANUS_APP_ID='264804657310512'
JANUS_APP_TOKEN='441046be6a35caaa163e5e69309a587c'
JANUS_APP_TOKEN='EAACEdEose0cBAHNjPZArRvKoPZBcTNnoCSwkswOON6ZB8C2YZBjLsHRZB6vDdnU1x1X1HVR56eCcVeTZCw9EhEQ2IixAv1JeUSiu0QshElHAQzEZBxNQ6KXAGSXOtahDIYlpSC9BTCsDGkRR3eIuE5nsJzBFuVrYQMV0bPKKOgzGVB4O9xbhdFn65qaMzLw9zcZD'

graph = facebook.GraphAPI(access_token=JANUS_APP_TOKEN, version='2.8')

page = graph.get_object(id='dnb')

fields = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message},likes{name}'}
feed = graph.get_connections(page['id'], 'feed', args=fields)

g = graph.request('/dnb/feed', {'fields':'from,id,message,created_time,status_type,comments{from,id,like_count,message},likes{name}'})

def store_post(post):
    print("{created_time} by {id}: {message}".format(**post))

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
while True:
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        [store_post(post=post) for post in feed['data']]
        # Attempt to make a request to the next page of data, if it exists.
        cont = input('=================== continue? =================== ')
        feed = requests.get(feed['paging']['next']).json()
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        raise
        break


