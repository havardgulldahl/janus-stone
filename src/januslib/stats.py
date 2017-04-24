import colorlog
import io
import json
import os.path
from datetime import datetime
import tempfile

from clint.textui import colored, puts, indent
from sortedcontainers import SortedDict # pip install sortedcontainers

logger = colorlog.getLogger('Janus.januslib.stats')
from . import JanusSink

class JanusStatsSink(JanusSink):
    
    def __init__(self, stat_type, output):
        super().__init__(output)
        self.stat_type = stat_type
        self.created_dates = SortedDict()
        self.counted = 0
        self.filter = None

    def __str__(self):
        'return pretty name'
        return '<#{} Stats({})>'.format(self.id, self.stat_type)

    def set_filter(self, cb):
        self.filter = cb
        
    def push(self, post):
        if self.filter is not None:
            if not self.filter(post): # run thru filter
                return
        if self.stat_type == 'date_count':
            post_date = post.datetime_created.date().isoformat()
            if not post_date in self.created_dates:
                self.created_dates[post_date] = 1
            else:
                self.created_dates[post_date] += 1
        self.counted += 1
        
    def finished(self):
        with tempfile.NamedTemporaryFile(suffix='.csv', prefix='janus_stats_{}'.format(self.stat_type), delete=False) as f:
            f.write('# Janus Stone stats {} created {}\r\n'.format(self.stat_type, datetime.now().isoformat()).encode())
            f.write('# Total count: {} ({}) \r\n'.format(self.counted, 'filter: {}'.format(self.filter) if self.filter is not None else 'unfiltered').encode())
            for dte, cnt in self.created_dates.items():
                f.write('{};{}\r\n'.format(dte, cnt).encode())
            puts('Finished processing {} posts. Here are the {} stats. Hope you are happy: {}'.format(self.counted, self.stat_type, f.name))

