#-*- enc: utf-8

import logging
import colorlog
import os
import html
from pathlib import Path
import facebook
import requests
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from clint.textui import colored, puts, indent

import http.server
import socketserver
import threading
import urllib

logger = logging.getLogger('Janus.januslib.fb')

from . import JanusSource, JanusPost, JanusException

class JanusFB(JanusSource):

    def __init__(self, facebookpage, output):
        super().__init__(output)
        self.pagename = facebookpage
        self.id = facebookpage
        self.graph = None

        # seed feed
        self.params = {'fields': 'from,id,message,created_time,status_type,comments{from,id,like_count,message,comments{from,like_count,created_time,message,comments{from,like_count,created_time,message}},created_time},likes{name},shares,type,source,picture,link,permalink_url'
        }

    def __str__(self):
        'return pretty name'
        return '<<<FacebookPageONLINE({})'.format(self.pagename)

    def authenticate(self):
        self.graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')

    def set_since(self, timestamp): # timestamp is datetime.datetime
        self.params['since'] = timestamp.value() # convert to unix timestamp

    def set_until(self, timestamp): # timestamp is datetime.datetime
        self.params['until'] = timestamp.value() # convert to unix timestamp

    def __iter__(self):
        if self.graph is None:
            self.authenticate()
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
                    yield JanusFacebookPost(post)
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
        self.id = facebookpage
        self.cachepath = Path(datapath, facebookpage)

        if not self.cachepath.is_dir():
            puts(colored.red('Error! No existing cache found in {!r}'.format(datapath)))

    def __str__(self):
        'return pretty name'
        return '<<<FacebookPageCACHED({})'.format(self.pagename)

    def __iter__(self):
        yield from [JanusFacebookPost(p) for p in self.cachepath.glob('*.json')]

class JanusFacebookPost(JanusPost):
    'A Facebook post with a standard JanusPost interface'

    def __init__(self, json_or_path):
        if isinstance(json_or_path, Path):
            self.path = json_or_path
            with json_or_path.open() as f:
                self.post = json.loads(f.read())
        elif isinstance(json_or_path, dict):
            self.post = json_or_path
            self.path = None
        elif os.path.exists(json_or_path):
            self.path = Path(json_or_path)
            self.post = json.load(json_or_path)
        else:
            self.post = json.loads(json_or_path)
            self.path = None

    @property
    def id(self):
        return self.post['id']
                    
    @property
    def datetime_created(self):
        '''Return datetetime.datetime representing the post's `created_time` field'''
        return dateutil.parser.parse(self.post['created_time'])

    @property
    def date_created(self):
        '''Return datetetime.date representing the post's `created_time` field'''
        return dateutil.parser.parse(self.post['created_time']).date()

    @property
    def like_count(self):
        return self.post['likes']['summary']['total_count'] if 'likes' in self.post else 0

    @property
    def share_count(self):
        return self.post['shares']['count'] if 'shares' in self.post else 0

    @property
    def comment_count(self):
        return self.post['comments']['summary']['total_count'] if 'comments' in self.post else 0

    @property
    def comments(self):
        return self.post['comments']['data'] if 'comments' in self.post else []

    def comments_html(self, comments_struct):
        'Turn a json list of comments into an html string'
        s = ['<ul>', ]
        for com in comments_struct:
            s.append('<li><b>{}</b> (+{}): {}'.format(html.escape(com['from']['name']), 
                                                      com['like_count'], 
                                                      html.escape(com['message'])
                                                      )
                    )
            if 'comments' in com:
                #recurse into nested comment
                s.append(comments_html(com['comments']['data']))
            s.append('</li>')
        s.append('</ul>')
        return ''.join(s)

    @property
    def message(self):
        return self.post['message'] if 'message' in self.post else ''

    @property
    def link(self):
        return self.post['link'] if 'link' in self.post else ''

    @property
    def permalink(self):
        return self.post['permalink_url'] if 'permalink_url' in self.post else ''

    @property
    def name(self):
        try:
            return self.post['from']['name']
        except KeyError:
            try:
                return self.post['data']['name']
            except KeyError:
                return 'Unknown'

    @property
    def media(self):
        try:
            if self.post['type'] == 'video':
                return post['source']
            elif self.post['type'] == 'photo':
                return self.post['picture']
            else:
                return ''
        except KeyError:
            return ''

def getPost(postid):
    'Get a facebook post by its `postid`, returning JanusFacebookPost'

    graph = facebook.GraphAPI(access_token=os.environ.get('FB_APP_TOKEN'), version='2.8')
    params = {'fields': 'from,id,message,created_time,likes.summary(1),status_type,comments.summary(1),shares,type,source,picture,link,permalink_url'}
    try:
        fbpost = graph.request('{}'.format(postid), params)
        return JanusFacebookPost(fbpost)
    except facebook.GraphAPIError as e:
        raise JanusException(str(e))

def fb_authenticate():
    permissions = ['public_profile',]
    canvas_url = 'http://gulldahlpc.local:8080/'
    fb_login_url = facebook.auth_url(os.environ.get('FB_APP_ID'), canvas_url, permissions, response_type='token')
    puts(colored.blue('Go to the following url in a browser to complete login:\n{}'.format(fb_login_url)))

class AuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        'Parse token from query'
        logger.debug('Got query: %r', self.path[:10] if len(self.path)>10 else self.path)
        query = {}
        if self.path.startswith('/?token='): # got token
            query = urllib.parse.parse_qs(self.path[2:])
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        if not 'token' in query:
            self.wfile.write('''<html><body onload="window.location.href='/?token='+window.location.hash.substring(14)">Token REDIRECT</body></html>'''.encode())
        else:
            self.wfile.write('''<html><body>Token captured. Please return to the Janus console</body></html>'''.encode())
            self.server.q.put(query['token'].pop())

    def log_message(self, format, *args):
        return # dont log anything

class Server(socketserver.TCPServer):
    allow_reuse_address = True

def fb_run_oauth_endpoint(q):
    'Start a webserver at 0.0.0.0:8080 to catch oauth code, update queue.Queue `q`'

    port = 8080
    addr = '0.0.0.0'

    httpd = Server((addr, port), AuthHandler, bind_and_activate=False)
    httpd.server_bind()
    httpd.server_activate()
    httpd.q = q
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()
    logger.debug("OAuth Endpoint live at http://{0}:{1}".format(addr, port))
    return t, httpd

