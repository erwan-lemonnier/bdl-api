import os
import logging
from bdl.utils import html_to_unicode
from bdl.tagger import Keyword


log = logging.getLogger(__name__)


class PriceRange:

    def __init__(self, currency, price_min, price_max):
        self.currency = currency.upper()
        self.price_min = price_min
        self.price_max = price_max


#
# Blacklist/whitelist logic
#

DIR_LISTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'etc')

class KeywordList:

    def __init__(self, filename):
        log.info("Loading list %s" % filename)
        s = open(DIR_LISTS + '/' + filename).read()
        lst = [l.strip() for l in s.split('\n') if len(l.strip()) > 0]
        if filename.endswith('.html'):
            # And convert to ascii to facilitate matching
            lst = [html_to_unicode(l).lower() for l in lst]
        elif filename.endswith('.txt'):
            lst = [l.lower() for l in lst]
        else:
            raise Exception("WTF: white/blacklist %s is neither .txt not .hmtl" % filename)

        self.keywords = [Keyword(l) for l in lst]
        self.filename = filename

    def match(self, text, language):
        assert language
        # log.debug("Matching [%s]/[%s] against %s" % (language, text, self))
        text = text.lower()
        for w in self.keywords:
            if w.match(text, language):
                log.debug("Item matches [%s] in list %s" % (w, self.filename))
                return True
        return False

    def __str__(self):
        return "<KeywordList '%s': %s>" % (
            self.filename,
            ' '.join([str(w) for w in self.keywords]),
        )

class Category:

    def __init__(self, name, blocket_category=None, prices=None):
        self.prices = prices
        self.name = name
        self.whitelist = KeywordList('%s-whitelist.html' % name)
        self.blacklist = KeywordList('%s-blacklist.html' % name)
        self.blocket_category = blocket_category

    def get_matching_words(self, text, language):
        assert text is not None
        assert language

        tags = []
        text = text.lower()
        for w in self.whitelist:
            if w in text:
                log.debug("Item matches [%s] in %s whitelist" % (w, self.name))
                tags.append(w.lower())
        return tags


CATEGORIES = [
    Category(
        'mode',
        blocket_category=4000,
        prices=[
            PriceRange('SEK', 699, 50000)
        ],
    ),
    Category(
        'design',
        blocket_category=2000,
        prices=[
            PriceRange('SEK', 800, 50000)
        ],
    ),
    Category(
        'antique',
        blocket_category=2000,
        prices=[
            PriceRange('SEK', 800, 50000)
        ],
    ),
    Category(
        'art',
        blocket_category=2000,
        prices=[
            PriceRange('SEK', 800, 50000)
        ],
    )

]

def get_categories():
    return CATEGORIES

SOLD = KeywordList('sold.html')
BLACKLIST_ALL = KeywordList('all-blacklist.html')
