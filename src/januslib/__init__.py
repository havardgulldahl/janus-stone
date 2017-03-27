import os
import io
import json
import uuid

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

class JanusFileSink(JanusSink):
    
    def __init__(self, cachepath, output):
        super().__init__(output)
        self.cachepath = cachepath

    def __str__(self):
        'return pretty name'
        return '<#{} File(->{})>'.format(self.id,self.cachepath)

    def push(self, post):
        if not os.path.exists(self.cachepath):
            os.makedirs(self.cachepath)
        with io.open('{}/{}.json'.format(self.cachepath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())

    def finished(self):
        pass

