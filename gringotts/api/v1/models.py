import datetime
import wsme
from wsme import types as wtypes
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)


operation_kind = wtypes.Enum(str, 'lt', 'le', 'eq', 'ne', 'ge', 'gt')


class APIBase(wtypes.Base):
    """Inherit from wsme Base class to handle complex types
    """
    @classmethod
    def from_db_model(cls, m):
        return cls(**(m.as_dict()))
    
    @classmethod
    def transform(cls, **kwargs):
        return cls(**kwargs)

    def as_dict(self):
        return dict((k.name, getattr(self, k.name))
                    for k in wtypes.inspect_class(self.__class__)
                    if getattr(self, k.name) != wsme.Unset)

    # NOTE(suo): These two methods is to ensure the APIBase object can
    # be pickled by python-memcache client.
    def __getstate__(self):
        return self.as_dict()

    def __setstate__(self, state):
        for key in state:
            setattr(self, key, state[key])

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


class Query(APIBase):
    """Sample query filter.
    """

    _op = None  # provide a default

    def get_op(self):
        return self._op or 'eq'

    def set_op(self, value):
        self._op = value

    field = wtypes.text
    "The name of the field to test"

    #op = wsme.wsattr(operation_kind, default='eq')
    # this ^ doesn't seem to work.
    op = wsme.wsproperty(operation_kind, get_op, set_op)
    "The comparison operator. Defaults to 'eq'."

    value = wtypes.text
    "The value to compare against the stored data"

    def __repr__(self):
        # for logging calls
        return '<Query %r %s %r>' % (self.field, self.op, self.value)

    @classmethod
    def sample(cls):
        return cls(field='resource_id',
                   op='eq',
                   value='bd9431c1-8d69-4ad3-803a-8d4a6b89fd36',
                   )


class Version(APIBase):
    """The version model"""
    version = wtypes.text


class Product(APIBase):
    """A product represents a rule applied to resources to be billed 
    """
    product_id = wtypes.text
    name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text
    description = wtypes.text

    type = wtypes.text
    unit_price = float
    unit = wtypes.text

    created_at = datetime.datetime
    updated_at = datetime.datetime

    @classmethod
    def sample(cls):
        return cls(product_id='product-xxx',
                   name='product-1',
                   service='Compute',
                   region_id='region-xxx',
                   description='some decs',
                   type='regular',
                   unit_price=2.5,
                   unit='hour',
                   created_at=datetime.datetime.utcnow(),
                   updated_at=datetime.datetime.utcnow())


class Purchase(APIBase):
    """A Purchase
    """
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text
    volume = int


class Price(APIBase):
    """Price represents some products collection
    """
    unit_price = float
    hourly_amount = float
    monthly_amount = float
    unit = wtypes.text


class Sale(APIBase):
    """Statisttics Model for one single product
    """
    product_id = wtypes.text
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text

    quantity = float
    unit = wtypes.text
    total_price = float

    @classmethod
    def sample(cls):
        return cls(product_id='product-xxx',
                   product_name='product-1',
                   service='Compute',
                   region_id='region-xxx',
                   quantity=1000,
                   unit='hour',
                   total_price=1234.7996)


class Sales(APIBase):
    """Statistics for all products
    """
    total_price = float
    sales = [Sale]
    start_time = datetime.datetime
    end_time = datetime.datetime


class Subscription(APIBase):
    """Represent model for a subscription to a product
    """
    unit_price = float
    quantity = int
    total_price = float
    status = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text
    created_time =  datetime.datetime


class Order(APIBase):
    """One single order
    """
    order_id = wtypes.text
    resource_id = wtypes.text
    resource_name = wtypes.text
    resource_status = wtypes.text
    unit_price = float
    total_price = float
    type = wtypes.text
    created_time = datetime.datetime

    @classmethod
    def sample1(cls):
        return cls(order_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_name='vm1',
                   resource_status='active',
                   unit_price=0.48,
                   total_price=12.55,
                   type='instance',
                   created_time=datetime.datetime(2013, 12, 29, 03, 00, 00))

    @classmethod
    def sample2(cls):
        return cls(order_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_id='31d25817-2ece-4f25-8b7b-9af8dac1a70f',
                   resource_name='vm2',
                   resource_status='active',
                   unit_price=0.48,
                   total_price=1234.55,
                   type='instance',
                   created_time=datetime.datetime(2013, 12, 29, 04, 00, 00))


class Orders(APIBase):
    """Collection of orders
    """
    total_price = float
    order_amount = int
    orders = [Order]

    @classmethod
    def sample(cls):
        return cls(total_price=1245.1,
                   order_amount=2,
                   orders=[Order.sample1(),
                           Order.sample2()])

class Bill(APIBase):
    """Detail of an order
    """
    start_time = datetime.datetime
    end_time = datetime.datetime
    total_price = float
    unit_price = float
    remarks = wtypes.text

    @classmethod
    def sample1(cls):
        return cls(start_time=datetime.datetime(2013, 12, 29, 03, 00, 00),
                   end_time=datetime.datetime(2013, 12, 29, 04, 00, 00),
                   total_price=12.34,
                   unit_price=0.48,
                   remarks='Instance has been created')

    @classmethod
    def sample2(cls):
        return cls(start_time=datetime.datetime(2013, 12, 29, 04, 00, 00),
                   end_time=datetime.datetime(2013, 12, 29, 05, 00, 00),
                   total_price=12.34,
                   unit_price=0.48,
                   remarks='Instance has been stopped')


class UserAccount(APIBase):
    """Account for a tenant
    """
    balance = float
    currency = wtypes.text

    @classmethod
    def sample(cls):
        return cls(balance=1000.56,
                   currency='CNY')


class AdminAccount(APIBase):
    """Account for a tenant
    """
    balance = float
    consumption = float
    currency = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text

    @classmethod
    def sample1(cls):
        return cls(balance=1000.56,
                   consumption=321.5,
                   currency='CNY',
                   user_id='user-id-xxx',
                   project_id='project-id-xxx')

    @classmethod
    def sample2(cls):
        return cls(balance=100.74,
                   consumption=432.4,
                   currency='CNY',
                   user_id='user-id-yyy',
                   project_id='project-id-yyy')
