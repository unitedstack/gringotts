"""Model classes for use in the storage API.
This model is the abstraction layer across all DB backends.
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
    :param type: The bill type of the product(regular/metered)
    :param unit_price: The unit price of the product
    :param unit: The unit of the price, currently there are fllowing options:
                 hour, month, year, GB-hour, IOPS-hour. Note that the unit
                 here should be corresponding to the period field. Fox example,
                 if period is hourly, and the unit here should be hour or GB-hour,
                 not month or GB-month.
    """
    def __init__(self,
                 product_id, name, service, region_id, description,
                 type, unit_price, unit,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            product_id=product_id,
            name=name,
            service=service,
            region_id=region_id,
            description=description,
            type=type,
            unit_price=unit_price,
            unit=unit,
            created_at=created_at,
            updated_at=updated_at)


class Order(Model):
    """The DB Model for order

    :param order_id: UUID of the order
    :param resource_id: UUID of the resource
    :param resource_name: The name of the resource
    :param resource_status: The status of the resource
    :param type: The type of the order
    :param unit_price: The unit price of this order, add up active subs
    :param unit: The unit of this order
    :param amount: The total fee this resource spent from creation to now
    :param cron_time: The next bill time
    :param status: The status of this subscription, maybe active, delete
    :param user_id: The user id this subscription belongs to
    :param project_id: The project id this subscription belongs to
    """
    def __init__(self,
                 order_id, resource_id, resource_name, resource_status,
                 type, unit_price, unit, amount, cron_time, status,
                 user_id, project_id,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            order_id=order_id,
            resource_id=resource_id,
            resource_name=resource_name,
            resource_status=resource_status,
            type=type,
            unit_price=unit_price,
            unit=unit,
            amount=amount,
            cron_time=cron_time,
            status=status,
            user_id=user_id,
            project_id=project_id,
            created_at=created_at,
            updated_at=updated_at)


class Subscription(Model):
    """The DB Model for Subscription

    :param subscription_id: UUID of the subscription
    :param status: The status of the subscription: inactive/active
    :param type: The type of the subscription, corresponding to resource
                 status.
    :param product_id: The product this resource subscribes to
    :param unit_price: The unit price of the product
    :param unit: The unit of the product
    :param resource_volume: The volue of the resource
    :param amount: The total fee this resource spent from creation to now
    :param order_id: The order this subscription belongs to
    :param user_id: The user id this subscription belongs to
    :param project_id: The project id this subscription belongs to
    """
    def __init__(self,
                 subscription_id, status, type, product_id, unit_price, unit,
                 resource_volume, amount, order_id, user_id, project_id,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            subscription_id=subscription_id,
            status=status,
            type=type,
            product_id=product_id,
            unit_price=unit_price,
            unit=unit,
            resource_volume=resource_volume,
            amount=amount,
            order_id=order_id,
            user_id=user_id,
            project_id=project_id,
            created_at=created_at,
            updated_at=updated_at)


class Bill(Model):
    """A detail bill record
    :param bill_id: The UUID of the bill
    :param start_time: The start time of the bill
    :param end_time: The end time of the bill
    :param amount: The fee between start_time and end_time
    :param unit_price: The unit price of the resource
    :param unit: The unit of the price
    :param order_id: The order id the bill belongs to
    :param remarks: The remarks of this bill
    :param user_id: The user id this bill belongs to
    :param project_id: The project id this bill belongs to
    """

    def __init__(self,
                 bill_id, start_time, end_time, amount, unit_price,
                 unit, order_id, remarks, user_id, project_id,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            bill_id=bill_id,
            start_time=start_time,
            end_time=end_time,
            amount=amount,
            unit_price=unit_price,
            unit=unit,
            order_id=order_id,
            remarks=remarks,
            user_id=user_id,
            project_id=project_id,
            created_at=created_at,
            updated_at=updated_at)


class Account(Model):
    """The DB model of account
    :param user_id: The uuid of the user
    :param project_id: The uuid of the project
    :param balance: The balance of the account
    :param consumption: The consumption of the account
    :param currency: The currency of the account
    """

    def __init__(self,
                 user_id, project_id, balance, consumption, currency,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            user_id=user_id,
            project_id=project_id,
            balance=balance,
            consumption=consumption,
            currency=currency,
            created_at=created_at,
            updated_at=updated_at)


class Charge(Model):
    """The charge record db model
    :param charge_id: The uuid of the charge
    :param user_id: The uuid of the user
    :param project_id: The uuid of the project
    :param value: The charge value one time
    :param currency: The currency of the value
    :param charge_time: The charge time
    """

    def __init__(self, charge_id, user_id, project_id, value,
                 currency, charge_time,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            charge_id=charge_id,
            user_id=user_id,
            project_id=project_id,
            value=value,
            currency=currency,
            charge_time=charge_time,
            created_at=created_at,
            updated_at=updated_at)


class Region(Model):
    """The region model
    """

    def __init__(self, region_id, name, description,
                 created_at=None, updated_at=None):
        Model.__init__(
            self,
            region_id=region_id,
            name=name,
            description=description,
            created_at=created_at,
            updated_at=updated_at)
