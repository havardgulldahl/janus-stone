#-*- enc: utf-8

import facebook
import requests
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from clint.textui import colored, puts, indent

from . import JanusSource

class JanusFB(JanusSource):

    def __init__(self, facebookpage, output):
        super().__init__(output)
        self.graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')
        self.pagename = facebookpage

        # seed feed
        self.params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message,comments{from,like_count,created_time,message,comments{from,like_count,created_time,message}},created_time},likes{name},shares,type,source,picture,link,permalink_url'
                    }

    def authenticate(self):
        raise NotImplementedError

    def set_since(self, timestamp):
        self.params['since'] = timestamp

    def set_until(self, timestamp):
        self.params['until'] = timestamp

    def __iter__(self):
        self.feed = self.graph.request('/{}/feed'.format(self.pagename), self.params)
        # Wrap this block in a while loop so we can keep paginating requests until
        # finished.
        cont = True
        while cont == True:
            if len(self.feed['data']) == 0: # no posts (left)
                raise StopIteration
            puts(colored.magenta('Trawling through {} posts:'.format(len(self.feed['data']))), self.output)
            try:
                # Perform some action on each post in the collection we receive from
                # Facebook.
                for post in self.feed['data']:
                    yield post
                # Attempt to make a request to the next page of data, if it exists.
                self.feed = requests.get(self.feed['paging']['next']).json()
            except KeyError:
                # When there are no more pages (['paging']['next']), break from the
                # loop and end the script.
                raise StopIteration

