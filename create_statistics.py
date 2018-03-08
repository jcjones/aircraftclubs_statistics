import math, statistics, pprint, json, argparse
import yaml
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import Counter, defaultdict, OrderedDict

config = {}

class RotationSchedule:
  def __init__(self):
    self.airports = []

  def configure(self, airports, period):
    self.airports = airports

    if 'months' in period:
      self.monthdelta = period['months']
    else:
      raise("Unknown period: " + json.dumps(period))

    if isinstance(period['reference_date'], str):
      self.reference = datetime.strptime(period['reference_date'], "%Y-%m-%d")
    else:
      self.reference = period['reference_date']

  def get_airport_on_date(self, aircraft, date):
    if len(self.airports) == 0:
      return None

    delta = relativedelta(date.date(), self.reference)
    delta_months = (delta.years * 12) + delta.months

    div, _ = divmod(delta_months, self.monthdelta)
    div += self.airports.index(aircraft['airport_at_reference'])

    _, cycle_count = divmod(div, len(self.airports))

    return self.airports[cycle_count]

def get_authenticated_session(url, username, password):
  s = requests.Session()
  r = s.post(url + '/functions/authentication/login.php',
        data={'username': config['aircraft_clubs']['username'],
              'password': config['aircraft_clubs']['password']})
  r.raise_for_status()
  login_result = r.json()['success']
  if login_result in ['incorrect', 'locked', 'expired']:
     raise("Could not login: " + login_result)
  return s

def get_events(session, url, rotation, aircraft_list, period_start, period_end):
  event_list = []

  for aircraft_name, aircraft in aircraft_list.items():
    r = session.get(url + '/functions/booking/getBookingsForCalendar.php',
          params={'start': period_start.timestamp(), 'end': period_end.timestamp(),
                  'a': aircraft['id']})
    r.raise_for_status()
    for event in r.json():
      start = datetime.strptime(event['start'], "%Y-%m-%d %H:%M:%S")
      end = datetime.strptime(event['end'], "%Y-%m-%d %H:%M:%S")
      is_maintenance = "maint" in event['icon']

      event_list.append({'aircraft_id': aircraft['id'], 'aircraft_name': aircraft_name,
                         'start': start, 'end': end, 'duration': end-start,
                         'weekend': is_weekend(start, end),
                         'airport': rotation.get_airport_on_date(aircraft, start),
                         'is_maintenance': is_maintenance })

  return sorted(event_list, key=lambda event: event['start'])

def is_weekend(start, end):
  if start.weekday() in [5, 6] or end.weekday() in [5,6]:
    return True
  if end - start < timedelta(days=1):
    return False
  if end - start > timedelta(days=6):
    return True

  x = start
  while x < end:
    if x.weekday() in [5, 6]:
      return True
    x += timedelta(days=1)
  return False


def gather_metadata(event_list):
  data = {}
  start = event_list[0]['start']
  end = event_list[len(event_list)-1]['end']
  return { 'start_date': start.strftime("%Y-%m-%d %H:%M:%S"),
           'end_date': end.strftime("%Y-%m-%d %H:%M:%S"),
           'length_days': (end - start).days,
           'num_events': len(event_list) }

def weekend_weekday_utilization(event_list):
  results={'weekend': Counter(), 'weekday': Counter()}
  for event in event_list:
    if event['weekend']:
      results['weekend']['total'] += 1
      results['weekend'][event['aircraft_name']] += 1
    else:
      results['weekday']['total'] += 1
      results['weekday'][event['aircraft_name']] += 1
  return results

def airport_utilization(event_list):
  results=Counter()
  for event in event_list:
    results[event['airport']] += 1
  return results

def length_histogram(event_list):
  results=Counter()
  for event in event_list:
    if event['is_maintenance']:
      continue

    length_hours = int(math.ceil(event['duration'].total_seconds() / (60*60)))
    results[length_hours] += 1

  return OrderedDict(sorted(results.items(), key=lambda t: t[0]))

def days_between_usage(event_list):
  deltas_by_name=defaultdict(list)
  last_event_by_name = {}

  for event in event_list:

    aircraft_name = event['aircraft_name']
    if aircraft_name not in last_event_by_name:
      last_event_by_name[aircraft_name] = event
    else:
      if event['start'].date() == last_event_by_name[aircraft_name]['end'].date():
        continue

      # Don't count either side of a maintenance activity
      if not event['is_maintenance'] and not last_event_by_name[aircraft_name]['is_maintenance']:
        delta_between = event['start'] - last_event_by_name[aircraft_name]['end']
        deltas_by_name[aircraft_name].append(abs(delta_between).total_seconds() / (60*60*24))

      last_event_by_name[aircraft_name] = event

  return deltas_by_name

def usage_by_weekday(event_list):
  day_of_week_by_name=defaultdict(Counter)
  for event in event_list:
    if event['is_maintenance']:
      continue

    x = event['start']
    while x < event['end']:
      day_of_week_by_name[event['aircraft_name']][x.strftime("%A")] += 1
      x += timedelta(days=1)

  return day_of_week_by_name

def aircraft_available_by_airport_and_weekday(event_list, aircraft, airports=["CHD", "DVT"]):
  aircraft_per_airport, mod = divmod(len(aircraft), len(airports))
  if mod != 0:
    raise "Uneven aircraft distribution!"

  # storage
  available_aircraft_by_airport_and_date = defaultdict(dict)
  # accumulators
  current_date = None
  aircraft_seen = []
  airport_usage = Counter()

  for event in event_list:
    if event['start'].date() != current_date:
      # Changing days, so let's record what we know (if we aren't at the beginning)
      if current_date != None:
        # Note how many aircraft were not seen
        for airport in airports:
          available_aircraft_by_airport_and_date[airport][current_date] = aircraft_per_airport - airport_usage[airport]

        # Initialize any gaps
        if event['start'].date() - current_date > timedelta(days=1):
          x = current_date
          while x < event['start'].date():
            for airport in airports:
              available_aircraft_by_airport_and_date[airport][x] = aircraft_per_airport
            x += timedelta(days=1)

      current_date = event['start'].date()
      airport_usage.clear()
      aircraft_seen.clear()

    if event['aircraft_name'] not in aircraft_seen:
      aircraft_seen.append(event['aircraft_name'])
      airport_usage[event['airport']] += 1

  airport_and_weekday_to_availability_list = {}
  for airport in airports:
    airport_and_weekday_to_availability_list[airport] = defaultdict(list)

  for airport, date_list in available_aircraft_by_airport_and_date.items():
    for date, count in date_list.items():
      airport_and_weekday_to_availability_list[airport][date.strftime("%A")].append(count)

  airport_and_dow_to_mean_available_aircraft = defaultdict(dict)
  for airport, date_list in airport_and_weekday_to_availability_list.items():
    for dow, counts in date_list.items():
      airport_and_dow_to_mean_available_aircraft[airport][dow] = statistics.mean(counts)

  return airport_and_dow_to_mean_available_aircraft

parser = argparse.ArgumentParser()
parser.add_argument("--json", help="output JSON to this file")
parser.add_argument("--weeks", help="Number of weeks to process", default=6, type=int)

args = parser.parse_args()

with open('config.yaml', 'r') as confFile:
  config = yaml.load(confFile)

s = get_authenticated_session(config['aircraft_clubs']['url'],
                              config['aircraft_clubs']['username'],
                              config['aircraft_clubs']['password'])

today = datetime.today()
time_horizon = timedelta(weeks=args.weeks)

rotation_schedule = RotationSchedule()
if 'rotation' in config['aircraft_clubs']:
  rotation_schedule.configure(config['aircraft_clubs']['rotation']['airports'],
                              config['aircraft_clubs']['rotation']['period'])

aircraft = config['aircraft_clubs']['aircraft']
events = get_events(s, config['aircraft_clubs']['url'], rotation_schedule,
                    aircraft, today - time_horizon, today)

dataset = {}
dataset['dataset_metadata'] = gather_metadata(events)
dataset['weekend_weekday_utilization'] = weekend_weekday_utilization(events)
dataset['airport_utilization'] = airport_utilization(events)
dataset['length_of_reservation_by_hours'] = length_histogram(events)
dataset['days_between_usage_by_aircraft'] = days_between_usage(events)
dataset['usage_by_weekday'] = usage_by_weekday(events)
dataset['aircraft_available_by_airport_and_weekday'] = aircraft_available_by_airport_and_weekday(events, aircraft)


pprint.pprint(dataset)

if args.json:
  with open(args.json, 'w') as outFile:
    json.dump(dataset, outFile)
