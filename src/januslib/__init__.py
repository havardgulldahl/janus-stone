import os
import io
import json
import json

class JanusSource:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        # seed feed

    def authenticate(self):
        raise NotImplementedError

    def iterate(self):
        raise NotImplementedError

class JanusSink:
    def __init__(self, outputchannel):
        self.output = outputchannel # duck typed file object 
        # seed feed

    def authenticate(self):
        raise NotImplementedError

    def push(self, post):
        raise NotImplementedError

class JanusFileSink(JanusSink):
    
    def __init__(self, cachepath, output):
        super(JanusFileSink, self).__init__(output)
        self.cachepath = cachepath

    def push(self, post):
        if not os.path.exists(self.cachepath):
            os.makedirs(self.cachepath)
        with io.open('{}/{}.json'.format(self.cachepath, post['id']), 'wb') as f:
            f.write(json.dumps(post).encode())
