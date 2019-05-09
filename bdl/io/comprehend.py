import logging
import boto3
from pymacaron.config import get_config
from pymacaron.crash import report_error


log = logging.getLogger(__name__)


client = None


def get_comprehend():
    global client
    if not client:
        conf = get_config()
        aws_region = conf.aws_region if conf.aws_region else conf.aws_default_region
        log.info("AWS Comprehend setup against region:%s access_key_id:%s, aws_secret:%s***" % (aws_region, conf.aws_access_key_id, conf.aws_secret_access_key[0:8]))
        client = boto3.client(
            'comprehend',
            region_name=aws_region,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key
        )

    return client


def identify_language(text):
    log.debug("Calling AWS comprehend on text '%s'" % text)
    r = get_comprehend().detect_dominant_language(
        Text=text
    )
    log.debug("Comprehend says: %s" % r)

    # Response:
    # {
    #   'Languages': [
    #      {'Score': 0.9993218779563904, 'LanguageCode': 'en'}
    #    ],
    #    'ResponseMetadata': ...
    # }

    if 'Languages' in r and len(r['Languages']) > 0:
        top_language = None
        top_score = 0
        for d in r['Languages']:
            log.debug("Identified language %s (score: %s)" % (d['LanguageCode'], d['Score']))
            if d['Score'] > top_score:
                top_language = d['LanguageCode']
        return top_language

    report_error("Amazon Comprend failed to identify language in [%s]" % text)
    return 'en'
