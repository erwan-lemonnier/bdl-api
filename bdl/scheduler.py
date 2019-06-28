import os
import logging
from flask import Flask
from pymacaron.utils import to_epoch, timenow

log = logging.getLogger(__name__)

app = Flask(__name__)




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
    if delta < 600:
        return

    log.info("TICTOC: Let's see what to scan...")
    with open(PATH, 'w') as f:
        f.write(str(now))

    turn_the_wheel()


def turn_the_wheel():
    """Periodically check if we should schedule some scans"""

    log.info("TURNING THE WHEEL")
    # TODO: proc.open() a script that scans what we want?
