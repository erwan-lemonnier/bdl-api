import logging
import boto3
from pymacaron.config import get_config


log = logging.getLogger(__name__)


client = None


def get_comprehend():
    global client
    if not client:
        conf = get_config()
        aws_region = conf.aws_region if conf.aws_region else conf.aws_default_region
        log.info("AWS Comprehend setup against region:%s access_key_id:%s, aws_secret:%s***" % (aws_region, conf.aws_access_key_id, conf.aws_secret_access_key[0:8]))
        client = boto3.resource(
            'comprehend',
            region_name=aws_region,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key
        )

    return client


def identify_language(text):
    r = get_comprehend().detect_dominant_language(text)
    log.debug("GOT r: %s" % r)
    assert 0
