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
    name = wsme.wsattr(wtypes.text, mandatory=True)
    service = wsme.wsattr(wtypes.text, mandatory=True)
    region_id = wsme.wsattr(wtypes.text, default='default')
    description = wtypes.text

    type = wsme.wsattr(wtypes.text, default='regular')
    unit_price = wsme.wsattr(float, mandatory=True)
    unit = wsme.wsattr(wtypes.text, mandatory=True, default='hour')

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
    amount = int


class Price(APIBase):
    """Price represents some products collection
    """
    unit_price = float
    total_price = float
    unit = wtypes.text
    currency = wtypes.text


class ProductStatistics(APIBase):
    """Statisttics Model for one single product
    """
    product_id = wtypes.text
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text

    volume = float
    unit = wtypes.text
    sales = float


    @classmethod
    def sample(cls):
        return cls(product_id='product-xxx',
                   name='product-1',
                   service='Compute',
                   region_id='region-xxx',
                   volume=1000,
                   price=0.48,
                   unit='hour',
                   sales=1234.7996,
                   start_time=datetime.datetime.utcnow(),
                   end_time=datetime.datetime.utcnow())


class ProductsStatistics(APIBase):
    """Statistics for all products
    """
    total_sales = float
    products = [ProductStatistics]
    start_time = datetime.datetime
    end_time = datetime.datetime


class ProductSubscription(APIBase):
    """Represent model for a subscription to a product
    """
    resource_id = wtypes.text
    resource_name = wtypes.text
    resource_volume = int
    user_id = wtypes.text
    project_id = wtypes.text
    sales = float
    created_time =  datetime.datetime


class ProductStatisticsDetail(APIBase):
    """Statisttics Model for product
    """
    product_id = wtypes.text
    product_name = wtypes.text
    service = wtypes.text
    region_id = wtypes.text

    total_sales = float
    total_volume = int
    subscriptions = [ProductSubscription]

    start_time = datetime.datetime
    end_time = datetime.datetime


class ResourceStatistics(APIBase):
    """One resource statistics
    """
    resource_id = wtypes.text
    resource_name = wtypes.text
    resource_status = wtypes.text
    resource_volume = int
    total_price = float
    created_time = datetime.datetime


class ResourcesStatistics(APIBase):
    """Statistics for all products
    """
    total_price = float
    resource_amount = int
    resources= [ResourceStatistics]
    resource_type = wtypes.text


class ResourceBill(APIBase):
    """Detail bill records of one resource
    """
    start_time = datetime.datetime
    end_time = datetime.datetime
    total_price = float
    unit_price = float
    unit = wtypes.text
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
                   remarks='Instance has been changed')

    @classmethod
    def sample3(cls):
        return cls(start_time=datetime.datetime(2013, 12, 29, 05, 00, 00),
                   end_time=datetime.datetime(2013, 12, 29, 06, 00, 00),
                   total_price=12.34,
                   unit_price=0.48,
                   remarks='Instance has been stopped')


class ResourceStatisticsDetail(APIBase):
    """Statistics for a resoruce
    """
    total_price = float
    bills = [ResourceBill]

    @classmethod
    def sample(cls):
        return cls(total_price=37.02,
                   bills=[ResourceBill.sample1(),
                          ResourceBill.sample2(),
                          ResourceBill.sample3()])
