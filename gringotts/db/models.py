"""Model classes for use in the storage API.
This model is the abstraction layer across all DB models.
"""


class Model(object):
    """Base class for storage API models.
    """

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in kwds.iteritems():
            setattr(self, k, v)

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Model):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], Model):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def __eq__(self, other):
        return self.as_dict() == other.as_dict()

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


class Product(Model):
    """The DB Model for Product, which should has the same fields
    with API models.

    :param product_id: UUID of the product
    :param name: The name of the product
    :param service: The service the product belongs to
    :param region_id: The region id the product belongs to
    :param description: Some description to this product
    :param type: The charge type of the product(free/once/regular/metered)
    :param period: How often the product will be charged. Default is hourly.
    :param accurate: Whether do accurate charging, such as charging one hour
                     even if the resource has been deleted within one hour,
                     or charging by seconds if the resource has been deleted
                     within one hour, default is True.
    :param price: The price of the product
    :param currency: The currency of the price
    :param unit: The unit of the price, currently there are fllowing options:
                 hour, month, year, GB-hour, IOPS-hour (regular)
    """
    def __init__(self,
                 product_id, name, service, region_id, description,
                 type, period, accurate, price, currency, unit,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            product_id=product_id,
            name=name,
            service=service,
            region_id=region_id,
            description=description,
            type=type,
            period=period,
            accurate=accurate,
            price=price,
            currency=currency,
            unit=unit,
            created_at=created_at,
            updated_at=updated_at)


class Subscirption(Model):
    """The DB Model for Subscription

    :param subscription_id: UUID of the subscription
    :param resource_id: UUID of the resource
    :param resource_name: The name of the resource 
    :param resource_type: The type of the resource
    :param resource_status: The status of the resource
    :param product_id: The product this resource subscribes to
    :param current_fee: The total fee this resource spent from creation to now
    :param cron_time: The next charge time
    :param status: The status of this subscription, maybe active, delete
    :param user_id: The user id this subscription belongs to
    :param project_id: The project id this subscription belongs to
    """
    def __init__(self,
                 subscription_id, resource_id, resource_name, resource_type,
                 resource_status, product_id, current_fee, cron_time, status,
                 user_id, project_id, created_at, updated_at):
        Model.__init__(
            self,
            subscription_id=subscription_id,
            resource_id=resource_id,
            resource_name=resource_name,
            resource_type=resource_type,
            resource_status=resource_status,
            product_id=product_id,
            current_fee=current_fee,
            cron_time=cron_time,
            status=status,
            user_id=user_id,
            project_id=project_id,
            created_at=created_at,
            updated_at=updated_at)
