
import io
import json
import os.path
from datetime import datetime
import tempfile

from clint.textui import colored, puts, indent
from . import JanusSink

class JanusStatsSink(JanusSink):
    
    def __init__(self, stat_type, output):
        super().__init__(output)
        self.stat_type = stat_type
        self.created_dates = {}
        self.counted = -1

    def __str__(self):
        'return pretty name'
        return '<#{} Stats({})>'.format(self.id, self.stat_type)

    def push(self, post):
        post_date = post.datetime_created.date().isoformat()
        if not post_date in self.created_dates:
            self.created_dates[post_date] = 1
        else:
            self.created_dates[post_date] += 1
        self.counted += 1
        

    def finished(self):
        with tempfile.NamedTemporaryFile(suffix='.csv', prefix='janus_stats_{}'.format(self.stat_type), delete=False) as f:
            f.write('# Janus Stone stats {} created {}\r\n'.format(self.stat_type, datetime.now().isoformat()).encode())
            for dte, cnt in self.created_dates.items():
                #puts(colored.blue(dte) + ': ' + colored.magenta(cnt), self.output)
                f.write('{};{}\r\n'.format(dte, cnt).encode())
            puts('Finished processing {} posts. Here are the {} stats. Hope you are happy: {}'.format(self.counted, self.stat_type, f.name))

