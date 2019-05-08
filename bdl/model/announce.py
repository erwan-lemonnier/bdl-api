import logging
from bdl.utils import mixin


log = logging.getLogger(__name__)


def model_to_announce(o):
    """Take a bravado object and return an Announce"""
    mixin(o, Announce)


class Announce():
    pass
