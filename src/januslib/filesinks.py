
import colorlog
import io
import json
import os.path

from . import JanusSink

logger = colorlog.getLogger('Janus.januslib.filesinks')

class JanusFileSink(JanusSink):
    
    def __init__(self, cachepath, output):
        super().__init__(output)
        self.cachepath = cachepath

    def __str__(self):
        'return pretty name'
        return '>>>File({})'.format(self.id, self.cachepath)

    def push(self, post):
        if not os.path.exists(self.cachepath):
            os.makedirs(self.cachepath)
        with io.open('{}/{}.json'.format(self.cachepath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())

    def finished(self):
        pass

class JanusCSVSink(JanusSink):
    def __init__(self, filename, separator, output):
        super().__init__(output)
        self.filename = filename
        self.separator = ',' if separator is None else separator

    def __str__(self):
        'return pretty name'
        return '>>>CSVFile({})'.format(self.id, self.filename)

    def __format_post(self, post):
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

        fields = [
             post['id'],
             post['created_time'],
             name,
             likes,
             message.replace('\n', ' '),
             link, 
             media,
             len(comments),
             shares,
             permalink,
        ]
        return self.separator.join(fields)

    def push(self, post):
        dirn = os.path.dirname(self.filename)
        if not os.path.exists(dirn):
            os.makedirs(dirn)
        if not os.path.exists(self.filename):
            pass
        with io.open(self.filename, 'wb+') as f:
            f.write(self.__format_post(post))

    def finished(self):
        pass
    
