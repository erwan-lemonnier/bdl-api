import os
import logging
from flask import Flask
import dynadbobjectstore
from dynadbmutex import MutexBag, MutexAlreadyAcquiredException
from boto import dynamodb2
from pymacaron.utils import to_epoch, timenow
from pymacaron.config import get_config

log = logging.getLogger(__name__)

app = Flask(__name__)


#
# Called every time AWS does a ping()
#

def tictoc():
    """Called every time Amazon calls the /ping endpoint, hence every few seconds,
    which is a bit too often, so tictoc() delays by calling turn_the_wheel()
    every N tics

    """

    PATH = "/tmp/bdl-api-lastcheck"

    lastcheck = 0
    if os.path.exists(PATH):
        with open(PATH) as f:
            s = f.read()
            lastcheck = int(s)

    now = to_epoch(timenow())
    delta = now - lastcheck
    log.debug("TICTOC: Last check was %s seconds ago" % delta)

    # Check if we should scan sites every 10 min (600sec)
    if delta < 6:
        return

    log.info("TICTOC: Let's see what to scan...")
    with open(PATH, 'w') as f:
        f.write(str(now))

    turn_the_wheel()


#
# ObjectStore
#

conn = None

def get_conn():
    global conn
    if not conn:
        conf = get_config()
        log.info("Dynamodb setup against region:%s access_key_id:%s, aws_secret:%s***" % (conf.aws_region, conf.aws_access_key_id, conf.aws_secret_access_key[0:8]))
        conn = dynamodb2.connect_to_region(
            conf.aws_region,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key
        )

    return conn


class ObjectStore(dynadbobjectstore.ObjectStore):

    def __init__(self):
        super().__init__(get_conn(), 'scheduler')


ObjectStore().create_table()


#
# Business logic
#


def turn_the_wheel():
    """Periodically check if we should schedule some scans"""

    log.info("TURNING THE WHEEL")
    # TODO: proc.open() a script that scans what we want?

    store = ObjectStore()

    # Get a mutex
    bag = MutexBag(get_conn(), 'scheduler')
    try:
        # If multiple processes want to acquire the same string 'name', only one
        # will succeed, and all others get a MutexAlreadyAcquiredException.
        mutex = bag.acquire('scheduler')

        sources = store.get('sources')
        if type(sources) is str:
            sources = {}
        log.debug("sources are %s" % sources)
        sources = scan_sources(sources)
        store.put('sources', sources)

    except MutexAlreadyAcquiredException:
        # Too bad, someone else already acquired this mutex
        log.debug("Mutex is already locked by someone else")
        return

    except Exception as e:
        # Make sure to release the mutex, even if the shit hit the fan
        log.debug("Caught exception. Releasing mutex anyway. Exception was: %s" % str(e))
        mutex.release()
        raise e

    mutex.release()


def scan_sources(sources):
    """Take a dict of sources and returned the updated dict."""

    # 'sources' is a dict of dicts:
    #
    # {
    #   'source_name': {
    #     'last_scan': <epoch of last scan for that source>,
    #     'scan_period': <how long in seconds before 2 scans>,
    #   }
    # }
    #

    ALL_SOURCES = [
        'tradera',
    ]

    # First, make sure that all sources are initialized
    for name in ALL_SOURCES:
        if name not in sources:
            sources[name] = {}
        if 'last_check' not in sources[name]:
            sources[name]['last_check'] = 0
        if 'scan_period' not in sources[name]:
            sources[name]['scan_period'] = 600

    # Then check
    for source in sources:
        pass

    return sources
