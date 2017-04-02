#-*- enc: utf-8

import os
from pathlib import Path
import facebook
import requests
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from clint.textui import colored, puts, indent

from . import JanusSource, JanusPost

class JanusFB(JanusSource):

    def __init__(self, facebookpage, output):
        super().__init__(output)
        self.graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')
        self.pagename = facebookpage

        # seed feed
        self.params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message,comments{from,like_count,created_time,message,comments{from,like_count,created_time,message}},created_time},likes{name},shares,type,source,picture,link,permalink_url'
                    }

    def __str__(self):
        'return pretty name'
        return '@{} (online)'.format(self.pagename)

    def authenticate(self):
        permissions = ['public_profile',]
        canvas_url = 'http://gulldahlpc.local:8000/test'
        fb_login_url = self.graph.auth_url(os.environ.get('FB_APP_ID'), canvas_url, permissios)
        puts(colored.blue('Go to the following url in a browser to complete login: {}'.format(fb_login_url), self.output))

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
                    yield JanusPost(post)
                # Attempt to make a request to the next page of data, if it exists.
                self.feed = requests.get(self.feed['paging']['next']).json()
            except KeyError:
                # When there are no more pages (['paging']['next']), break from the
                # loop and end the script.
                raise StopIteration

class JanusFBCached(JanusSource):
    'Reading Facebook posts from disk cache'

    def __init__(self, facebookpage, datapath, output):
        super().__init__(output)
        self.graph = None
        self.pagename = facebookpage
        self.cachepath = Path(datapath, facebookpage)

        if not self.cachepath.is_dir():
            puts(colored.red('Error! No existing cache found in {!r}'.format(datapath)))

    def __str__(self):
        'return pretty name'
        return '@{} (CACHED)'.format(self.pagename)

    def __iter__(self):
        yield from [JanusPost(p) for p in self.cachepath.glob('*.json')]
