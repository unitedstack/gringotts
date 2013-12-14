"""SQLAlchemy storage backend."""

from gringotts.db import base
from gringotts.db import models as db_models

from gringotts.db.sqlalchemy import migration
from gringotts.db.sqlalchemy import models as sa_models
from gringotts.db.sqlalchemy.models import Base

from gringotts.openstack.common import log
from gringotts.openstack.common.db.sqlalchemy import session as db_session
from gringotts.openstack.common.db.sqlalchemy import utils as db_utils


LOG = log.getLogger(__name__)

get_session = db_session.get_session


def model_query(context, model, *args, **kwargs):
    """Query helper for simpler session usage.

    :param context: the user context
    :param model: query model
    :param session: if present, the session to use
    """

    session = kwargs.get('session') or get_session()
    query = session.query(model, *args)
    return query


def _paginate_query(context, model, limit=None, marker=None,
                    sort_key=None, sort_dir=None, query=None):
    if not query:
        query = model_query(context, model)
    sort_keys = ['id']
    if sort_key and sort_key not in sort_keys:
        sort_keys.insert(0, sort_key)
    query = db_utils.paginate_query(query, model, limit, sort_keys,
                                    marker=marker, sort_dir=sort_dir)
    return query.all()


class SQLAlchemyStorage(base.StorageEngine):
    """Put the data into a SQLAlchemy database.
    """

    @staticmethod
    def get_connection(conf):
        """Return a Connection instance based on the configuration settings.
        """
        return Connection(conf)


class Connection(base.Connection):
    """SqlAlchemy connection."""

    def __init__(self, conf):
        url = conf.database.connection
        if url == 'sqlite://':
            conf.database.connection = \
                os.environ.get('CEILOMETER_TEST_SQL_URL', url)

    def upgrade(self):
        migration.db_sync()

    def clear(self):
        session = db_session.get_session()
        engine = session.get_bind()
        for table in reversed(Base.metadata.sorted_tables):
            engine.execute(table.delete())

    @staticmethod
    def _row_to_db_product_model(row):
        return db_models.Product(product_id=row.product_id,
                                 name=row.name,
                                 service=row.service,
                                 region_id=row.region_id,
                                 description=row.description,
                                 type=row.type,
                                 period=row.period,
                                 accurate=row.accurate,
                                 price=row.price,
                                 currency=row.currency,
                                 unit=row.unit,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at)

    def create_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            product_ref = sa_models.Product()
            product_ref.update(product.as_dict())
            session.add(product_ref)
        return self._row_to_db_product_model(product_ref)

    def get_products(self, context, filters=None, limit=None,
                     marker=None, sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Product)
        if 'name' in filters:
            query = query.filter_by(name=filters['name'])
        if 'service' in filters:
            query = query.filter_by(service=filters['service'])
        if 'region_id' in filters:
            query = query.filter_by(region_id=filters['region_id'])
        result =  _paginate_query(context, sa_models.Product,
                                  limit=limit, marker=marker,
                                  sort_key=sort_key, sort_dir=sort_dir,
                                  query=query)
        return (self._row_to_db_product_model(p) for p in result)

    def get_product(self, context, product_id):
        query = model_query(context, sa_models.Product).\
                filter_by(product_id=product_id)
        ref = query.one()
        return self._row_to_db_product_model(ref)

    def delete_product(self, context, product_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product_id)
            query.delete()

    def update_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product.product_id)
            query.update(product.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_product_model(ref)
