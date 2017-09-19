import os

import httplib2
import yaml
from apiclient import discovery
from flask import Flask
from flask import request, render_template, session, redirect
from google.appengine.api import users
from oauth2client.appengine import AppAssertionCredentials
from oauth2client.contrib.flask_util import UserOAuth2

import settings
from myapp.calendar_sync import *

app = Flask(__name__)

app.config['GOOGLE_OAUTH2_CLIENT_ID'] = settings.CLIENT_ID
app.config['GOOGLE_OAUTH2_CLIENT_SECRET'] = settings.CLIENT_SECRET

app.secret_key = settings.SECRET_KEY

oauth2 = UserOAuth2(app, scopes=settings.SCOPE)

credentials = AppAssertionCredentials('https://www.googleapis.com/auth/calendar.readonly')


def load_calendar_configs():
    with open("bank_holiday_calendars.yaml", 'r') as stream:
        return yaml.load(stream)['calendars']


@app.route('/', methods=['GET'])
def index():
    http = credentials.authorize(httplib2.Http())
    calendar_service = discovery.build('calendar', 'v3', http=http)

    compared_calendars = collections.OrderedDict()
    for config in load_calendar_configs():
        compared_calendars[config['name']] = compare_calendars(calendar_service, config)

    return render_template('index.html',
                           logout_url=users.create_logout_url('/'),
                           email=users.get_current_user().email(),
                           calendars=compared_calendars)


@app.route('/sync', methods=['GET'])
@oauth2.required
def sync():
    if oauth2.credentials.access_token_expired:
        logging.info("Refreshing token")
        session.clear()
        return redirect(oauth2.authorize_url(request.url))

    calendar_service = discovery.build('calendar', 'v3', http=oauth2.http(timeout=20))
    counter = 0
    for config in load_calendar_configs():
        counter += sync_calendars(calendar_service, config)

    compared_calendars = collections.OrderedDict()
    for config in load_calendar_configs():
        compared_calendars[config['name']] = compare_calendars(calendar_service, config)

    return render_template('index.html',
                           logout_url=users.create_logout_url('/'),
                           email=users.get_current_user().email(),
                           calendars=compared_calendars,
                           sync_count=counter)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error404.html'), 404


@app.errorhandler(500)
def application_error(e):
    return render_template('error500.html',
                           error_message='{}'.format(e),
                           request_id=os.environ.get('REQUEST_LOG_ID')), 500


@app.after_request
def apply_common_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=10886400; includeSubDomains; preload"
    return response
