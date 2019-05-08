import logging
from bdl.model.item import model_to_item
from bdl.exceptions import ItemNotFoundError
from pymacaron_dynamodb import PersistentSwaggerObject, DynamoDBItemNotFound


log = logging.getLogger(__name__)


def store_item(item, index, async):
    # REMOVE
    import json
    from pymacaron_core.swagger.apipool import ApiPool
    log.debug("Storing to DB: %s" % json.dumps(ApiPool.bdl.model_to_json(item), indent=4))
    # REMOVE

    # Duh. Dynamodb does not like floats...
    price = item.price
    price_sold = item.price_sold

    if price:
        item.price = str(price)
    if price_sold:
        item.price_sold = str(price_sold)

    PersistentSwaggerObject.save_to_db(item)

    item.price = price
    item.price_sold = price_sold

    if index:
        item.index_to_es(async=async)


class PersistentItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'Item'
    table_name = 'items'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing item %s" % item.item_id)
        store_item(item, index, async)


class PersistentArchivedItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'Item'
    table_name = 'items-archived'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing archived item %s" % item.item_id)
        store_item(item, index, async)


def item_exists(item_id):
    """Return true if this item exists"""
    try:
        get_item(item_id)
        return True
    except ItemNotFoundError:
        return False


def get_item(item_id):
    """Retrieve an item from the item table, or the archive"""
    try:
        log.debug("Looking up item %s in items forsale" % item_id)
        p = PersistentItem.load_from_db(item_id)
        model_to_item(p)
        return p
    except DynamoDBItemNotFound:
        try:
            log.debug("Looking up item %s in item archive" % item_id)
            p = PersistentArchivedItem.load_from_db(item_id)
            model_to_item(p)
            return p
        except DynamoDBItemNotFound:
            log.debug("Item %s not found in Dynamodb" % item_id)
            raise ItemNotFoundError(item_id)
