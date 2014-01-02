"""SQLAlchemy storage backend."""

from __future__ import absolute_import

import functools
import os
from sqlalchemy import desc

from gringotts import context as gring_context
from gringotts import exception

from gringotts.db import base
from gringotts.db import models as db_models

from gringotts.db.sqlalchemy import migration
from gringotts.db.sqlalchemy import models as sa_models
from gringotts.db.sqlalchemy.models import Base

from gringotts.openstack.common.db.sqlalchemy import session as db_session
from gringotts.openstack.common.db.sqlalchemy import utils as db_utils
from gringotts.openstack.common import log


LOG = log.getLogger(__name__)

get_session = db_session.get_session


def require_admin_context(f):
    """Decorator to require admin request context.

    The second argument to the wrapped function must be the context.

    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        gring_context.require_admin_context(args[1])
        return f(*args, **kwargs)
    return wrapper


def require_context(f):
    """Decorator to require *any* user or admin context.

    This does no authorization for user or project access matching, see
    :py:func:`nova.context.authorize_project_context` and
    :py:func:`nova.context.authorize_user_context`.

    The second argument to the wrapped function must be the context.

    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        gring_context.require_context(args[1])
        return f(*args, **kwargs)
    return wrapper


def model_query(context, model, *args, **kwargs):
    """Query helper for simpler session usage.

    :param context: the user context
    :param model: query model
    :param session: if present, the session to use
    """

    session = kwargs.get('session') or get_session()
    query = session.query(model, *args)

    if gring_context.is_user_context(context):
        query = query.filter_by(project_id=context.project_id)
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
                os.environ.get('GRINGOTTS_TEST_SQL_URL', url)

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
                                 unit_price=row.unit_price,
                                 unit=row.unit,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_order_model(row):
        return db_models.Order(order_id=row.order_id,
                               resource_id=row.resource_id,
                               resource_name=row.resource_name,
                               resource_status=row.resource_status,
                               type=row.type,
                               unit_price=row.unit_price,
                               unit=row.unit,
                               amount=row.amount,
                               cron_time=row.cron_time,
                               status=row.status,
                               user_id=row.user_id,
                               project_id=row.project_id,
                               created_at=row.created_at,
                               updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_subscription_model(row):
        return db_models.Subscription(subscription_id=row.subscription_id,
                                      status=row.status,
                                      type=row.type,
                                      product_id=row.product_id,
                                      unit_price=row.unit_price,
                                      unit=row.unit,
                                      order_id=row.order_id,
                                      resource_volume=row.resource_volume,
                                      amount=row.amount,
                                      user_id=row.user_id,
                                      project_id=row.project_id,
                                      created_at=row.created_at,
                                      updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_bill_model(row):
        return db_models.Bill(bill_id=row.bill_id,
                              start_time=row.start_time,
                              end_time=row.end_time,
                              amount=row.amount,
                              unit_price=row.unit_price,
                              unit=row.unit,
                              order_id=row.order_id,
                              remarks=row.remarks,
                              user_id=row.user_id,
                              project_id=row.project_id,
                              created_at=row.created_at,
                              updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_account_model(row):
        return db_models.Account(user_id=row.user_id,
                                 project_id=row.project_id,
                                 balance=row.balance,
                                 consumption=row.consumption,
                                 currency=row.currency,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_charge_model(row):
        return db_models.Charge(charge_id=row.charge_id,
                                user_id=row.user_id,
                                project_id=row.project_id,
                                value=row.value,
                                unit=row.unit,
                                charge_time=row.charge_time,
                                created_at=row.created_at,
                                updated_at=row.updated_at)

    @require_admin_context
    def create_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            product_ref = sa_models.Product()
            product_ref.update(product.as_dict())
            session.add(product_ref)
        return self._row_to_db_product_model(product_ref)

    @require_context
    def get_products(self, context, filters=None, limit=None,
                     marker=None, sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Product)
        if 'name' in filters:
            query = query.filter_by(name=filters['name'])
        if 'service' in filters:
            query = query.filter_by(service=filters['service'])
        if 'region_id' in filters:
            query = query.filter_by(region_id=filters['region_id'])

        if marker is not None:
            try:
                marker = self.get_product(context, marker)
            except exception.ProductIdNotFound:
                raise exception.MarkerNotFount(marker)

        result = _paginate_query(context, sa_models.Product,
                                 limit=limit, marker=marker,
                                 sort_key=sort_key, sort_dir=sort_dir,
                                 query=query)
        return (self._row_to_db_product_model(p) for p in result)

    @require_context
    def get_product(self, context, product_id):
        query = model_query(context, sa_models.Product).\
            filter_by(product_id=product_id)
        try:
            ref = query.one()
        except Exception:
            raise exception.ProductIdNotFound(product_id)
        return self._row_to_db_product_model(ref)

    @require_admin_context
    def delete_product(self, context, product_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product_id)
            query.delete()

    @require_admin_context
    def update_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product.product_id)
            query.update(product.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_product_model(ref)

    @require_admin_context
    def create_order(self, context, order):
        session = db_session.get_session()
        with session.begin():
            ref = sa_models.Order()
            ref.update(order.as_dict())
            session.add(ref)
        return self._row_to_db_order_model(ref)

    @require_admin_context
    def update_order(self, context, order):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Order)
            query = query.filter_by(order_id=order.order_id)
            query.update(order.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_order_model(ref)

    @require_context
    def get_order_by_resource_id(self, context, resource_id):
        query = model_query(context, sa_models.Order).\
            filter_by(resource_id=resource_id)
        ref = query.one()
        return self._row_to_db_order_model(ref)

    @require_context
    def get_order(self, context, order_id):
        query = model_query(context, sa_models.Order).\
            filter_by(order_id=order_id)
        ref = query.one()
        return self._row_to_db_order_model(ref)

    @require_context
    def get_orders(self, context, limit=None, marker=None,
                   sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Order)
        result = _paginate_query(context, sa_models.Order,
                                 limit=limit, marker=marker,
                                 sort_key=sort_key, sort_dir=sort_dir,
                                 query=query)
        return (self._row_to_db_order_model(o) for o in result)

    @require_admin_context
    def create_subscription(self, context, subscription):
        session = db_session.get_session()
        with session.begin():
            sub_ref = sa_models.Subscription()
            sub_ref.update(subscription.as_dict())
            session.add(sub_ref)
        return self._row_to_db_subscription_model(sub_ref)

    @require_admin_context
    def update_subscription(self, context, subscription):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Subscription)
            query = query.filter_by(subscription_id=subscription.subscription_id)
            query.update(subscription.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_subscription_model(ref)

    @require_context
    def get_subscriptions_by_order_id(self, context, order_id,
                                      status=None, type=None):
        query = model_query(context, sa_models.Subscription).\
            filter_by(order_id=order_id)
        if status:
            query = query.filter_by(status=status)
        if type:
            query = query.filter_by(type=type)
        ref = query.all()
        return (self._row_to_db_subscription_model(r) for r in ref)

    @require_context
    def get_subscription(self, context, subscription_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Subscription)
            query = query.filter_by(subscription_id=subscription_id)
            ref = query.one()
        return self._row_to_db_subscription_model(ref)

    @require_admin_context
    def get_subscriptions_by_product_id(self, context, product_id,
                                        start_time=None, end_time=None,
                                        limit=None, marker=None, sort_key=None,
                                        sort_dir=None):
        query = model_query(context, sa_models.Subscription).\
            filter_by(product_id=product_id)

        if start_time:
            query = query.filter(sa_models.Subscription.created_at >= start_time)
        if end_time:
            query = query.filter(sa_models.Subscription.created_at <= end_time)

        ref = _paginate_query(context, sa_models.Subscription,
                              limit=limit, marker=marker,
                              sort_key=sort_key, sort_dir=sort_dir,
                              query=query)

        return (self._row_to_db_subscription_model(r) for r in ref)

    @require_admin_context
    def create_bill(self, context, bill):
        session = db_session.get_session()
        with session.begin():
            bill_ref = sa_models.Bill()
            bill_ref.update(bill.as_dict())
            session.add(bill_ref)
        return self._row_to_db_bill_model(bill_ref)

    @require_admin_context
    def update_bill(self, context, bill):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Bill)
            query = query.filter_by(bill_id=bill.bill_id)
            query.update(bill.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_bill_model(ref)

    @require_context
    def get_latest_bill(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Bill)
            query = query.filter_by(order_id=order_id)
            ref = query.order_by(desc(sa_models.Bill.id)).all()[0]
        return self._row_to_db_bill_model(ref)

    @require_admin_context
    def get_bills_by_subscription_id(self, context, subscription_id):
        query = model_query(context, sa_models.Bill).\
            filter_by(subscription_id=subscription_id)
        ref = query.all()
        return (self._row_to_db_bill_model(r) for r in ref)

    @require_context
    def create_account(self, context, account):
        session = db_session.get_session()
        with session.begin():
            account_ref = sa_models.Account()
            account_ref.update(account.as_dict())
            session.add(account_ref)
        return self._row_to_db_account_model(account_ref)

    @require_context
    def get_account(self, context, project_id):
        query = model_query(context, sa_models.Account).\
            filter_by(project_id=project_id)
        ref = query.one()
        return self._row_to_db_account_model(ref)

    @require_context
    def update_account(self, context, account):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Account)
            query = query.filter_by(project_id=account.project_id)
            query.update(account.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_account_model(ref)

    @require_context
    def create_charge(self, context, charge):
        session = db_session.get_session()
        with session.begin():
            ref = sa_models.Charge()
            ref.update(charge.as_dict())
            session.add(ref)
        return self._row_to_db_charge_model(ref)
