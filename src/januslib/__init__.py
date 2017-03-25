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

    def push(self):
        raise NotImplementedError
