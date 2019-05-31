import logging
from pymacaron.config import get_config
from boto import ses

log = logging.getLogger(__name__)

conn = None

def get_ses_conn():
    global conn
    if not conn:
        conf = get_config()
        conn = ses.connect_to_region(
            'eu-west-1',
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key
        )

    return conn

def send_email(to_email, title, body, from_email=None):
    """Send email using SES"""

    if not to_email or not title or not body:
        raise Exception("Missing parameters: one of to, title or body is undefined")
    if not from_email:
        from_email = get_config().email_from

    # TODO: check ses quotas to make sure email does not get dropped because of quota limits
    # see http://boto.cloudhackers.com/en/latest/ses_tut.html
    log.info("Sending email to %s from %s with title '%s'" % (to_email, from_email, title))
    get_ses_conn().send_email(from_email, title, body, [to_email])

    # TODO: check result? catch exception? make sure email didn't bounce??
