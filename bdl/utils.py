import logging
import types
import re
from pymacaron.auth import generate_token
from html.parser import HTMLParser


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


htmlparser = HTMLParser()

def html_to_unicode(s):
    """Take an html-encoded string and return a unicode string"""
    return htmlparser.unescape(s)


def cleanup_string(s):
    s = s.lower()
    s = re.sub('<[^<]+?>', ' ', s)
    s = html_to_unicode(s)
    s = re.sub(r'[;,*_=+\!\'\"\#\?\´\´\\\/\^\(\)\&\@\|\[\]\{\}\%]', ' ', s)
    s = s.replace('\n', ' ').replace('\r', '')
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    return s
