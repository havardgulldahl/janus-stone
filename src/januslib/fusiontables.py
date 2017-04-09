import logging
import collections
import fusionclient
from . import JanusSink, JanusSource
import dateutil.parser
import html
from clint.textui import colored, puts, indent

FUSION_INSERT_QUEUE_MAX=25

def fusionify_timestamp(datestring):
    '''2016-12-31T21:56:10+0000' -> 2016-12-31 21:56:10'''
    yourdate = dateutil.parser.parse(datestring)
    return yourdate.strftime('%Y-%m-%d %H:%M:%S')

def comments_html(comments):
    'Turn a json list of comments into an html string'
    s = ['<ul>', ]
    for com in comments:
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


class JanusFusiontablesSink(JanusSink):

    # https://developers.google.com/fusiontables/docs/v2/reference/
    def __init__(self, tableid, output):
        super().__init__(output)
        self.tableid = tableid
        self.fusion = fusionclient.Fusion()
        self._q = []

    def __str__(self):
        'return pretty name'
        return '<#{} Fusiontables(->{}..)>'.format(self.id, self.tableid[:8])

    def autenticate(self):
        raise NotImplementedError # TODO: FIX

    def __format_post(self, post):
        # beat structure out of post data, which will vary from post to post
        likes = len(post['likes']) if 'likes' in post else 0
        shares = post['shares']['count'] if 'shares' in post else 0
        comments = post['comments']['data'] if 'comments' in post else []
        message = post['message'] if 'message' in post else ''
        link = post['link'] if 'link' in post else ''
        permalink = post['permalink_url'] if 'permalink_url' in post else ''
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
            'Dato': fusionify_timestamp(post['created_time']),
            'Avsender': html.escape(name),
            '# Likes': likes,
            'Melding': html.escape(message.replace('\n', ' ')),
            'Link': link, 
            'Media': media,
            '# kommentarer': len(comments),
            'kommentarer': comments_html(comments),
            'Delinger': shares,
            'Permalink': permalink,
        })
        return kwargs

    def push(self, post):
        'Take a post and prepare it for upload'
        squeezed_post = self.__format_post(post)
        self._q.append(squeezed_post)
        if len(self._q) == FUSION_INSERT_QUEUE_MAX:
            self.insert_sql(self._q)
            self._q = []

    def finished(self):
        'Finish off queue'
        if len(self._q) > 0:
            self.insert_sql(self._q)
        
    def insert_sql(self, rowdata):
        http_code, status = self.fusion.insertrows(self.tableid, rowdata)
        if http_code > 201:
            puts(colored.red(repr(status)))
            puts('Error detected! Cooling down for a bit might work', self.output)
        else:
            if 'kind' in status and status['kind'] == 'fusiontables#sqlresponse':
                luck = '{} rows added: {}.'.format(len(status['rows']), status['rows'])
            else: # dont know what the format is
                luck = repr(status)
            puts(colored.green(luck), self.output)

class JanusFusiontablesSource(JanusSource):

    # https://developers.google.com/fusiontables/docs/v2/reference/
    def __init__(self, tableid, output):
        super().__init__(output)
        self.tableid = tableid
        self.fusion = fusionclient.Fusion()
        self.tables = self.fusion.run(self.fusion.service.table().list())['items']
        self.metadata = None
        for t in self.tables:
            if t['tableId'] == tableid:
                self.metadata = t
        self.filter = None # is set in JanusSource.set_filter

    def __str__(self):
        'return pretty name'
        n = self.metadata['name']
        return '<<<Fusiontables({}..)>'.format(n[:8] if len(n)>8 else n)

    def autenticate(self):
        raise NotImplementedError # TODO: FIX

    def __iter__(self):
        colnames = [ c['name'] for c in self.metadata['columns'] ]
        q = self.fusion.select(colnames, self.tableid, self.filter)
        return iter(q['rows'])
        
        

