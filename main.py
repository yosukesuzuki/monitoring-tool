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
import sendgrid
import validators
from flask import Flask, render_template
from google.appengine.ext import deferred
from lxml import etree
from models import States
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
    elements = [e.attrib['title'] for e in d("label.screen-name")]
    credential_file = os.path.join(os.path.dirname(__file__), 'credential.json')
    with open(credential_file, 'r') as dataFile:
        credential_dict = json.loads(dataFile.read())
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credential_dict,
                                                                   scopes=['https://spreadsheets.google.com/feeds'])
    gs_client = gspread.authorize(credentials)
    gfile = gs_client.open_by_key(config_dict['doc_key'])
    worksheet = gfile.sheet1
    records = worksheet.get_all_values()
    results = []
    for i, r in enumerate(records):
        if i > 0:
            working = False
            in_use = False
            if r[3] != '':
                in_use = True
            for e in elements:
                if r[0] in e:
                    working = True
            result = {'id': r[0], 'working': working, 'in_use': in_use, 'notifications': r[3], 'location': r[2]}
            results.append(result)
            if in_use is False:
                logging.info(u'{} is not in use, skipped'.format(r[0]))
                continue
            state = States.get_by_id(r[0])
            if working is False:
                if state is None or state.working is True:
                    logging.info(u'{}: looks bad, notification task will be sent to que'.format(r[0]))
                    States(id=r[0], working=False).put()
                    deferred.defer(send_notification, result)
                else:
                    logging.info(u'{}: looks bad, same status as before'.format(r[0]))
            else:
                logging.info(u'{}: looks good'.format(r[0]))
                States(id=r[0], working=True).put()
    return render_template('index.html', results=results)


def send_notification(result):
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_file, 'r') as configFile:
        config_dict = json.loads(configFile.read())
    notifications = result['notifications'].split(',')
    notification_message = u'{} is not working now! location is {}'.format(result['id'], result['location'])
    for noti in notifications:
        if noti.startswith('https://hooks.slack.com'):
            post_data = json.dumps({
                'text': notification_message,
                'channel': config_dict['slack_channel'], 'username': config_dict['slack_user'],
                'icon_emoji': config_dict['slack_icon']})
            r = requests.post(noti, data=post_data)
            if r.status_code != 200:
                logging.error(u'failed: {}'.format(r.text))
        if validators.email(noti):
            logging.info(u'send email to: {}'.format(noti))
            send_notification_by_sendgrid(noti, notification_message)


def send_notification_by_sendgrid(mail_to, notification_message):
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_file, 'r') as configFile:
        config_dict = json.loads(configFile.read())
    sg = sendgrid.SendGridAPIClient(apikey=config_dict['sendgrid_api_key'])
    data = {
        "personalizations": [
            {
                "to": [
                    {
                        "email": mail_to
                    }
                ],
                "subject": notification_message
            }
        ],
        "from": {
            "email": config_dict['sendgrid_from_email'],
            "name": config_dict['sendgrid_from_email_name']
        },
        "content": [
            {
                "type": "text/plain",
                "value": notification_message
            }
        ],
        "template_id": config_dict['sendgrid_template_id']
    }
    response = sg.client.mail.send.post(request_body=data)
    if response.status_code != 202:
        logging.error(response.body)


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', 500

# [END app]
