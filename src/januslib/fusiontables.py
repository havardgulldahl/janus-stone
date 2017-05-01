import logging
import colorlog
import collections
import time
import fusionclient
from . import JanusSink, JanusSource, JanusPost, JanusException
from . import fb
import dateutil.parser
import html
from clint.textui import colored, puts, indent

logger = colorlog.getLogger('Janus.januslib.fusiontables')

FUSION_INSERT_QUEUE_MAX=25

class JanusFusiontablesException(JanusException):
    pass

class JanusFusiontablesCoolDownException(JanusFusiontablesException):
    pass

__all__ = ['JanusFusiontablesSink', 
           'JanusFusiontablesFacebookUpdateSink', 
           'JanusFusiontablesSource', 
           'JanusFusiontablePost',
           'get_fusiontables',
           ]

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

def get_fusiontables():
    'Get a list of all fusion tables'
    fus = fusionclient.Fusion()
    try:
        return [JanusFusiontable(t) for t in fus.run(fus.service.table().list())['items']]
    except KeyError:
        return []

class JanusFusiontablesSink(JanusSink):

    # https://developers.google.com/fusiontables/docs/v2/reference/
    def __init__(self, table, output):
        super().__init__(output)
        self.table = table
        self.fusion = fusionclient.Fusion()
        self._q = []
        #self.metadata = self.fusion.run(self.fusion.service.table().get(tableId=tableid))

    def __str__(self):
        'return pretty name'
        n = str(self.table)
        return '>>>Fusiontable({})'.format(self._slugify(n))

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
        self.run(self.fusion.insertrows, self.table.tableid, rowdata)

    def run(self, function, *args):
        http_code, status = function(*args)
        if http_code > 201:
            puts(colored.red(repr(status)))
            puts('Error detected! Cooling down for a bit might work', self.output)
            time.sleep(2.0)
        else:
            if 'kind' in status and status['kind'] == 'fusiontables#sqlresponse':
                luck = '{} rows added: {}.'.format(len(status['rows']), status['rows'])
            else: # dont know what the format is
                luck = repr(status)
            puts(colored.green(luck), self.output)

class JanusFusiontablesFacebookUpdateSink(JanusFusiontablesSink):
    'Update an existing fusion table with Facebook posts for each row'

    def __init__(self, table, columns, output):
        super().__init__(table, output)
        if columns is None:
            self.updateCols = ['share_count', 'comment_count', 'like_count', 'permalink'] # which columns to update (JanusFacebookPost.<col>)
        else:
            self.updateCols = columns

    def __str__(self):
        'return pretty name'
        n = str(self.table)
        return '>>>FusiontablesFacebookUpdate({})'.format(self._slugify(n))

    def push(self, post):
        'Take a fusiontable post and SQL UPDATE the existing table with data from live facebook'
        try:
            fresh_fb = fb.getPost(post.id)
        except JanusException as e:
            logger.exception(e)
            puts(colored.red(repr(e)))
            return
        _map = { 'share_count': 'Delinger', #TODO: Get rid of this
                 'comment_count': 'AntallKommentarer',
                 'like_count': 'Likes',
                 'permalink': 'Permalink',
                 }
        cols = [ " '{}'='{}' ".format(_map[col],getattr(fresh_fb, col)) for col in self.updateCols ]
        q = "UPDATE {} SET {} WHERE ROWID='{}'".format(self.table.tableid, ','.join(cols), post.rowid)
        logger.debug('about to UPDATE SQL rowid=%r: %r', post.rowid, q)
        self.run(self.fusion.sql, q)
        time.sleep(2.0)

class JanusFusiontablesSource(JanusSource):

    # https://developers.google.com/fusiontables/docs/v2/reference/
    def __init__(self, table, output):
        super().__init__(output)
        self.table = table
        self.id = table.tableid
        self.fusion = fusionclient.Fusion()
        #self.metadata = self.fusion.run(self.fusion.service.table().get(tableId=tableid))

    def __str__(self):
        'return pretty name'
        n = str(self.table)
        return '<<<Fusiontables({})>'.format(self._slugify(n))

    def autenticate(self):
        raise NotImplementedError # TODO: FIX

    def __iter__(self):
        colnames = [ c['name'] for c in self.table.metadata['columns'] ]
        where = [self.filter,] if self.filter is not None else []
        if self.since is not None: # its a datetime.datetime
            where.append(""" 'Dato' >= '{}' """.format(self.since.strftime('%Y.%m.%d')))
        if self.until is not None: # its a datetime.datetime
            where.append(""" 'Dato' <= '{}' """.format(self.until.strftime('%Y.%m.%d')))
            
        q = self.fusion.select(colnames, self.table.tableid, where=where)
        yield from [ JanusFusiontablePost(q['columns'], post) for post in q['rows'] ]
        

class JanusFusiontable:
    'A object wrapper for a Fusion Table'

    def __init__(self, metadata):
        self.metadata = metadata
        logger.debug('Got table metadata: %r', metadata)

    def __str__(self):
        return self.name

    @property
    def tableid(self):
        return self.metadata['tableId']

    @property
    def name(self):
        return self.metadata['name']

class JanusFusiontablePost(JanusPost):
    'A post from Fusion Tables, with a standard interface'

    def __init__(self, columns, rowdata):
        self.post = { col:data for (col, data) in zip(columns, rowdata) }
        logger.debug('setting self.post= %r', self.post)

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
        return self.post['Avsender']

    @property
    def media(self):
        return self.post['Media']
