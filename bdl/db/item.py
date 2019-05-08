import logging
from bdl.model.item import model_to_item
from bdl.exceptions import ItemNotFoundError
from pymacaron_dynamodb import PersistentSwaggerObject, DynamoDBItemNotFound


log = logging.getLogger(__name__)


# Duh. Dynamodb does not like floats...
def numbers_to_strings(item):
    if item.price:
        item.price = str(item.price)
    if item.price_sold:
        item.price_sold = str(item.price_sold)

def strings_to_numbers(item):
    if item.price:
        item.price = float(item.price)
    if item.price_sold:
        item.price_sold = float(item.price_sold)


class PersistentItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'Item'
    table_name = 'items'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing item %s" % item.item_id)
        # REMOVE
        import json
        from pymacaron_core.swagger.apipool import ApiPool
        log.debug("Storing to DB: %s" % json.dumps(ApiPool.bdl.model_to_json(item), indent=4))
        # REMOVE
        numbers_to_strings(item)
        PersistentSwaggerObject.save_to_db(item)
        strings_to_numbers(item)
        if index:
            item.index_to_es(async=async)


class PersistentArchivedItem(PersistentSwaggerObject):
    api_name = 'bdl'
    model_name = 'Item'
    table_name = 'items-archived'
    primary_key = 'item_id'

    def save_to_db(item, index=True, async=True):
        log.info("Storing item %s" % item.item_id)
        numbers_to_strings(item)
        PersistentSwaggerObject.save_to_db(item)
        strings_to_numbers(item)
        if index:
            item.index_to_es(async=async)


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
