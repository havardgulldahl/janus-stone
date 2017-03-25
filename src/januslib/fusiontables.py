import collections
import fusionclient
from . import JanusSink
import dateutil
import html

FUSION_INSERT_QUEUE_MAX=25

def fusionify_timestamp(datestring):
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


class JanusFusionTables(JanusSink):

    # https://developers.google.com/fusiontables/docs/v2/reference/
    def __init__(self, tableid, output):
        super(JanusFusionTables, self).__init__(output)
        self.tableid = tableid
        self.fusion = fusionclient.Fusion()
        self._q = []

    def autenticate(self):
        raise NotImplementedError # TODO: FIX

    def __format_post(self, post):
        # beat structure out of post data, which will vary from post to post
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

        kwargs = collections.OrderedDict({
            'ID': post['id'],
            'Dato': simplify_timestamp(post['created_time']),
            'Avsender': html.escape(name),
            '# Likes': likes,
            'Melding': html.escape(message.replace('\n', ' ')),
            'Link': link, 
            'Media': media,
            '# kommentarer': len(comments),
            'kommentarer': comments_html(comments),
            'Delinger': shares,
        })
        return kwargs

    def push(self, post)
        'Take a post and prepare it for upload'
        squeezed_post = self.__format_post(post)
        self._q.append(squeezed_post)
        if len(self._q) == FUSION_INSERT_QUEUE_MAX:
            self.insert_sql(self._q)
            self._q = []
        
    def insert_sql(self, rowdata):
        http_code, status = self.fusion.insertrows(self.fusiontable, rowdata)
        if http_code > 201:
            puts(colored.red(repr(status)), stream=self.output)
            puts('Error detected! Cooling down for a bit might work', stream=self.output)
            cont = input('=================== Continue? press y =================== ')
            if cont.strip().lower() != 'y': 
                cont = False
                break
        else:
            if 'kind' in status and status['kind'] == 'fusiontables#sqlresponse':
                luck = 'Rows added: {}.'.format(status['rows'])
            else: # dont know what the format is
                luck = repr(status)
            puts(colored.green(luck), stream=self.output)
