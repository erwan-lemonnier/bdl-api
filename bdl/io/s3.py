import logging
from pymacaron.config import get_config
from boto import s3

# Because of dots in bucket names: https://github.com/boto/boto/issues/421
from boto.s3.connection import ProtocolIndependentOrdinaryCallingFormat


log = logging.getLogger(__name__)


conn = None


def get_s3_conn():
    global conn
    if not conn:
        conf = get_config()
        conn = s3.connect_to_region(
            conf.aws_region,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key,
            calling_format=ProtocolIndependentOrdinaryCallingFormat()
        )

    return conn
