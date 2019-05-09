import logging


log = logging.getLogger(__name__)


class PriceRange:

    def __init__(self, currency, price_min, price_max):
        self.currency = currency.upper()
        self.price_min = price_min
        self.price_max = price_max

class Category:

    def __init__(self, name, blocket_category=None, prices=None):
        self.prices = prices
        self.name = name
        self.whitelist = '%s-whitelist.html' % name
        self.blacklist = '%s-blacklist.html' % name
        self.blocket_category = blocket_category


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
