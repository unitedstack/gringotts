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
    uuid = wtypes.text
    name = wtypes.text
    description = wtypes.text

    meter_name = wtypes.text
    source = wtypes.text

    region_id = wtypes.text
    user_id = wtypes.text
    project_id = wtypes.text

    type = wtypes.text
    time_size = int
    time_unit = wtypes.text
    quantity_from = int
    quantity_to = int
    quantity_unit = wtypes.text

    price = float
    currency = wtypes.text

    created_at = datetime.datetime
    updated_at = datetime.datetime

    @classmethod
    def sample(cls):
        return cls(uuid='uuid',
                   name='product-1',
                   description='some decs',
                   meter_name='instance',
                   source='nova',
                   region_id='region-xxx',
                   user_id='user-xxx',
                   project_id='project-xxx',
                   type='time',
                   time_size=1,
                   time_unit='hour',
                   quantity_from=0,
                   quantity_to=0,
                   quantity_unit='KB',
                   price=2.5,
                   currency='RMB',
                   created_at=datetime.datetime.utcnow(),
                   updated_at=datetime.datetime.utcnow())
