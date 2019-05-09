import logging
from bdl.tagger import get_matching_tags
from bdl.categories import get_categories
from bdl.io.s3 import get_s3_conn
from bdl.utils import html_to_unicode


log = logging.getLogger(__name__)


#
# Blacklist/whitelist logic
#

LIST_CACHE = {}


def get_list(name):
    global LIST_CACHE
    if name not in LIST_CACHE:
        log.info("Fetching list %s from S3" % name)
        k = get_s3_conn().get_bucket('static.klue.it').get_key('crawler/' + name)
        s = k.get_contents_as_string().decode('utf-8')
        lst = [l.strip() for l in s.split('\n') if len(l.strip()) > 0]
        if name.endswith('.html'):
            # And convert to ascii to facilitate matching
            lst = [html_to_unicode(l).lower() for l in lst]
        elif name.endswith('.txt'):
            lst = [l.lower() for l in lst]
        else:
            raise Exception("WTF: white/blacklist %s is neither .txt not .hmtl" % name)
        LIST_CACHE[name] = lst

    return LIST_CACHE[name]


def empty_list_cache():
    global LIST_CACHE
    LIST_CACHE = {}


def match_list(text, listname):
    text = text.lower()
    for w in get_list(listname):
        if w in text:
            log.debug("Item matches [%s] in list %s" % (w, listname))
            return True
    return False


def get_matching_words(text, listname):
    tags = []
    text = text.lower()
    for w in get_list(listname):
        if w in text:
            log.debug("Item matches [%s] in list %s" % (w, listname))
            tags.append(w.lower())
    return tags


def set_item_tags(item, reset=False):
    """Update the item's tags with matching words and category from this whitelist"""
    item_tags = []

    if not reset:
        if hasattr(item, 'tags') and item.tags:
            item_tags = item.tags.split('|')
            item_tags = [i for i in item_tags if i]

    text = "%s %s" % (item.title, item.description)

    # Find all words that match this item
    for cat in get_categories():
        tags = get_matching_words(text, cat.whitelist)
        if len(tags) > 0:
            item_tags = item_tags + tags + [cat.name.upper()]

    # Find all tags/categories that match this item
    tags = get_matching_tags(text)
    if len(tags) > 0:
        item_tags = item_tags + tags

    if item.facebook_group_id:
        item_tags.append(str(item.facebook_group_id))

    item.tags = sorted(set(item_tags))

    log.info("Tagging item with %s" % item.tags)
