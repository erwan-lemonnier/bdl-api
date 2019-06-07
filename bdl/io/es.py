import logging
import json
from pymacaron.config import get_config
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection, serializer, compat, exceptions


log = logging.getLogger(__name__)


# Copy/pasted from https://github.com/elastic/elasticsearch-py/issues/374
class JSONSerializerPython2(serializer.JSONSerializer):
    """Override elasticsearch library serializer to ensure it encodes utf characters during json dump.
    See original at: https://github.com/elastic/elasticsearch-py/blob/master/elasticsearch/serializer.py#L42
    A description of how ensure_ascii encodes unicode characters to ensure they can be sent across the wire
    as ascii can be found here: https://docs.python.org/2/library/json.html#basic-usage
    """
    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, compat.string_types):
            return data
        try:
            return json.dumps(data, default=self.default, ensure_ascii=True)
        except (ValueError, TypeError) as e:
            raise exceptions.SerializationError(data, e)


def get_es(config_path=None, host=None, aws_access_key_id=None, aws_secret_access_key=None, aws_region=None):
    """Return an instance of Elasticsearch"""
    conf = get_config(path=config_path)
    if not aws_access_key_id:
        aws_access_key_id = conf.aws_access_key_id
    if not aws_secret_access_key:
        aws_secret_access_key = conf.aws_secret_access_key
    if not aws_region:
        aws_region = conf.aws_region
    if not host:
        host = conf.es_search_host
    awsauth = AWS4Auth(
        aws_access_key_id,
        aws_secret_access_key,
        aws_region,
        'es'
    )

    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        serializer=JSONSerializerPython2()
    )

    return es
