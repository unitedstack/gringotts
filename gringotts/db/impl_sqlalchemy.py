"""SQLAlchemy storage backend."""

from __future__ import absolute_import

import datetime
import functools
import os
from sqlalchemy import desc, asc
from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from oslo.config import cfg

from gringotts import constants as const
from gringotts import context as gring_context
from gringotts import exception
from gringotts import utils as gringutils

from gringotts.db import base
from gringotts.db import models as db_models

from gringotts.db.sqlalchemy import migration
from gringotts.db.sqlalchemy import models as sa_models
from gringotts.db.sqlalchemy.models import Base

from gringotts.openstack.common.db import exception as db_exception
from gringotts.openstack.common.db.sqlalchemy import session as db_session
from gringotts.openstack.common.db.sqlalchemy import utils as db_utils
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)
cfg.CONF.import_opt('enable_owe', 'gringotts.master.service')
cfg.CONF.import_opt('allow_delay_seconds', 'gringotts.master.service', group='master')

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

    if gring_context.is_user_context(context) and hasattr(model, 'project_id'):
        query = query.filter_by(project_id=context.project_id)
    return query


def paginate_query(context, model, limit=None, offset=None,
                   sort_key=None, sort_dir=None, query=None):
    if not query:
        query = model_query(context, model)
    sort_keys = ['id']
    if sort_key and sort_key not in sort_keys:
        sort_keys.insert(0, sort_key)
    query = _paginate_query(query, model, limit, sort_keys,
                            offset=offset, sort_dir=sort_dir)
    return query.all()


def _paginate_query(query, model, limit, sort_keys, offset=None,
                     sort_dir=None, sort_dirs=None):
    if 'id' not in sort_keys:
        # TODO(justinsb): If this ever gives a false-positive, check
        # the actual primary key, rather than assuming its id
        LOG.warn(_('Id not in sort_keys; is sort_keys unique?'))

    assert(not (sort_dir and sort_dirs))

    # Default the sort direction to ascending
    if sort_dirs is None and sort_dir is None:
        sort_dir = 'desc'

    # Ensure a per-column sort direction
    if sort_dirs is None:
        sort_dirs = [sort_dir for _sort_key in sort_keys]

    assert(len(sort_dirs) == len(sort_keys))

    # Add sorting
    for current_sort_key, current_sort_dir in zip(sort_keys, sort_dirs):
        try:
            sort_dir_func = {
                'asc': asc,
                'desc': desc,
            }[current_sort_dir]
        except KeyError:
            raise ValueError(_("Unknown sort direction, "
                               "must be 'desc' or 'asc'"))
        try:
            sort_key_attr = getattr(model, current_sort_key)
        except AttributeError:
            raise InvalidSortKey()
        query = query.order_by(sort_dir_func(sort_key_attr))

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    return query


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
                                 deleted=row.deleted,
                                 unit_price=row.unit_price,
                                 unit=row.unit,
                                 quantity=row.quantity,
                                 total_price=row.total_price,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at,
                                 deleted_at=row.deleted_at)

    @staticmethod
    def _row_to_db_order_model(row):
        return db_models.Order(order_id=row.order_id,
                               resource_id=row.resource_id,
                               resource_name=row.resource_name,
                               type=row.type,
                               status=row.status,
                               unit_price=row.unit_price,
                               unit=row.unit,
                               total_price=row.total_price,
                               cron_time=row.cron_time,
                               date_time=row.date_time,
                               user_id=row.user_id,
                               project_id=row.project_id,
                               region_id=row.region_id,
                               owed=row.owed,
                               created_at=row.created_at,
                               updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_subscription_model(row):
        return db_models.Subscription(subscription_id=row.subscription_id,
                                      type=row.type,
                                      product_id=row.product_id,
                                      unit_price=row.unit_price,
                                      unit=row.unit,
                                      quantity=row.quantity,
                                      total_price=row.total_price,
                                      order_id=row.order_id,
                                      user_id=row.user_id,
                                      project_id=row.project_id,
                                      region_id=row.region_id,
                                      created_at=row.created_at,
                                      updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_bill_model(row):
        return db_models.Bill(bill_id=row.bill_id,
                              start_time=row.start_time,
                              end_time=row.end_time,
                              type=row.type,
                              status=row.status,
                              unit_price=row.unit_price,
                              unit=row.unit,
                              total_price=row.total_price,
                              order_id=row.order_id,
                              resource_id=row.resource_id,
                              remarks=row.remarks,
                              user_id=row.user_id,
                              project_id=row.project_id,
                              region_id=row.region_id,
                              created_at=row.created_at,
                              updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_account_model(row):
        return db_models.Account(user_id=row.user_id,
                                 project_id=row.project_id,
                                 balance=row.balance,
                                 consumption=row.consumption,
                                 currency=row.currency,
                                 level=row.level,
                                 owed=row.owed,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_charge_model(row):
        return db_models.Charge(charge_id=row.charge_id,
                                user_id=row.user_id,
                                project_id=row.project_id,
                                value=row.value,
                                type=row.type,
                                come_from=row.come_from,
                                currency=row.currency,
                                charge_time=row.charge_time,
                                created_at=row.created_at,
                                updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_region_model(row):
        return db_models.Region(region_id=row.region_id,
                                name=row.name,
                                description=row.description,
                                created_at=row.created_at,
                                updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_precharge_model(row):
        return db_models.PreCharge(code=row.code,
                                   price=row.price,
                                   used=row.used,
                                   dispatched=row.dispatched,
                                   user_id=row.user_id,
                                   project_id=row.project_id,
                                   created_at=row.created_at,
                                   expired_at=row.expired_at,
                                   remarks=row.remarks)

    @require_admin_context
    def create_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            product_ref = sa_models.Product()
            product_ref.update(product.as_dict())
            session.add(product_ref)
        return self._row_to_db_product_model(product_ref)

    @require_context
    def get_products(self, context, filters=None, read_deleted=False,
                     limit=None, offset=None, sort_key=None,
                     sort_dir=None):
        query = model_query(context, sa_models.Product)
        if 'name' in filters:
            query = query.filter_by(name=filters['name'])
        if 'service' in filters:
            query = query.filter_by(service=filters['service'])
        if 'region_id' in filters:
            query = query.filter_by(region_id=filters['region_id'])
        if not read_deleted:
            query = query.filter_by(deleted=False)

        result = paginate_query(context, sa_models.Product,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_product_model(p) for p in result)

    @require_context
    def get_product(self, context, product_id):
        query = model_query(context, sa_models.Product).\
            filter_by(product_id=product_id).\
            filter_by(deleted=False)
        try:
            ref = query.one()
        except NoResultFound:
            raise exception.ProductIdNotFound(product_id)
        return self._row_to_db_product_model(ref)

    @require_admin_context
    def delete_product(self, context, product_id):
        product = self.get_product(context, product_id)
        product.deleted = True

        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product.product_id)
            query.update(product.as_dict(), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_product_model(ref)

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
    def create_order(self, context, **order):
        session = db_session.get_session()
        with session.begin():
            ref = sa_models.Order(
                order_id=order['order_id'],
                resource_id=order['resource_id'],
                resource_name=order['resource_name'],
                type=order['type'],
                unit_price=order['unit_price'],
                unit=order['unit'],
                total_price=0,
                cron_time=None,
                date_time=None,
                status=order['status'],
                user_id=order['user_id'],
                project_id=order['project_id'],
                region_id=order['region_id']
            )
            session.add(ref)
        return self._row_to_db_order_model(ref)

    @require_admin_context
    def update_order(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            # Get subs of this order
            subs = model_query(context, sa_models.Subscription, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                filter_by(type=kwargs['change_to']).\
                with_lockmode('read').all()

            # caculate new unit price
            unit_price = 0
            unit = None

            for sub in subs:
                unit_price += sub.unit_price * sub.quantity
                unit = sub.unit

            # update the order
            a_order = dict(unit_price=unit_price,
                           unit=unit,
                           updated_at=datetime.datetime.utcnow())

            if kwargs['change_order_status']:
                a_order.update(status=kwargs['first_change_to'] or kwargs['change_to'])
            if kwargs['cron_time']:
                a_order.update(cron_time=kwargs['cron_time'])

            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                with_lockmode('update').\
                update(a_order)

    @require_context
    def get_order_by_resource_id(self, context, resource_id):
        query = model_query(context, sa_models.Order).\
            filter_by(resource_id=resource_id)
        try:
            ref = query.one()
        except NoResultFound:
            LOG.warning('The order of the resource(%s) not found' % resource_id)
            raise exception.ResourceOrderNotFound(resource_id=resource_id)

        return self._row_to_db_order_model(ref)

    @require_context
    def get_order(self, context, order_id):
        query = model_query(context, sa_models.Order).\
            filter_by(order_id=order_id)
        try:
            ref = query.one()
        except NoResultFound:
            LOG.warning('The order %s not found' % order_id)
            raise exception.OrderNotFound(order_id=order_id)

        return self._row_to_db_order_model(ref)

    @require_context
    def get_orders(self, context, start_time=None, end_time=None, type=None,
                   status=None, limit=None, offset=None, sort_key=None,
                   sort_dir=None, with_count=False, region_id=None,
                   project_id=None, owed=None):
        """Get orders that have bills during start_time and end_time.
        If start_time is None or end_time is None, will ignore the datetime
        range, and return all orders
        """
        query = model_query(context, sa_models.Order)

        if type:
            query = query.filter_by(type=type)
        if status:
            query = query.filter_by(status=status)
        if region_id:
            query = query.filter_by(region_id=region_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if owed:
            query = query.filter_by(owed=owed)

        if all([start_time, end_time]):
            query = query.join(sa_models.Bill,
                               sa_models.Order.order_id==sa_models.Bill.order_id)
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)
            query = query.group_by(sa_models.Bill.order_id)

        if with_count:
            total_count = len(query.all())

        result = paginate_query(context, sa_models.Order,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)
        if with_count:
            return (self._row_to_db_order_model(o) for o in result), total_count
        else:
            return (self._row_to_db_order_model(o) for o in result)

    @require_admin_context
    def get_active_order_count(self, context, region_id=None, owed=None):
        query = model_query(context, sa_models.Order,
                            func.count(sa_models.Order.id).label('count'))
        if region_id:
            query = query.filter_by(region_id=region_id)
        if owed:
            query = query.filter_by(owed=owed)
        query = query.filter(not_(sa_models.Order.status == const.STATE_DELETED))
        return query.one().count or 0

    @require_admin_context
    def get_stopped_order_count(self, context, region_id=None, owed=None):
        query = model_query(context, sa_models.Order,
                            func.count(sa_models.Order.id).label('count'))
        if region_id:
            query = query.filter_by(region_id=region_id)
        if owed:
            query = query.filter_by(owed=owed)
        query = query.filter(sa_models.Order.status == const.STATE_STOPPED)
        return query.one().count or 0

    @require_context
    def get_active_orders(self, context, type=None, limit=None, offset=None, sort_key=None,
                   sort_dir=None, region_id=None, project_id=None, owed=None, within_one_hour=None):
        """Get all active orders
        """
        query = model_query(context, sa_models.Order)

        if type:
            query = query.filter_by(type=type)
        if region_id:
            query = query.filter_by(region_id=region_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if owed:
            query = query.filter_by(owed=owed)

        if within_one_hour:
            one_hour_later = timeutils.utcnow() + datetime.timedelta(hours=1)
            query = query.filter(sa_models.Order.cron_time < one_hour_later)

        query = query.filter(not_(sa_models.Order.status==const.STATE_DELETED))

        result = paginate_query(context, sa_models.Order,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)
        return (self._row_to_db_order_model(o) for o in result)

    @require_admin_context
    def create_subscription(self, context, **subscription):
        session = db_session.get_session()
        with session.begin():
            # Get product
            try:
                product = model_query(context, sa_models.Product, session=session).\
                        filter_by(name=subscription['product_name']).\
                        filter_by(service=subscription['service']).\
                        filter_by(region_id=subscription['region_id']).\
                        filter_by(deleted=False).\
                        with_lockmode('update').one()
            except NoResultFound:
                msg = "Product with name(%s) within service(%s) in region_id(%s) not found" % \
                       (subscription['product_name'], subscription['service'], subscription['region_id'])
                LOG.warning(msg)
                return None
            except MultipleResultsFound:
                msg = "Duplicated products with name(%s) within service(%s) in region_id(%s)" % \
                       (subscription['product_name'], subscription['service'], subscription['region_id'])
                LOG.error(msg)
                raise exception.DuplicatedProduct(reason=msg)

            quantity = subscription['resource_volume']

            subscription = sa_models.Subscription(
                subscription_id=uuidutils.generate_uuid(),
                type=subscription['type'],
                product_id=product.product_id,
                unit_price=product.unit_price,
                unit=product.unit,
                quantity=quantity,
                total_price=gringutils._quantize_decimal('0'),
                order_id=subscription['order_id'],
                user_id=subscription['user_id'],
                project_id=subscription['project_id'],
                region_id=subscription['region_id']
            )

            session.add(subscription)

            # Update product
            product.quantity += quantity

        return self._row_to_db_subscription_model(subscription)

    def update_subscription(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            subs = model_query(context, sa_models.Subscription, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                filter_by(type=kwargs['change_to']).\
                with_lockmode('update').all()

            for sub in subs:
                sub.quantity = kwargs['quantity']

    def update_flavor_subscription(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            try:
                old_product = model_query(context, sa_models.Product, session=session).\
                        filter_by(name=kwargs['old_flavor']).\
                        filter_by(service=kwargs['service']).\
                        filter_by(region_id=kwargs['region_id']).\
                        filter_by(deleted=False).\
                        with_lockmode('update').one()
                new_product = model_query(context, sa_models.Product, session=session).\
                        filter_by(name=kwargs['new_flavor']).\
                        filter_by(service=kwargs['service']).\
                        filter_by(region_id=kwargs['region_id']).\
                        filter_by(deleted=False).\
                        with_lockmode('update').one()
            except NoResultFound:
                msg = "Product with name(%s/%s) within service(%s) in region_id(%s) not found" % \
                       (kwargs['old_flavor'], kwargs['new_flavor'], kwargs['service'], kwargs['region_id'])
                LOG.error(msg)
                return None
            except MultipleResultsFound:
                msg = "Duplicated products with name(%s/%s) within service(%s) in region_id(%s)" % \
                       (kwargs['old_flavor'], kwargs['new_flavor'], kwargs['service'], kwargs['region_id'])
                LOG.error(msg)
                raise exception.DuplicatedProduct(reason=msg)

            try:
                sub = model_query(context, sa_models.Subscription, session=session).\
                    filter_by(order_id=kwargs['order_id']).\
                    filter_by(product_id=old_product.product_id).\
                    filter_by(type=kwargs['change_to']).\
                    with_lockmode('update').one()
            except NoResultFound:
                msg = "Subscription with order_id(%s), product_id(%s), type(%s) not found" % \
                        (kwargs['order_id'], old_product.product_id, kwargs['change_to'])
                LOG.error(msg)
                return None
            sub.unit_price = new_product.unit_price
            sub.product_id = new_product.product_id

    @require_context
    def get_subscriptions_by_order_id(self, context, order_id, type=None):
        query = model_query(context, sa_models.Subscription).\
            filter_by(order_id=order_id)
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
                                        limit=None, offset=None, sort_key=None,
                                        sort_dir=None):
        query = model_query(context, sa_models.Subscription).\
            filter_by(product_id=product_id)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Subscription.created_at >= start_time)
            query = query.filter(sa_models.Subscription.created_at < end_time)

        ref = paginate_query(context, sa_models.Subscription,
                             limit=limit, offset=offset,
                             sort_key=sort_key, sort_dir=sort_dir,
                             query=query)

        return (self._row_to_db_subscription_model(r) for r in ref)

    @require_context
    def get_latest_bill(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Bill)
            query = query.filter_by(order_id=order_id)
            ref = query.order_by(desc(sa_models.Bill.id)).all()[0]
        return self._row_to_db_bill_model(ref)

    @require_context
    def get_owed_bills(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Bill)
            query = query.filter_by(order_id=order_id)
            query = query.filter_by(status=const.BILL_OWED)
            ref = query.order_by(desc(sa_models.Bill.id)).all()
        return (self._row_to_db_bill_model(r) for r in ref)

    @require_context
    def get_bills_by_order_id(self, context, order_id, type=None,
                              start_time=None, end_time=None,
                              limit=None, offset=None, sort_key=None,
                              sort_dir=None):
        query = model_query(context, sa_models.Bill).\
            filter_by(order_id=order_id)
        if type:
            query = query.filter_by(type=type)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)

        result = paginate_query(context, sa_models.Bill,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_bill_model(r) for r in result)

    @require_context
    def get_bills(self, context, start_time=None, end_time=None,
                  project_id=None, type=None, limit=None, offset=None,
                  sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Bill)

        if type:
            query = query.filter_by(type=type)

        if project_id:
            if not context.is_admin:
                raise exception.NotAuthorized()
            query = query.filter_by(project_id=project_id)

        query = query.filter_by(status=const.BILL_PAYED)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)

        result = paginate_query(context, sa_models.Bill,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_bill_model(b) for b in result)

    @require_context
    def get_bills_count(self, context, order_id=None, project_id=None,
                        type=None, start_time=None, end_time=None):
        query = model_query(context, sa_models.Bill,
                            func.count(sa_models.Bill.id).label('count'))
        if order_id:
            query = query.filter_by(order_id=order_id)
        if project_id:
            if not context.is_admin:
                raise exception.NotAuthorized()
            query = query.filter_by(project_id=project_id)
        if type:
            query = query.filter_by(type=type)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)

        return query.one().count or 0

    @require_context
    def get_bills_sum(self, context, region_id=None, start_time=None, end_time=None,
                      order_id=None, project_id=None, type=None):
        query = model_query(context, sa_models.Bill,
                            func.sum(sa_models.Bill.total_price).label('sum'))
        if order_id:
            query = query.filter_by(order_id=order_id)
        if project_id:
            if not context.is_admin:
                raise exception.NotAuthorized()
            query = query.filter_by(project_id=project_id)
        if type:
            query = query.filter_by(type=type)
        if region_id:
            query = query.filter_by(region_id=region_id)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)

        return query.one().sum or 0

    @require_context
    def get_bills_count_and_sum(self, context, order_id=None, project_id=None,
                                type=None, start_time=None, end_time=None):
        query = model_query(context, sa_models.Bill,
                            func.count(sa_models.Bill.id).label('count'),
                            func.sum(sa_models.Bill.total_price).label('sum'))
        if order_id:
            query = query.filter_by(order_id=order_id)
        if project_id:
            if not context.is_admin:
                raise exception.NotAuthorized()
            query = query.filter_by(project_id=project_id)
        if type:
            query = query.filter_by(type=type)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)

        return query.one().count or 0, query.one().sum or 0

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

    @require_admin_context
    def get_accounts(self, context, limit=None, offset=None,
                     sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Account)

        result = paginate_query(context, sa_models.Account,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_account_model(r) for r in result)

    @require_admin_context
    def get_accounts_count(self, context):
        query = model_query(context, sa_models.Account,
                            func.count(sa_models.Account.id).label('count'))
        return query.one().count or 0

    @require_admin_context
    def update_account(self, context, project_id, **data):
        session = db_session.get_session()
        with session.begin():
            account = model_query(context, sa_models.Account, session=session).\
                filter_by(project_id=project_id).\
                with_lockmode('update').one()

            account.balance += data['value']

            if account.balance >= 0:
                account.owed = False

            if not data.get('charge_time'):
                charge_time = datetime.datetime.utcnow()
            else:
                charge_time = timeutils.parse_isotime(data['charge_time'])

            charge = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                      user_id=account.user_id,
                                      project_id=project_id,
                                      currency=data.get('currency') or 'CNY',
                                      value=data['value'],
                                      type=data.get('type'),
                                      come_from=data.get('come_from'),
                                      charge_time=charge_time)
            session.add(charge)

        return self._row_to_db_charge_model(charge)

    @require_context
    def get_charges(self, context, project_id=None, start_time=None, end_time=None,
                    limit=None, offset=None, sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.Charge)

        if project_id:
            query = query.filter_by(project_id=project_id)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Charge.charge_time >= start_time,
                                 sa_models.Charge.charge_time < end_time)

        result = paginate_query(context, sa_models.Charge,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_charge_model(r) for r in result)

    @require_context
    def get_charges_price_and_count(self, context, project_id=None,
                                    start_time=None, end_time=None):
        query = model_query(context, sa_models.Charge,
                            func.count(sa_models.Charge.id).label('count'),
                            func.sum(sa_models.Charge.value).label('sum'))

        if project_id:
            query = query.filter_by(project_id=project_id)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Charge.charge_time >= start_time,
                                 sa_models.Charge.charge_time < end_time)

        return query.one().sum or 0, query.one().count or 0

    @require_admin_context
    def create_bill(self, context, order_id, action_time=None, remarks=None, end_time=None):
        """There are three type of results:
        0, Create bill successfully, including account is owed and order is owed,
           or account is not owed and balance is greater than 0
        1, Suspend to create bill, but set order to owed, that is account is owed
           and order is not owed
        2, Create bill successfully, but set account to owed, that is account is not
           owed and balance is less than 0
        """
        session = db_session.get_session()
        result = {'type': 0, 'resource_owed': False}
        with session.begin():
            # Get order
            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=order_id).\
                with_lockmode('update').one()

            if order.status == const.STATE_CHANGING:
                return result

            # Create a bill
            if not action_time:
                action_time = order.cron_time

            now = timeutils.utcnow() + datetime.timedelta(
                    seconds=cfg.CONF.master.allow_delay_seconds)

            if action_time > now:
                LOG.warn('The action_time(%s) of the order(%s) if greater than utc now(%s)' %
                         (action_time, order_id, now))
                return result

            bill = sa_models.Bill(bill_id=uuidutils.generate_uuid(),
                                  start_time=action_time,
                                  end_time=end_time or action_time + datetime.timedelta(hours=1),
                                  type=order.type,
                                  status=const.BILL_PAYED,
                                  unit_price=order.unit_price,
                                  unit=order.unit,
                                  total_price=order.unit_price,
                                  order_id=order.order_id,
                                  resource_id=order.resource_id,
                                  remarks=remarks,
                                  user_id=order.user_id,
                                  project_id=order.project_id,
                                  region_id=order.region_id)
            session.add(bill)

            # if end_time is specified, it means the action is stopping the instance,
            # so there is no need to update account, creating a new bill is enough.
            if end_time:
                return result

            # Update the order
            cron_time = action_time + datetime.timedelta(hours=1)
            order.total_price += order.unit_price
            order.cron_time = cron_time
            order.updated_at = datetime.datetime.utcnow()

            # Update subscriptions
            subs = model_query(context, sa_models.Subscription, session=session).\
                filter_by(order_id=order_id).\
                filter_by(type=order.status).\
                all()

            for sub in subs:
                sub_single_price = sub.unit_price * sub.quantity
                sub_single_price = gringutils._quantize_decimal(sub_single_price)
                sub.total_price += sub_single_price
                sub.updated_at = datetime.datetime.utcnow()

                # update product
                product = model_query(context, sa_models.Product, session=session).\
                    filter_by(product_id=sub.product_id).\
                    filter_by(deleted=False).\
                    one()
                product.total_price += sub_single_price

            # Update account
            account = model_query(context, sa_models.Account, session=session).\
                filter_by(project_id=order.project_id).\
                with_lockmode('update').one()

            account.balance -= order.unit_price
            account.consumption += order.unit_price
            account.updated_at = datetime.datetime.utcnow()

            result['user_id'] = account.user_id
            result['project_id'] = account.project_id
            result['resource_type'] = order.type
            result['resource_id'] = order.resource_id
            result['region_id'] = order.region_id
            result['resource_owed'] = False

            if not cfg.CONF.enable_owe:
                return result

            # Account is owed
            if self._check_if_account_first_owed(account):
                account.owed = True
                result['type'] = 1
            # Order is owed
            elif self._check_if_order_first_owed(account, order):
                reserved_days = gringutils.cal_reserved_days(account.level)
                date_time = datetime.datetime.utcnow() + datetime.timedelta(days=reserved_days)
                order.date_time = date_time
                order.owed = True
                result['type'] = 2
                result['date_time'] = date_time
            # Account is charged but order is still owed
            elif self._check_if_account_charged(account, order):
                result['type'] = 3
                order.owed = False
                order.date_time = None

            if order.owed:
                result['resource_owed'] = True

            return result

    def _check_if_account_charged(self, account, order):
        if not account.owed and order.owed:
            return True
        return False

    def _check_if_order_first_owed(self, account, order):
        if account.owed and not order.owed:
            return True
        return False

    def _check_if_account_first_owed(self, account):
        if account.level == 9:
            return False
        if not account.owed and account.balance <= 0:
            return True
        else:
            return False

    @require_admin_context
    def close_bill(self, context, order_id, action_time):
        session = db_session.get_session()
        result = {'type': 0, 'resource_owed': False}
        with session.begin():
            # get order
            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=order_id).\
                with_lockmode('update').one()

            # Update the latest bill
            try:
                bill = model_query(context, sa_models.Bill, session=session).\
                    filter_by(order_id=order_id).\
                    order_by(desc(sa_models.Bill.id)).all()[0]
            except IndexError:
                LOG.warning('There is no latest bill for the order: %s' % order_id)
                return result

            if action_time >= bill.end_time:
                return result

            delta = timeutils.delta_seconds(action_time, bill.end_time) / 3600.0
            delta = gringutils._quantize_decimal(delta)

            more_fee = gringutils._quantize_decimal(delta * order.unit_price)
            bill.end_time = action_time
            bill.total_price -= more_fee
            bill.updated_at = datetime.datetime.utcnow()

            # Update the order
            order.total_price -= more_fee
            order.cron_time = None
            order.status = const.STATE_CHANGING
            order.updated_at = datetime.datetime.utcnow()

            # Update subscriptions
            subs = model_query(context, sa_models.Subscription, session=session).\
                filter_by(order_id=order_id).\
                filter_by(type=order.status).\
                all()

            for sub in subs:
                sub_more_fee = gringutils._quantize_decimal(delta * sub.unit_price * sub.quantity)
                sub.total_price -= sub_more_fee
                sub.updated_at = datetime.datetime.utcnow()

                # update product
                product = model_query(context, sa_models.Product, session=session).\
                    filter_by(product_id=sub.product_id).\
                    filter_by(deleted=False).\
                    one()
                product.total_price -= sub_more_fee

            # Update the account
            account = model_query(context, sa_models.Account, session=session).\
                filter_by(project_id=order.project_id).\
                with_lockmode('update').\
                one()
            account.balance += more_fee
            account.consumption -= more_fee
            account.updated_at = datetime.datetime.utcnow()

            if not cfg.CONF.enable_owe:
                return result

            if account.owed and account.balance > 0:
                result['type'] = 1
                result['user_id'] = account.user_id
                result['project_id'] = account.project_id
                account.owed = False

            if order.owed and action_time < order.date_time:
                result['resource_owed'] = True
                result['resource_id'] = order.resource_id

            return result


    @require_admin_context
    def fix_order(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=order_id).\
                with_lockmode('update').one()
            bills = model_query(context, sa_models.Bill, session=session).\
                filter_by(order_id=order_id).all()
            account = model_query(context, sa_models.Account, session=session).\
                filter_by(project_id=order.project_id).\
                with_lockmode('update').one()

            one_hour_later = timeutils.utcnow() + datetime.timedelta(hours=1)
            more_fee = 0

            for bill in bills:
                if bill.end_time > one_hour_later:
                    more_fee += bill.total_price
                    session.delete(bill)

            bill = model_query(context, sa_models.Bill, session=session).\
                filter_by(order_id=order_id).\
                order_by(desc(sa_models.Bill.id)).all()[0]

            order.cron_time = bill.end_time
            order.total_price -= more_fee

            account.balance += more_fee
            account.consumption -= more_fee


    @require_admin_context
    def create_precharge(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            for i in xrange(kwargs['number']):
                while True:
                    try:
                        session.add(sa_models.PreCharge(code=gringutils.random_str(),
                                                        price=kwargs['price'],
                                                        expired_at=kwargs['expired_at']))
                    except db_exception.DBDuplicateEntry:
                        continue
                    else:
                        break

    @require_context
    def get_precharges(self, context, project_id, limit=None, offset=None,
                       sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.PreCharge).\
                filter_by(deleted=False)

        if project_id:
            query = query.filter_by(project_id=project_id)

        result = paginate_query(context, sa_models.PreCharge,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_precharge_model(r) for r in result)

    @require_context
    def get_precharge_by_code(self, context, code):
        try:
            precharge = model_query(context, sa_models.PreCharge).\
                    filter_by(deleted=False).\
                    filter_by(code=code).one()
        except NoResultFound:
            LOG.warning('The precharge %s not found' % kwargs['code'])
            raise exception.PreChargeNotFound(precharge_code=kwargs['code'])
        return self._row_to_db_precharge_model(precharge)

    @require_admin_context
    def dispatch_precharge(self, context, code, remarks=None):
        session = db_session.get_session()
        with session.begin():
            try:
                precharge = model_query(context, sa_models.PreCharge, session=session).\
                        filter_by(deleted=False).\
                        filter_by(code=code).one()
            except NoResultFound:
                raise exception.PreChargeNotFound(precharge_code=code)
            precharge.dispatched = True
            precharge.remarks = remarks

        return self._row_to_db_precharge_model(precharge)

    @require_context
    def use_precharge(self, context, code, user_id=None, project_id=None):
        session = db_session.get_session()
        with session.begin():
            try:
                precharge = session.query(sa_models.PreCharge).\
                        filter_by(deleted=False).\
                        filter_by(code=code).one()
            except NoResultFound:
                raise exception.PreChargeNotFound(precharge_code=code)

            if precharge.used:
                raise exception.PreChargeHasUsed(precharge_code=code)

            now = datetime.datetime.utcnow()
            if precharge.expired_at < now:
                raise exception.PreChargeHasExpired(precharge_code=code)

            # Update account
            try:
                account = model_query(context, sa_models.Account, session=session).\
                    filter_by(project_id=project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.AccountNotFound(project_id=project_id)

            account.balance += precharge.price
            if account.balance >= 0:
                account.owed = False

            # Add charge records
            charge_time = datetime.datetime.utcnow()
            charge = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                      user_id=account.user_id,
                                      project_id=project_id,
                                      currency='CNY',
                                      value=precharge.price,
                                      type='coupon',
                                      come_from="coupon",
                                      charge_time=charge_time)
            session.add(charge)

            # Update precharge
            precharge.used = True
            precharge.user_id = user_id
            precharge.project_id = project_id

        return self._row_to_db_precharge_model(precharge)

    @require_context
    def fix_resource(self, context, resource_id):
        session = db_session.get_session()
        with session.begin():
            query = session.query(sa_models.Order).\
                filter_by(resource_id=resource_id)
            orders = query.all()

            if len(orders) > 2:
                return

            for order in orders:
                if order.status != 'deleted':
                    new_order = order
                else:
                    old_order = order

            old_order.status = new_order.status
            old_order.unit_price = new_order.unit_price
            old_order.unit = new_order.unit

            if new_order.total_price > 0:
                account = session.query(sa_models.Account).\
                    filter_by(project_id=new_order.project_id).one()
                account.balance += new_order.total_price
                account.consumption -= new_order.total_price

            bills = session.query(sa_models.Bill).filter_by(order_id=new_order.order_id)
            for bill in bills:
                session.delete(bill)

            session.delete(new_order)

    @require_context
    def fix_stopped_order(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            order = session.query(sa_models.Order).filter_by(order_id=order_id).one()
            bills = session.query(sa_models.Bill).filter_by(order_id=order_id).\
                    order_by(desc(sa_models.Bill.id)).all()
            account = session.query(sa_models.Account).filter_by(project_id=order.project_id).one()

            more_fee = gringutils._quantize_decimal('0')
            add_new_bill = True
            cron_time = None

            for bill in bills:
                if bill.total_price == gringutils._quantize_decimal('0.0020') or \
                        bill.total_price == gringutils._quantize_decimal('0.0400') or \
                        bill.total_price == gringutils._quantize_decimal('0.0800'):
                    more_fee += bill.total_price
                if bill.total_price == gringutils._quantize_decimal('0.0000'):
                    add_new_bill = False
                    cron_time = bill.end_time
                    break
                if bill.total_price != gringutils._quantize_decimal('0.0020') or \
                        bill.total_price != gringutils._quantize_decimal('0.0400') or \
                        bill.total_price != gringutils._quantize_decimal('0.0800') or \
                        bill.remarks == 'Sytstem Adjust':
                    start_time = bill.end_time
                    cron_time = bill.end_time + datetime.timedelta(days=30)
                    break
                session.delete(bill)

            if add_new_bill:
                bill = sa_models.Bill(bill_id=uuidutils.generate_uuid(),
                                      start_time=start_time,
                                      end_time=start_time + datetime.timedelta(days=30),
                                      type=order.type,
                                      status=const.BILL_PAYED,
                                      unit_price=gringutils._quantize_decimal('0.0000'),
                                      unit=order.unit,
                                      total_price=gringutils._quantize_decimal('0.0000'),
                                      order_id=order.order_id,
                                      resource_id=order.resource_id,
                                      remarks='Instance Has Been Stopped',
                                      user_id=order.user_id,
                                      project_id=order.project_id,
                                      region_id=order.region_id)
                session.add(bill)

            order.unit_price = gringutils._quantize_decimal('0.0000')
            order.cron_time = cron_time

            order.total_price -= more_fee
            account.balance += more_fee
            account.consumption -= more_fee
