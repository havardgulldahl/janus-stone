import logging
import collections
import fusionclient
from . import JanusSink, JanusSource, JanusPost
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
        likes = post['likes']['summary']['total_count'] if 'likes' in post else 0
        shares = post['shares']['count'] if 'shares' in post else 0
        comments = post['comments']['data'] if 'comments' in post else []
        comments_count = post['comments']['summary']['total_count'] if 'comments' in post else 0
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
            'Likes': likes,
            'Melding': html.escape(message.replace('\n', ' ')),
            'Link': link, 
            'Media': media,
            'AntallKommentarer': comments_count,
            'Kommentarer': comments_html(comments),
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

class JanusFusiontablesFacebookUpdateSink(JanusFusiontablesSink):
    'Update an existing fusion table with Facebook posts for each row'

    def __init__(self, tableid, output):
        super().__init__(tableid, output)
        updateCols = ['share_count', 'comment_count', 'like_count'] # which columns to update (JanusFacebookPost.<col>)

    def __str__(self):
        'return pretty name'
        return '<#{} FusiontablesFacebookUpdate(->{}..)>'.format(self.id, self.tableid[:8])

    def push(self, post):
        'Take a fusiontable post and SQL UPDATE the existing table with data from live facebook'
        fresh_fb = fb.getPost(post.id)
        cols = [ " '{}'='{}' ".format(col,getattr(fresh_fb, col)) for col in self.updateCols ]
        rowid = post.get('rowid', None)
        q = "UPDATE {} SET {} WHERE ROWID='{}'".format(self.tableid, ','.join(cols), rowid)
        logging.debug('about to UPDATE SQL rowid=%r: %r', q)


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
        return '<<<Fusiontables({}..)>'.format(n[:12] if len(n)>12 else n)

    def autenticate(self):
        raise NotImplementedError # TODO: FIX

    def __iter__(self):
        colnames = [ c['name'] for c in self.metadata['columns'] ]
        q = self.fusion.select(colnames, self.tableid, self.filter)
        yield from [ JanusFusiontablePost(q['columns'], post) for post in q['rows'] ]
        

class JanusFusiontablePost(JanusPost):
    'A post from Fusion Tables, with a standard interface'

    def __init__(self, columns, rowdata):
        self.post = { col:data for (col, data) in zip(columns, rowdata) }
        logging.debug('setting self.post= %r', self.post)

    @property
    def id(self):
        return self.post['ID']

    @property
    def rowid(self):
        return self.post['rowid']

    @property
    def datetime_created(self):
        '''Return datetetime.datetime representing the post's `created_time` field'''
        return dateutil.parser.parse(self.post['Dato'])

    @property
    def like_count(self):
        return self.post['Likes']

    @property
    def share_count(self):
        return self.post['Delinger']

    @property
    def comment_count(self):
        return post['AntallKommentarer']

    @property
    def comments(self):
        return self.post['Kommentarer']

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
        return self.post['Melding']

    @property
    def link(self):
        return self.post['Link'] 

    @property
    def permalink(self):
        return self.post['Permalink'] 

    @property
    def name(self):
        return post['Avsender']

    @property
    def media(self):
        return post['Media']
