#!/usr/bin/env python3
import os
import sys
import json
import time
import logging
import requests
import click
import flask
import traceback
from pymacaron.config import get_config
from pymacaron.auth import generate_token
from pymacaron.utils import timenow, to_epoch
from pymacaron.crash import set_error_reporter
from pymacaron.crash import report_error
from pymacaron.crash import populate_error_report


log = logging.getLogger(__name__)


app = flask.Flask(__name__)


# Setup logging
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(message)s')
# handler.setFormatter(formatter)
log.addHandler(handler)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)


PATH_LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.append(PATH_LIBS)

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pym-config.yaml')
get_config(config_path)

from bdl.exceptions import bdl_error_reporter
from bdl.io.slack import do_slack


# If set, will override the default api|scraper.bazardelux.com target urls
HOST = None


def call_api(method, url, data=None, ignore_error=False):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer %s' % generate_token('scheduler', data={}, expire_in=86400)
    }
    log.info("Calling %s %s" % (method, url))
    if method == 'POST':
        r = requests.post(url, data=json.dumps(data), headers=headers)
    else:
        r = requests.get(url, headers=headers)
    log.info("=> Got: %s" % r.text)
    if str(r.status_code) != '200':
        raise Exception("Call to %s %s with data %s returned %s" % (method, url, data, r.text))
    return r.json()


#
# Lambda implementation
#

def scan_source(source=None, manual=False):
    source = source.upper()
    log.info("=> Lauching scan of source %s" % source)

    domain = HOST if HOST else 'https://api.bazardelux.com'

    # By default, scan 1 day back in time
    epoch_oldest = to_epoch(timenow()) - 86600

    # Find out epoch of last scan
    j = call_api('GET', '%s/v1/search/latest?source=%s' % (domain, source), ignore_error=True)
    if 'bdlitem' in j and 'epoch_published' in j['bdlitem']:
        epoch_oldest = j['bdlitem']['epoch_published']
        # If j is an error, just use the default epoch_oldest

    # And launch a scan
    date_oldest = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch_oldest))
    log.info("Scanning back to epoch %s (%s)" % (epoch_oldest, date_oldest))
    call_api(
        'POST',
        'https://crawler.bazardelux.com/v1/crawler/scan',
        {
            'source': source,
            'epoch_oldest': epoch_oldest,
        },
    )

    do_slack(
        "Scheduler: %slaunched scan of source %s back to %s" % ('manually ' if manual else '', source, date_oldest),
        channel=get_config().slack_scheduler_channel,
    )


def update_sitemap(source=None, manual=False):
    log.info("=> Lauching sitemap update")

    domain = HOST if HOST else 'https://api.bazardelux.com'

    call_api('GET', '%s/v1/bdl/sitemap/update' % domain)

    do_slack(
        "Scheduler: %supdated sitemap" % ('manually ' if manual else ''),
        channel=get_config().slack_scheduler_channel,
    )


def clean_source(source=None, manual=False):
    source = source.upper()
    log.info("=> Cleaning up oldest announces from %s" % source)
    # Count how many items are indexed from this source, and retrieve as many
    # of them so that all will be scanned within a week
    # Call v1/parse with the item's urls

    do_slack(
        "Scheduler: %slaunched cleanup of source %s" % ('manually ' if manual else '', source),
        channel=get_config().slack_scheduler_channel,
    )


#
# Generic wraper for running pymacaron code in a lambda
#

def generic_handler(f, event, manual=False):
    """Execute a method while wrapping it in a pymacaron context.
    Expects an event dict of the form:
    {
      source: <source>,  (optional)
      test: True|False,  (optional)
    }
    """

    with app.test_request_context(''):
        # Configure the error reporter and force pymacaron to report errors
        set_error_reporter(bdl_error_reporter)
        os.environ['DO_REPORT_ERROR'] = "1"

        try:
            # Is it a custom test action?
            if 'action' in event:
                if event['action'] == 'NOP':
                    log.info("Called in self-test mode. Doing nothing")
                elif event['action'] == 'FAIL':
                    raise Exception("Simulate an error")
                else:
                    raise Exception("Do not know how to handle action %s" % event['action'])
            else:
                # Just execute the callback
                event['manual'] = manual
                f(**event)

        except Exception as e:
            data = {}
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace = traceback.format_exception(exc_type, exc_value, exc_traceback, 30)
            data['trace'] = trace
            populate_error_report(data)
            report_error(
                title='%s CRASH: %s' % ('MANUAL' if manual else 'LAMBDA', f.__name__),
                data=data,
                caught=e,
                is_fatal=True,
            )

            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }


    return {
        'statusCode': 200,
        'body': json.dumps({'info': 'Executed %s' % f.__name__})
    }


#
# Handle execution from within a lambda function
#

def lambda_scan_source(event, context):
    return generic_handler(scan_source, event, manual=False)

def lambda_clean_source(event, context):
    return generic_handler(clean_source, event, manual=False)

def lambda_update_sitemap(event, context):
    return generic_handler(update_sitemap, event, manual=False)


#
# Handle command line execution
#

@click.command()
@click.option('--scan', required=False, metavar='SOURCE', help="Scan the given source", default=False)
@click.option('--clean', required=False, metavar='SOURCE', help="Remove sold announces from this source", default=False)
@click.option('--sitemap/--no-sitemap', required=False, metavar='', help="Update the bazardelux sitemap", default=False)
@click.option('--host', required=False, metavar='PROTO://HOST:PORT', help="Call this proto://host:port instead of the default bazardelux.com server", default=False)
def main(scan, clean, sitemap, host):
    """Scheduler for bazardelux.com, in charge of running crawlers at regular
    intervals, polling items to remove them when they are sold and updating the
    sitemaps every day.

    Can also be used to launch a single scan, clean or sitemap operation.

    Examples:

    tictac                      # Start the scheduler and keep it running #
    tictac --scan TRADERA       # Scan TRADERA                            #
    tictac --clean TRADERA      # Purge the oldest sold ads from TRADERA  #
    tictac --sitemap            # Update bazardelux's sitemap             #
    tictac --sitemap --host http://127.0.0.1:8080

    """

    # Configure the error reporter and force pymacaron to report errors
    set_error_reporter(bdl_error_reporter)
    os.environ['DO_REPORT_ERROR'] = "1"

    global HOST
    if host:
        HOST = host

    #
    # Check arguments and run single tasks
    #

    if scan or clean:
        if scan and clean:
            log.warn("You must provide only one of --scan or --clean")
            sys.exit(1)
        if scan:
            generic_handler(scan_source, {'source': scan}, manual=True)
            sys.exit(0)
        if clean:
            generic_handler(clean_source, {'source': clean}, manual=True)
            sys.exit(0)
    elif sitemap:
        generic_handler(update_sitemap, {}, manual=True)
        sys.exit(0)

    log.warn("No action specified")
    sys.exit(1)


if __name__ == "__main__":
    with app.test_request_context(''):
        main()
