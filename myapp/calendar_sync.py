import collections
import datetime
import logging
import urllib


def get_events(calendar_service, config):
    fields = 'items(end,start,summary,description,htmlLink)'
    time_min = datetime.date.today().isoformat()
    time_max = (datetime.date.today() + datetime.timedelta(18 * 30)).isoformat()
    logging.info("Syncing events between %s and %s" % (time_min, time_max))
    source_events = calendar_service.events().list(
            calendarId=config['source'],
            timeMin=time_min + "T00:00:00-00:00",
            timeMax=time_max + "T00:00:00-00:00",
            fields=fields,
            maxResults=300,
            singleEvents=True,
            orderBy='startTime').execute()
    target_events = calendar_service.events().list(
            calendarId=config['target'],
            timeMin=time_min + "T00:00:00-00:00",
            timeMax=time_max + "T00:00:00-00:00",
            fields=fields,
            maxResults=300,
            singleEvents=True,
            orderBy='startTime').execute()
    return source_events.get('items'), target_events.get('items')


def create_event(calendar_service, calendar_id, start, end, summary, description):
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'date': start,
        },
        'end': {
            'date': end,
        },
        'guestsCanInviteOthers' : False,
        'visibility': 'public',
        'reminders': {
            'useDefault': False
        }
    }

    return calendar_service.events().insert(calendarId=calendar_id, body=event)


def merge_calendars(source_events, target_events, config):
    date_dict = {}

    for event in source_events:
        key = "%s_%s: %s" % (event['start']['date'], config['name'], event['summary'])

        if key not in date_dict:
            date_dict[key] = {}
            date_dict[key]['class'] = ''
            date_dict[key]['summary'] = event['summary']
            if 'description' in event:
                date_dict[key]['description'] = event['description']
            date_dict[key]['date'] = event['start']['date']

        date_dict[key]['source_event'] = event

    for event in target_events:
        key = "%s_%s" % (event['start']['date'], event['summary'])

        if key not in date_dict:
            date_dict[key] = {}
            date_dict[key]['class'] = ''
            date_dict[key]['summary'] = event['summary']
            if 'description' in event:
                date_dict[key]['description'] = event['description']
            date_dict[key]['date'] = event['start']['date']

        date_dict[key]['target_event'] = event

    for key, value in date_dict.iteritems():
        if ('source_event' not in value) or ('target_event' in value and value['summary'] in config['ignore_events']):
            value['class'] = 'info'
            value['glyphicon_tooltip'] = 'Event manually added to %s calendar' % config['name']
            value['glyphicon'] = 'glyphicon-pencil'
        elif 'target_event' not in value and value['summary'] not in config['ignore_events']:
            value['class'] = 'warning'
            value['glyphicon_tooltip'] = 'Event need synchronisation'
            value['glyphicon'] = 'glyphicon-remove'
        elif 'target_event' in value:
            value['class'] = 'success'
            value['glyphicon_tooltip'] = 'Event copied'
            value['glyphicon'] = 'glyphicon-ok'
        else:
            value['glyphicon_tooltip'] = 'Event ignored'
            value['glyphicon'] = 'glyphicon-ban-circle'

    return collections.OrderedDict(sorted(date_dict.items()))


def compare_calendars(calendar_service, config):
    source_summary = calendar_service.calendars().get(calendarId=config['source']).execute()['summary']
    target_summary = calendar_service.calendars().get(calendarId=config['target']).execute()['summary']
    logging.info("Comparing %s calendar: '%s' (%s) with '%s' (%s)" % (config['name'], source_summary, config['source'], target_summary, config['target']))

    events = get_events(calendar_service, config)

    source_events = [e for e in events[0] if 'date' in e['start'] and 'date' in e['end']]
    target_events = [e for e in events[1] if 'date' in e['start'] and 'date' in e['end']]

    country_dict = {
        'events': merge_calendars(source_events, target_events, config),
        'source_link': "https://calendar.google.com/calendar/embed?src=%s" % urllib.quote(config['source']),
        'target_link': "https://calendar.google.com/calendar/embed?src=%s" % urllib.quote(config['target'])
    }

    return country_dict


def sync_calendars(calendar_service, config):
    source_summary = calendar_service.calendars().get(calendarId=config['source']).execute()['summary']
    target_summary = calendar_service.calendars().get(calendarId=config['target']).execute()['summary']
    logging.info("Synchronising %s calendar: '%s' (%s) with '%s' (%s)" % (config['name'], source_summary, config['source'], target_summary, config['target']))

    events = get_events(calendar_service, config)

    # let's filter out events with datetime or ignored summary before set comparison
    source_events = [e for e in events[0] if 'date' in e['start'] and 'date' in e['end'] and e['summary'] not in config['ignore_events']]
    target_events = [e for e in events[1] if 'date' in e['start'] and 'date' in e['end']]

    logging.info("Ignoring %d source and %d target events" % (len(events[0]) - len(source_events), len(events[1]) - len(target_events)))

    source_set = set([(e['start']['date'], e['end']['date'], "%s: %s" % (config['name'], e['summary']), e['description'] if 'description' in e else "") for e in source_events])
    target_set = set([(e['start']['date'], e['end']['date'], e['summary'], e['description'] if 'description' in e else "") for e in target_events])

    new_events = source_set - target_set
    logging.info("source(%d) - target(%d) = %d new events" % (len(source_set), len(target_set), len(new_events)))
    counter = 0
    for new_event in new_events:
        logging.debug("Creating %s in '%s' calendar" % (str(new_event), target_summary))
        create_event(calendar_service, config['target'], start=new_event[0], end=new_event[1], summary=new_event[2], description=new_event[3]).execute()
        counter += 1
    return counter
