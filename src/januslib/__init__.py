import os
import io
import json
import uuid
import dateutil
from pathlib import Path

class JanusSource:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        # seed feed

    def __str__(self):
        'return pretty name'
        return '<{}>'.format(self.__class__.__name__)

    def authenticate(self):
        raise NotImplementedError

    def iterate(self):
        raise NotImplementedError

class JanusSink:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        self.id = str(uuid.uuid4())[:4]
        # seed feed

    def __str__(self):
        'return pretty name'
        return '<#{} {}>'.format(self.id, self.__class__.__name__)

    def authenticate(self):
        raise NotImplementedError

    def push(self, post):
        raise NotImplementedError

    def finished(self):
        raise NotImplementedError

class JanusPost:
    'A Facebook post with an easy interface'

    def __init__(self, json_or_path):
        if isinstance(json_or_path, Path):
            self.path = json_or_path
            with json_or_path.open() as f:
                self.post = json.loads(f.read())
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
