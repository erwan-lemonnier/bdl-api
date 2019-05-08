import logging
import types
from pymacaron.auth import generate_token


log = logging.getLogger(__name__)


def mixin(o, *args):
    """Monkey patch all methods from class cls into instance o"""
    # See: https://filippo.io/instance-monkey-patching-in-python/

    for cls in args:
        methods = [m for m in dir(cls) if not m.startswith('__')]
        for m in methods:
            setattr(o, m, types.MethodType(getattr(cls, m), o))


def gen_jwt_token(type='www', scrapper=None, language='en'):
    assert type in ('www', 'scrapper', 'test')

    data = {
        'type': type,
        'language': language,
    }

    if scrapper:
        data['scrapper'] = scrapper

    user_id = 'bdl-api'

    return generate_token(
        user_id,
        data=data,
        # Expire in 3 days
        expire_in=259200,
    )
