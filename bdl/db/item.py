import logging
from boto3.dynamodb.conditions import Key
from bdl.model.item import model_to_item
from bdl.exceptions import ItemNotFoundError
from pymacaron_dynamodb import PersistentSwaggerObject, DynamoDBItemNotFound


log = logging.getLogger(__name__)


def store_item(item):
    # REMOVE
    import json
    from pymacaron_core.swagger.apipool import ApiPool
    log.debug("Storing to DB: %s" % json.dumps(ApiPool.bdl.model_to_json(item), indent=4))
    # REMOVE

    # Duh. Dynamodb does not like floats: convert them to strings...
    price = None
    price_sold = None
    if item.bdlitem:
        price = item.bdlitem.price
        price_sold = None
        if hasattr(item.bdlitem, 'price_sold'):
            price_sold = item.bdlitem.price_sold

        if price:
            item.bdlitem.price = str(price)
        if price_sold:
            item.bdlitem.price_sold = str(price_sold)
    # End of float normalization

    PersistentSwaggerObject.save_to_db(item)

    # Restore float values
    if item.bdlitem:
        item.bdlitem.price = price
        if price_sold:
            item.bdlitem.price_sold = price_sold


class PersistentItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'Item'
    table_name = 'items'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing item %s" % item.item_id)
        store_item(item)
        if index:
            item.index_to_es(async=async)


class PersistentArchivedItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'ArchivedItem'
    table_name = 'items-archived'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing archived item %s" % item.item_id)
        store_item(item)


def item_exists(item_id):
    """Return true if this item exists"""
    try:
        get_item(item_id)
        return True
    except ItemNotFoundError:
        return False


def get_item(item_id):
    """Retrieve an item from the item table, or the archive"""
    log.debug("Looking up item %s in items forsale" % item_id)
    try:
        p = PersistentItem.load_from_db(item_id)
        model_to_item(p)
        return p
    except DynamoDBItemNotFound:
        pass
    except Exception as e:
        raise e

    log.debug("Looking up item %s in item archive" % item_id)
    try:
        p = PersistentArchivedItem.load_from_db(item_id)
        model_to_item(p)
        return p
    except DynamoDBItemNotFound:
        log.debug("Item %s not found in Dynamodb" % item_id)
        raise ItemNotFoundError(item_id)


def get_item_by_native_url(native_url):
    """Retrieve an item from the item table, or the archive"""

    # Try the Item table first
    dbitems = PersistentItem.get_table().query(
        IndexName='native_url-index',
        KeyConditionExpression=Key('native_url').eq(native_url)
    )

    assert dbitems['Count'] <= 1, "Found more than 1 Item with native_url: '%s'" % native_url
    if dbitems['Count'] == 1:
        i = PersistentItem.to_model(dbitems['Items'][0])
        model_to_item(i)
        return i

    # Then the ArchivedItem table
    dbitems = PersistentArchivedItem.get_table().query(
        IndexName='native_url-index',
        KeyConditionExpression=Key('native_url').eq(native_url)
    )

    assert dbitems['Count'] <= 1, "Found more than 1 ArchivedItem with native_url: '%s'" % native_url
    if dbitems['Count'] == 1:
        i = PersistentArchivedItem.to_model(dbitems['Items'][0])
        model_to_item(i)
        return i

    return None
