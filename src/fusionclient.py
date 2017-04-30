#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import httplib2
import urllib.parse
import sys,os
import logging
import colorlog
import json
from pprint import pprint
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from apiclient.discovery import build
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow

logger = colorlog.getLogger('Janus.fusionclient')

# For this example, the client id and client secret are command-line arguments.
client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")

# The scope URL for read/write access to a user's calendar data
scope = 'https://www.googleapis.com/auth/fusiontables'

# Create a flow object. This object holds the client_id, client_secret, and
# scope. It assists with OAuth 2.0 steps to get user authorization and
# credentials.
flow = OAuth2WebServerFlow(client_id, client_secret, scope)

class Fusion:

  def __init__(self):
    # Create a Storage object. This object holds the credentials that your
    # application needs to authorize access to the user's data. The name of the
    # credentials file is provided. If the file does not exist, it is
    # created. This object can only hold credentials for a single user, so
    # as-written, this script can only handle a single user.
    storage = Storage('credentials.dat')

    # The get() function returns the credentials for the Storage object. If no
    # credentials were found, None is returned.
    credentials = storage.get()

    # If no credentials are found or the credentials are invalid due to
    # expiration, new credentials need to be obtained from the authorization
    # server. The oauth2client.tools.run_flow() function attempts to open an
    # authorization server page in your default web browser. The server
    # asks the user to grant your application access to the user's data.
    # If the user grants access, the run_flow() function returns new credentials.
    # The new credentials are also stored in the supplied Storage object,
    # which updates the credentials.dat file.
    if credentials is None or credentials.invalid:
        credentials = tools.run_flow(flow, storage, tools.argparser.parse_args())

    # Create an httplib2.Http object to handle our HTTP requests, and authorize it
    # using the credentials.authorize() function.
    http = httplib2.Http()
    http = credentials.authorize(http)

    # The apiclient.discovery.build() function returns an instance of an API service
    # object can be used to make API calls. The object is constructed with
    # methods specific to the calendar API. The arguments provided are:
    #   name of the API ('calendar')
    #   version of the API you are using ('v3')
    #   authorized httplib2.Http() object that can be used for API calls
    self.service = build('fusiontables', 'v2', http=http)
    self.http = self.service._http

  def run(self, request):
        try:
            response = request.execute()
            # Accessing the response like a dict object with an 'items' key
            # returns a list of item objects (events).
            #logging.debug(response)
            return response
            # Get the next request object by passing the previous request object to
            # the list_next method.
            #request = service.events().list_next(request, response)

        except AccessTokenRefreshError:
            # The AccessTokenRefreshError exception is raised if the credentials
            # have been revoked by the user or they have expired.
            print ('The credentials have been revoked or expired, please re-run'
                'the application to re-authorize')

  def sql(self, sqlstring):
        url = '{}query'.format(self.service._baseUrl)
        logger.debug('sending request to %r', url)
        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        response, content = self.http.request(url, 
                                              'POST', 
                                              headers=headers, 
                                              body=urllib.parse.urlencode({'sql':sqlstring}))
        #logger.debug('.sql got %r response: %r', response, content)
        try:
            cont = json.loads(content.decode())
        except:
            cont = content
        return (int(response['status'], 10), cont)

  def insertrows(self, tableid, sqlvals):
        'sqlvals is a list of OrderedDicts' 
        kyes = sqlvals[0].keys()
        colnames = [ swrap(k) for k in kyes ]
        valblock = []
        sql = []
        for vals in sqlvals:
            sql.append("INSERT INTO {} ({}) VALUES ({})".format(tableid, 
                                                                ', '.join(colnames), 
                                                                ', '.join( [ swrap(vals[v]) for v in kyes ] )
                                                                )
                                                                )
        logger.debug("generated INSERT sql: %r", sql)
        return self.sql('; '.join(sql)) #returning tuple

  def select(self, what, tableid, where=None):
        'Run a SQL SELECT query to get `what` (a list of columns or a function) on `tableid`, optionally filtered by `where`, and return response'
        if isinstance(what, list):
            q = 'ROWID,'+','.join(map(swrap, what))
        else:
            q = what
        sqlstring = "SELECT {} FROM {} ".format(q, tableid)
        if isinstance(where, list) and len(where) > 0: # where is a list of conditionals
            sqlstring = sqlstring + " WHERE {}".format(' AND '.join(where))
        logger.debug("generated SELECT sql: %r", sqlstring)
        req = self.service.query().sqlGet(sql=sqlstring)
        return self.run(req)

def swrap(a):
    return ''' '{}' '''.format(a)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    f = Fusion()
    #req = f.service.table().list()
    #f.run(req)


