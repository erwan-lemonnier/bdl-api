import os
import logging
from bdl.tagger import KeywordList


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

class Category:

    def __init__(self, name, blocket_category=None, prices=None):
        self.prices = prices
        self.name = name
        self.whitelist = KeywordList('%s/%s-whitelist.html' % (DIR_LISTS, name))
        self.blacklist = KeywordList('%s/%s-blacklist.html' % (DIR_LISTS, name))
        self.blocket_category = blocket_category

    def get_matching_words(self, text, language):
        assert text is not None
        assert language

        tags = []
        text = text.lower()
        for w in self.whitelist.keywords:
            if w.match(text, language):
                log.debug("Item matches [%s] in %s whitelist" % (w, self.name))
                tags.append(w.word.lower())
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

SOLD = KeywordList('%s/sold.html' % DIR_LISTS)
BLACKLIST_ALL = KeywordList('%s/all-blacklist.html' % DIR_LISTS)
