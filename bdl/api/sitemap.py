import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import requests
import re
import xml.etree.ElementTree as ET
from boto.s3.key import Key
from unidecode import unidecode
from pymacaron.utils import timenow
from pymacaron_core.swagger.apipool import ApiPool
from bdl.utils import html_to_unicode
from bdl.io.s3 import get_s3_conn
from bdl.api.search import doc_to_item
from bdl.db.elasticsearch import get_all_docs


log = logging.getLogger(__name__)


#
# Utils for generating sitemaps
#

def compile_sitemap(urls):

    if len(urls) == 0:
        return ''

    log.info("Generating sitemap with %s urls" % len(urls))

    elems = ''

    for url in urls:
        if type(url) is dict:

            if 'priority' not in url:
                url['priority'] = '0.8'

            s = (
                '  <url>\n'
                '    <loc>' + url['url'] + '</loc>\n'
                '    <priority>' + url['priority'] + '</priority>\n'
            )

            if 'lastmod' in url:
                s = s + '    <lastmod>' + url['lastmod'] + '</lastmod>\n'

            if 'changefreq' in url:
                s = s + '    <changefreq>' + url['changefreq'] + '</changefreq>\n'

            for l in ('en', 'sv'):
                if l in list(url.keys()):
                    log.info("hreflang for %s is %s" % (l, url[l]))
                    s = s + '    <xhtml:link rel="alternate" hreflang="' + l + '" href="' + url[l] + '" />\n'

            s = s + '  </url>\n'

        else:
            s = (
                '  <url>\n'
                '    <loc>' + url + '</loc>\n'
                '    <priority>0.8</priority>\n'
                '  </url>\n'
            )

        elems = elems + s

    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        elems,
        '</urlset>',
    ])


def compile_sitemap_index(urls):

    log.info("Generating a sitemap index with %s urls" % len(urls))

    elems = ''

    for url in urls:
        if type(url) is dict:
            s = (
                '  <sitemap>\n'
                '    <loc>' + url['url'] + '</loc>\n'
            )
            if 'lastmod' in url:
                s = s + '    <lastmod>' + url['lastmod'] + '</lastmod>\n'
            s = s + '  </sitemap>\n'

        else:
            s = (
                '  <sitemap>\n'
                '    <loc>' + url + '</loc>\n'
                '  </sitemap>\n'
            )

        elems = elems + s

    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        elems,
        '</sitemapindex>',
    ])


#
# Generating monthly sitemaps
#

def set_item_url(item):

    # NOTE: make sure to keep in synch with the same dict in bdl-com/www/translations.json
    URL_FORSALE_LABEL = {
        "en": "forsale",
        "sv": "tillsalu",
        "fr": "avendre",
    }

    s = unidecode(html_to_unicode(item.bdlitem.title))
    s = re.sub('[^0-9a-zA-Z]+', '-', s)
    s = re.sub('[-]+', '-', s)
    s = s.strip('-')
    s = '%s_%s_%s__%s' % (s, item.bdlitem.price, item.bdlitem.currency, item.item_id)
    language = item.bdlitem.language
    forsale = URL_FORSALE_LABEL.get(language) if language in URL_FORSALE_LABEL else URL_FORSALE_LABEL['en']
    item.url = 'https://bazardelux.com/%s/%s/%s' % (language, forsale, s)


def get_items_forsale_for_period(year, month):

    log.info("About to list all items under period %s-%s" % (year, month))

    for create_date in get_dates_in_month(year, month):

        log.info("Fetching items published on %s" % create_date)

        index_name = 'bdlitems-live'
        doc_type = 'BDL_ITEM'
        batch_size = 100
        esquery = {
            "size": batch_size,
            "query": {
                "match" : {
                    "date_created" : create_date
                }
            }
        }

        for doc in get_all_docs(esquery, index_name, doc_type, batch_size):
            i = doc_to_item(doc)
            set_item_url(i)
            yield i


def generate_sitemap_announces(year, month):
    """Generate the endprice sitemap for the given year-month
    period and upload it to S3"""

    # Name of that partial sitemap
    smap_name = 'sitemap-bazardelux-%04d-%02d.xml' % (year, month)

    # We use a dict to filter out duplicates
    urls = {}

    def add_url(url, date_created):
        # Add one url to the the urls dict
        log.debug("Adding (%s) (%s)" % (date_created, url))
        urls[url] = {
            'url': url,
            'lastmod': str(date_created)[0:10],
            'priority': '0.8',
        }

    # A problem we have is that from day to day, as the sitemap gets
    # recompiled, announces that have been sold will have been removed from the
    # ES index and therefore disappear from the sitemap. We could scan the
    # dynamodb archive, but that would be awfully slow. So instead, we keep all
    # urls indexed so far that month and only add to that list. That means
    # we'll loose a few announces: those that got added, then sold the same
    # day. But it's okay.

    # First, fetch the sitemap for this year and month, if it exists, and load it into urls
    smap = get_sitemap_urls(smap_name)
    if smap:
        # Extract all urls from that sitemap
        log.debug("Loading: %s" % smap[0:500])
        root = ET.fromstring(smap)
        for url_data in list(root):
            url, date = None, None
            for e in list(url_data):
                if str(e.tag).endswith('loc'):
                    # It's the url
                    url = e.text
                elif str(e.tag).endswith('lastmod'):
                    # It's the date updated
                    date = e.text
            if url:
                add_url(url, date)

        log.info("Loaded %s announces from current sitemap" % len(urls))

    # Now add all announces still in the ES index
    for item in get_items_forsale_for_period(year, month):
        log.info("Got item: %s" % item)
        if not item:
            continue

        if len(urls) > 50000:
            # A sitemap may not contain more than 50000 entries...
            break

        add_url(item.url, item.date_created)

    urls = list(urls.keys())

    log.info("Listed %s announces for period %04d-%02d" % (len(urls), year, month))

    smap = compile_sitemap(urls)

    upload_sitemap(smap, smap_name)


#
# Utils
#

def upload_sitemap(smap, key_name):

    if len(smap) == 0:
        log.info("NOT uploading sitemap %s: it's empty..." % (key_name))
        return

    log.info("Uploading sitemap %s" % (key_name))

    bucket = get_s3_conn().get_bucket('static.bazardelux.com')

    k = Key(bucket)
    k.key = key_name
    k.set_metadata('Content-Type', 'application/xml')
    k.set_contents_from_string(smap)
    k.set_acl('public-read')


def get_sitemap_urls(key_name):
    bucket = get_s3_conn().get_bucket('static.bazardelux.com')
    k = bucket.get_key(key_name)
    if not k:
        return ''
    return k.get_contents_as_string()


def ping_search_engines():
    """Re-register the new sitemaps on main search engines"""
    server_url = 'https://bazardelux.com'
    url = '%s/sitemap.xml' % server_url
    url = urllib.parse.quote_plus(url)
    ping_urls = [
        'https://www.google.com/webmasters/sitemaps/ping?sitemap=' + url,
        'http://www.bing.com/webmaster/ping.aspx?siteMap=' + url,
        'http://pingsitemap.com/?action=submit&url=' + url,
    ]
    for ping_url in ping_urls:
        log.info("Submitting %s" % ping_url)
        try:
            r = requests.get(ping_url)
            if r.status_code != 200:
                raise Exception("Failed to submit new sitemap to %s" % ping_url)
        except Exception as e:
            raise Exception("Failed to submit new sitemap to %s because caught %s" % (ping_url, str(e)))


def get_dates_in_month(year, month):

    day_one_str = '%04d-%02d-01' % (year, month)
    day_one = datetime.strptime(day_one_str, "%Y-%m-%d")
    dates = [day_one_str]

    for delta in range(1, 31):
        d = day_one + timedelta(days=delta)
        d_str = d.strftime("%Y-%m-%d")
        if d_str.startswith('%04d-%02d' % (year, month)):
            dates.append(d_str)

    return dates

#
# API endpoint
#

STATIC_URLS = [
    'en', 'sv', 'fr',
    'en/about', 'sv/about', 'fr/about',
    'en/faq', 'sv/faq', 'fr/faq',
]

def generate_sitemap_static_pages():
    urls = []
    for url in STATIC_URLS:
        urls.append({
            'url': 'https://bazardelux.com/%s' % url,
            'priority': '1.0',
        })
    smap = compile_sitemap(urls)
    smap_name = 'sitemap-bazardelux-pages.xml'
    upload_sitemap(smap, smap_name)


def do_generate_sitemap():
    """Update the sitemap and regenerate parts of it that may have changed"""

    # Generate sitemap of static pages
    generate_sitemap_static_pages()

    # Regenerate sitemap for the current month
    now = timenow()
    generate_sitemap_announces(now.year, now.month)

    # List all sitemaps for this site
    log.info("Listing all sitemaps in static.bazardelux.com")
    bucket = get_s3_conn().get_bucket('static.bazardelux.com')
    urls = []
    for k in bucket.list():
        if k.name.startswith("sitemap-bazardelux"):
            urls.append('https:' + k.generate_url(expires_in=0, query_auth=False))

    # Compile and upload sitemap index
    log.info("Sitemap index contains %s sitemaps" % len(urls))
    smap = compile_sitemap_index(urls)
    smap_name = 'sitemap-www-https-bazardelux-com.xml'
    upload_sitemap(smap, smap_name)

    # And ping search engines
    ping_search_engines()

    return ApiPool.api.model.Ok()
