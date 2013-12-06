"""
SQLAlchemy models for Gringotts data
"""

import json
import urlparse
from oslo.config import cfg

from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy import DateTime, Index, Float, Boolean, Text
from sqlalchemy.types import TypeDecorator, DATETIME
from sqlalchemy.ext.declarative import declarative_base

from gringotts.openstack.common import timeutils

sql_opts = [
    cfg.StrOpt('mysql_engine',
               default='InnoDB',
               help='MySQL engine')
]

cfg.CONF.register_opts(sql_opts)


def table_args():
    engine_name = urlparse.urlparse(cfg.CONF.database.connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': cfg.CONF.mysql_engine,
                'mysql_charset': "utf8"}
    return None


class JSONEncodedDict(TypeDecorator):
    "Represents an immutable structure as a json-encoded string."

    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class GringottsBase(object):
    """Base class for Gringotts Models."""
    __table_args__ = table_args()
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in values.iteritems():
            setattr(self, k, v)


Base = declarative_base(cls=GringottsBase)


class Product(Base):
    """Product DB Model of SQLAlchemy"""

    __tablename__ = 'product'

    id = Column(Integer, primary_key=True)

    uuid = Column(String(255))
    name = Column(String(255))
    description = Column(String(255))

    meter_name = Column(String(255))
    source = Column(String(255))

    region_id = Column(String(255))
    user_id = Column(String(255))
    project_id = Column(String(255))

    type = Column(String(255))
    time_size = Column(Integer)
    time_unit = Column(String(255))
    quantity_from = Column(Integer)
    quantity_to = Column(Integer)
    quantity_unit = Column(String(255))

    price = Column(Float)
    currency = Column(String(255))

    created_at = Column(DateTime, default=timeutils.utcnow)
    updated_at = Column(DateTime)
