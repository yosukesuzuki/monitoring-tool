# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START app]
import json
import logging
import os

import gspread
import requests
from flask import Flask, render_template
from lxml import etree
from oauth2client.service_account import ServiceAccountCredentials
from pyquery import PyQuery as pq
from requests.auth import HTTPBasicAuth
from requests_toolbelt.adapters import appengine

appengine.monkeypatch()

app = Flask(__name__)


@app.route('/')
def index():
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_file, 'r') as configFile:
        config_dict = json.loads(configFile.read())
    r = requests.get(config_dict['target_url'],
                     auth=HTTPBasicAuth(config_dict['client_id'], config_dict['client_secret']))
    parser = etree.XMLParser(recover=True)
    d = pq(etree.fromstring(r.text, parser))
    lists = [e.attrib['title'] for e in d("label.screen-name")]
    credential_file = os.path.join(os.path.dirname(__file__), 'credential.json')
    with open(credential_file, 'r') as dataFile:
        credential_dict = json.loads(dataFile.read())
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credential_dict,
                                                                   scopes=['https://spreadsheets.google.com/feeds'])
    doc_key = config_dict['doc_key']
    gs_client = gspread.authorize(credentials)
    gfile = gs_client.open_by_key(doc_key)
    worksheet = gfile.sheet1
    records = worksheet.get_all_values()
    return render_template('index.html', lists=lists, records=records)


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', 500

# [END app]