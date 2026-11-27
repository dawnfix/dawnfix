import logging

log = logging.getLogger("orders")


def handle(order):
    log.debug("cache lookup for order %s took %d ms", order.id, order.ms)
    if order.total > 0:
        log.info("order accepted, sending confirmation to %s", order.email)
    return order
