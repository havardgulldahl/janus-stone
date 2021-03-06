import logging
import colorlog
import os
import io
import json
import uuid
import dateutil
from pathlib import Path

logger = colorlog.getLogger('Janus.januslib')

class JanusException(Exception):
    pass

class JanusSource:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        self.since = None
        self.until = None
        self.filter = None
        self.id = str(uuid.uuid4())[:4]
        # seed feed

    def __str__(self):
        'return pretty name'
        return '<{}>'.format(self.__class__.__name__)

    def _slugify(self, s, maxlen=20):
        'convenience method to truncate - slugify - a string'
        if len(s) <= maxlen: return s
        return '{}..{}'.format(s[:9], s[-9:])

    def __iter__(self):
        raise NotImplementedError

    def authenticate(self):
        raise NotImplementedError

    def set_since(self, dtobj):
        self.since = dtobj # datetime.datetime

    def set_until(self, dtobj):
        self.until = dtobj # datetime.datetime

    def set_filter(self, filterstring):
        'Each source will use this to filter results server side. The format is source dependant'
        self.filter = filterstring 

class JanusSink:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        self.id = str(uuid.uuid4())[:4]
        # seed feed

    def __str__(self):
        'return pretty name'
        return '<#{} {}>'.format(self.id, self.__class__.__name__)

    def _slugify(self, s, maxlen=20):
        'convenience method to truncate - slugify - a string'
        if len(s) <= maxlen: return s
        return '{}..{}'.format(s[:9], s[-9:])

    def authenticate(self):
        raise NotImplementedError

    def push(self, post):
        raise NotImplementedError

    def finished(self):
        raise NotImplementedError

class JanusPost:
    'A Janus post with a standard interface'

    @property
    def id(self):
        raise NotImplementedError
                    
    @property
    def datetime_created(self):
        '''Return datetetime.datetime '''
        raise NotImplementedError

