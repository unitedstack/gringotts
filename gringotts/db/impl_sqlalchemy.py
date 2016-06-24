"""SQLAlchemy storage backend."""

from __future__ import absolute_import
import datetime
import functools
import os

from oslo_config import cfg
from sqlalchemy import desc, asc
from sqlalchemy import func
from sqlalchemy import not_
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
import wsme

from gringotts import constants as const
from gringotts import context as gring_context
from gringotts.db import base
from gringotts.db import models as db_models
from gringotts.db.sqlalchemy import migration
from gringotts.db.sqlalchemy import models as sa_models
from gringotts import exception
from gringotts.openstack.common.db import exception as db_exception
from gringotts.openstack.common.db.sqlalchemy import session as db_session
from gringotts.openstack.common import jsonutils
from gringotts.openstack.common import log
from gringotts.openstack.common import timeutils
from gringotts.openstack.common import uuidutils
from gringotts.price import pricing
from gringotts import utils as gringutils


LOG = log.getLogger(__name__)
cfg.CONF.import_opt('enable_owe', 'gringotts.master.service')
cfg.CONF.import_opt('allow_delay_seconds',
                    'gringotts.master.service', group='master')

get_session = db_session.get_session
quantize = gringutils._quantize_decimal


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


def require_domain_context(f):
    """Decorator to require *any* domain or admin context.
    The second argument to the wrapped function must be the context.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        gring_context.require_domain_context(args[1])
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

    if (gring_context.is_domain_owner_context(context) and
            hasattr(model, 'domain_id')):
        query = query.filter_by(domain_id=context.domain_id)
    if gring_context.is_user_context(context) and hasattr(model, 'user_id'):
        query = query.filter_by(user_id=context.user_id)
    return query


def paginate_query(context, model, limit=None, offset=None,
                   sort_key=None, sort_dir=None, query=None):
    if not query:
        query = model_query(context, model)
    sort_keys = ['id']
    # support for multiple sort_key
    keys = []
    if sort_key:
        keys = sort_key.split(',')
    for k in keys:
        k = k.strip()
        if k and k not in sort_keys:
            sort_keys.insert(0, k)
    query = _paginate_query(query, model, limit, sort_keys,
                            offset=offset, sort_dir=sort_dir)
    return query.all()


def _paginate_query(query, model, limit, sort_keys, offset=None,
                    sort_dir=None, sort_dirs=None):
    if 'id' not in sort_keys:
        # TODO(justinsb): If this ever gives a false-positive, check
        # the actual primary key, rather than assuming its id
        LOG.warn('Id not in sort_keys; is sort_keys unique?')

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
            raise ValueError("Unknown sort direction, "
                             "must be 'desc' or 'asc'")
        try:
            sort_key_attr = getattr(model, current_sort_key)
        except AttributeError:
            raise exception.Invalid()
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
        for table in reversed(sa_models.Base.metadata.sorted_tables):
            engine.execute(table.delete())

    @staticmethod
    def _row_to_db_product_model(row):
        return db_models.Product(product_id=row.product_id,
                                 name=row.name,
                                 service=row.service,
                                 region_id=row.region_id,
                                 description=row.description,
                                 deleted=row.deleted,
                                 unit_price=row.unit_price,
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
                               domain_id=row.domain_id,
                               owed=row.owed,
                               charged=row.charged,
                               renew=row.renew,
                               renew_method=row.renew_method,
                               renew_period=row.renew_period,
                               created_at=row.created_at,
                               updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_subscription_model(row):
        return db_models.Subscription(subscription_id=row.subscription_id,
                                      type=row.type,
                                      product_id=row.product_id,
                                      unit_price=row.unit_price,
                                      quantity=row.quantity,
                                      order_id=row.order_id,
                                      user_id=row.user_id,
                                      project_id=row.project_id,
                                      region_id=row.region_id,
                                      domain_id=row.domain_id,
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
                              domain_id=row.domain_id,
                              created_at=row.created_at,
                              updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_account_model(row):
        return db_models.Account(user_id=row.user_id,
                                 domain_id=row.domain_id,
                                 balance=row.balance,
                                 frozen_balance=row.frozen_balance,
                                 consumption=row.consumption,
                                 level=row.level,
                                 owed=row.owed,
                                 deleted=row.deleted,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at,
                                 deleted_at=row.deleted_at)

    @staticmethod
    def _row_to_db_project_model(row):
        return db_models.Project(user_id=row.user_id,
                                 project_id=row.project_id,
                                 domain_id=row.domain_id,
                                 consumption=row.consumption,
                                 created_at=row.created_at,
                                 updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_charge_model(row):
        return db_models.Charge(charge_id=row.charge_id,
                                user_id=row.user_id,
                                domain_id=row.domain_id,
                                value=row.value,
                                type=row.type,
                                come_from=row.come_from,
                                trading_number=row.trading_number,
                                operator=row.operator,
                                remarks=row.remarks,
                                charge_time=row.charge_time,
                                created_at=row.created_at,
                                updated_at=row.updated_at)

    @staticmethod
    def _row_to_db_deduct_model(row):
        return db_models.Deduct(req_id=row.req_id,
                                deduct_id=row.deduct_id,
                                type=row.type,
                                money=row.money,
                                remark=row.remark,
                                order_id=row.order_id,
                                created_at=row.created_at)

    @staticmethod
    def _row_to_db_precharge_model(row):
        return db_models.PreCharge(code=row.code,
                                   price=row.price,
                                   used=row.used,
                                   dispatched=row.dispatched,
                                   deleted=row.deleted,
                                   operator_id=row.operator_id,
                                   user_id=row.user_id,
                                   domain_id=row.domain_id,
                                   created_at=row.created_at,
                                   deleted_at=row.deleted_at,
                                   expired_at=row.expired_at,
                                   remarks=row.remarks)

    def _product_object_to_dict(self, product):
        p_dict = product.as_dict()
        try:
            p_dict['unit_price'] = p_dict['unit_price'].as_dict()
            for key in ['price', 'monthly_price', 'yearly_price']:
                if key in p_dict['unit_price']:
                    p_dict['unit_price'][key] = \
                        p_dict['unit_price'][key].as_dict()
                    new_segmented = []
                    base_price = p_dict['unit_price'][key]['base_price']
                    p_dict['unit_price'][key]['base_price'] = str(base_price)
                    for seg in p_dict['unit_price'][key]['segmented']:
                        new_seg = seg.as_dict()
                        new_seg['price'] = str(new_seg['price'])
                        new_segmented.append(new_seg)
                    p_dict['unit_price'][key]['segmented'] = new_segmented
            p_dict['unit_price'] = jsonutils.dumps(p_dict['unit_price'])
        except KeyError:
            LOG.error("The unit_price lack of some key words.")
            return None

        return p_dict

    def create_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            product_ref = sa_models.Product()
            product_ref.update(self._product_object_to_dict(product))
            session.add(product_ref)
        return self._row_to_db_product_model(product_ref)

    def get_products_count(self, context, filters=None):
        query = get_session().query(
            sa_models.Product,
            func.count(sa_models.Product.id).label('count'))
        if 'name' in filters:
            query = query.filter_by(name=filters['name'])
        if 'service' in filters:
            query = query.filter_by(service=filters['service'])
        if 'region_id' in filters:
            query = query.filter_by(region_id=filters['region_id'])
        query = query.filter_by(deleted=False)

        return query.one().count or 0

    def get_products(self, context, filters=None, read_deleted=False,
                     limit=None, offset=None, sort_key=None,
                     sort_dir=None):
        query = get_session().query(sa_models.Product)
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

    def get_product(self, context, product_id):
        query = model_query(context, sa_models.Product).\
            filter_by(product_id=product_id).\
            filter_by(deleted=False)
        try:
            ref = query.one()
        except NoResultFound:
            raise exception.ProductIdNotFound(product_id)
        return self._row_to_db_product_model(ref)

    def delete_product(self, context, product_id):
        product = self.get_product(context, product_id)
        product.deleted = True

        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product.product_id)
            query.update(product.as_dict(),
                         synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_product_model(ref)

    def update_product(self, context, product):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Product)
            query = query.filter_by(product_id=product.product_id)
            query.update(self._product_object_to_dict(product), synchronize_session='fetch')
            ref = query.one()
        return self._row_to_db_product_model(ref)

    def reset_product(self, context, product, excluded_projects=[]):
        session = db_session.get_session()
        with session.begin():
            # get all active orders in specified region
            orders = session.query(sa_models.Order).\
                filter_by(region_id=product.region_id).\
                filter(not_(sa_models.Order.status == const.STATE_DELETED)).\
                filter(sa_models.Order.project_id.notin_(excluded_projects)).\
                all()
            for order in orders:
                # get all subscriptions of this order that belongs to
                # this product
                p_subs = session.query(sa_models.Subscription).\
                    filter_by(order_id=order.order_id).\
                    filter_by(product_id=product.product_id).\
                    all()
                # update subscription's unit price
                for s in p_subs:
                    s.unit_price = product.unit_price

                # update order's unit price
                t_subs = session.query(sa_models.Subscription).\
                    filter_by(order_id=order.order_id).\
                    filter_by(type=order.status).\
                    all()
                unit_price = 0
                for s in t_subs:
                    price_data = None
                    if s.unit_price:
                        try:
                            unit_price_data = jsonutils.loads(s.unit_price)
                            price_data = unit_price_data.get('price', None)
                        except (Exception):
                            pass

                    unit_price += pricing.calculate_price(
                        s.quantity, price_data)

                if order.unit_price != 0:
                    order.unit_price = unit_price

    def get_product_by_name(self, context, product_name, service, region_id):
        try:
            product = model_query(context, sa_models.Product).\
                filter_by(name=product_name).\
                filter_by(service=service).\
                filter_by(region_id=region_id).\
                filter_by(deleted=False).\
                one()
        except NoResultFound:
            msg = "Product with name(%s) within service(%s) in region_id(%s) "
            "not found" % (product_name, service, region_id)
            LOG.warning(msg)
            return None
        except MultipleResultsFound:
            msg = "Duplicated products with name(%s) within service(%s) in "
            "region_id(%s)" % (product_name, service, region_id)
            LOG.error(msg)
            raise exception.DuplicatedProduct(reason=msg)

        return self._row_to_db_product_model(product)

    @require_admin_context
    def create_order(self, context, **order):
        session = db_session.get_session()
        with session.begin():
            # get project
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=order['project_id']).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s',
                          order['project_id'])
                raise exception.ProjectNotFound(project_id=order['project_id'])

            if not order['unit'] or order['unit'] == 'hour':
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
                    user_id=project.user_id,  # the payer
                    project_id=order['project_id'],
                    domain_id=project.domain_id,
                    region_id=order['region_id'],
                )
                session.add(ref)
            else:
                start_time = timeutils.utcnow()
                months = gringutils.to_months(order['unit'], order['period'])
                end_time = gringutils.add_months(start_time, months)
                total_price = order['unit_price'] * order['period']
                if order['period'] > 1:
                    remarks = "Renew for %s %ss" % \
                        (order['period'], order['unit'])
                else:
                    remarks = "Renew for %s %s" % \
                        (order['period'], order['unit'])

                # add a bill
                bill = sa_models.Bill(
                    bill_id=uuidutils.generate_uuid(),
                    start_time=start_time,
                    end_time=end_time,
                    type=order['type'],
                    status=const.BILL_PAYED,
                    unit_price=order['unit_price'],
                    unit=order['unit'],
                    total_price=total_price,
                    order_id=order['order_id'],
                    resource_id=order['resource_id'],
                    remarks=remarks,
                    user_id=project.user_id,
                    project_id=order['project_id'],
                    region_id=order['region_id'],
                    domain_id=project.domain_id)
                session.add(bill)

                # add an order
                ref = sa_models.Order(
                    order_id=order['order_id'],
                    resource_id=order['resource_id'],
                    resource_name=order['resource_name'],
                    type=order['type'],
                    unit_price=order['unit_price'],
                    unit=order['unit'],
                    total_price=total_price,
                    cron_time=end_time,
                    date_time=None,
                    status=order['status'],
                    user_id=project.user_id,  # the payer
                    project_id=order['project_id'],
                    domain_id=project.domain_id,
                    region_id=order['region_id'],
                )
                if order['renew']:
                    ref.renew = order['renew']
                    ref.renew_method = order['unit']
                    ref.renew_period = order['period']
                session.add(ref)

                # Update project and user_project
                try:
                    user_project = model_query(
                        context, sa_models.UserProject, session=session).\
                        filter_by(project_id=order['project_id']).\
                        filter_by(user_id=project.user_id).\
                        with_lockmode('update').one()
                except NoResultFound:
                    LOG.error('Could not find the relationship between '
                              'user(%s) and project(%s)',
                              project.user_id, order['project_id'])
                    raise exception.UserProjectNotFound(
                        user_id=project.user_id,
                        project_id=order['project_id'])

                project.consumption += total_price
                project.updated_at = datetime.datetime.utcnow()
                user_project.consumption += total_price
                user_project.updated_at = datetime.datetime.utcnow()

                # Update account
                try:
                    account = model_query(
                        context, sa_models.Account, session=session).\
                        filter_by(user_id=project.user_id).\
                        with_lockmode('update').one()
                except NoResultFound:
                    LOG.error('Could not find the account: %s',
                              project.user_id)
                    raise exception.AccountNotFound(user_id=project.user_id)

                account.frozen_balance -= total_price
                account.consumption += total_price
                account.updated_at = datetime.datetime.utcnow()

        return self._row_to_db_order_model(ref)

    @require_admin_context
    def update_order(self, context, **kwargs):
        """Change unit price of this order
        """
        session = db_session.get_session()
        with session.begin():
            # Get subs of this order
            subs = model_query(
                context, sa_models.Subscription, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                filter_by(type=kwargs['change_to']).\
                with_lockmode('read').all()

            # caculate new unit price
            unit_price = 0

            for sub in subs:
                price_data = None
                if sub.unit_price:
                    try:
                        unit_price_data = jsonutils.loads(sub.unit_price)
                        price_data = unit_price_data.get('price', None)
                    except (Exception):
                        pass

                unit_price += pricing.calculate_price(
                    sub.quantity, price_data)

            # update the order
            a_order = dict(unit_price=unit_price,
                           updated_at=datetime.datetime.utcnow())

            if kwargs['change_order_status']:
                a_order.update(
                    status=kwargs['first_change_to'] or kwargs['change_to'])
            if kwargs['cron_time']:
                a_order.update(cron_time=kwargs['cron_time'])

            model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                with_lockmode('update').\
                update(a_order)

    @require_admin_context
    def close_order(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            try:
                order = model_query(
                    context, sa_models.Order, session=session).\
                    filter_by(order_id=order_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.OrderNotFound(order_id=order_id)
            order.unit_price = quantize('0.0000')
            order.status = const.STATE_DELETED
            order.updated_at = datetime.datetime.utcnow()
        return self._row_to_db_order_model(order)

    @require_context
    def get_order_by_resource_id(self, context, resource_id):
        query = model_query(context, sa_models.Order).\
            filter_by(resource_id=resource_id)
        try:
            ref = query.one()
        except NoResultFound:
            LOG.warning('The order of the resource(%s) not found', resource_id)
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
                   user_id=None, project_ids=None, owed=None, resource_id=None,
                   bill_methods=None, read_deleted=True):
        """Get orders that have bills during start_time and end_time.
        If start_time is None or end_time is None, will ignore the datetime
        range, and return all orders
        """
        query = get_session().query(sa_models.Order)

        if type:
            query = query.filter_by(type=type)
        if status:
            query = query.filter_by(status=status)
        if resource_id:
            query = query.filter_by(resource_id=resource_id)
        if bill_methods:
            query = query.filter(sa_models.Order.unit.in_(bill_methods))
        if region_id:
            query = query.filter_by(region_id=region_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if project_ids is not None:
            query = query.filter(sa_models.Order.project_id.in_(project_ids))
        if owed is not None:
            query = query.filter_by(owed=owed)
        if not read_deleted:
            query = query.filter(
                not_(sa_models.Order.status == const.STATE_DELETED))

        if all([start_time, end_time]):
            query = query.join(
                sa_models.Bill,
                sa_models.Order.order_id == sa_models.Bill.order_id
            )
            query = query.filter(sa_models.Bill.start_time >= start_time,
                                 sa_models.Bill.start_time < end_time)
            query = query.group_by(sa_models.Bill.order_id)

        if with_count:
            total_count = len(query.all())

        result = paginate_query(context, sa_models.Order,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)
        rows = (self._row_to_db_order_model(o) for o in result)
        if with_count:
            return rows, total_count
        else:
            return rows

    @require_admin_context
    def get_active_order_count(self, context, region_id=None,
                               owed=None, type=None, bill_methods=None):
        query = model_query(context, sa_models.Order,
                            func.count(sa_models.Order.id).label('count'))
        if region_id:
            query = query.filter_by(region_id=region_id)
        if owed is not None:
            query = query.filter_by(owed=owed)
        if type:
            query = query.filter_by(type=type)
        if bill_methods:
            query = query.filter(sa_models.Order.unit.in_(bill_methods))

        query = query.filter(
            not_(sa_models.Order.status == const.STATE_DELETED)
        )
        if not owed:
            query = query.filter(
                not_(sa_models.Order.cron_time == None)  # noqa
            )
        return query.one().count or 0

    @require_admin_context
    def get_stopped_order_count(self, context, region_id=None,
                                owed=None, type=None, bill_methods=None):
        query = model_query(context, sa_models.Order,
                            func.count(sa_models.Order.id).label('count'))
        if region_id:
            query = query.filter_by(region_id=region_id)
        if owed is not None:
            query = query.filter_by(owed=owed)
        if type:
            query = query.filter_by(type=type)
        if bill_methods:
            query = query.filter(sa_models.Order.unit.in_(bill_methods))

        query = query.filter(sa_models.Order.status == const.STATE_STOPPED)
        query = query.filter(
            sa_models.Order.unit_price == quantize('0'))
        return query.one().count or 0

    @require_context
    def get_active_orders(self, context, type=None, limit=None, offset=None,
                          sort_key=None, sort_dir=None, region_id=None,
                          user_id=None, project_id=None, owed=None,
                          charged=None, within_one_hour=None,
                          bill_methods=None):
        """Get all active orders
        """
        query = get_session().query(sa_models.Order)

        if type:
            query = query.filter_by(type=type)
        if region_id:
            query = query.filter_by(region_id=region_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if owed is not None:
            query = query.filter_by(owed=owed)
        if charged:
            query = query.filter_by(charged=charged)
        if bill_methods:
            query = query.filter(sa_models.Order.unit.in_(bill_methods))

        if within_one_hour:
            one_hour_later = timeutils.utcnow() + datetime.timedelta(hours=1)
            query = query.filter(sa_models.Order.cron_time < one_hour_later)

        query = query.filter(
            not_(sa_models.Order.status == const.STATE_DELETED))

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
                product = model_query(
                    context, sa_models.Product, session=session).filter_by(
                        name=subscription['product_name']).filter_by(
                            service=subscription['service']).filter_by(
                                region_id=subscription['region_id']).\
                    filter_by(deleted=False).with_lockmode('update').one()
            except NoResultFound:
                msg = 'Product with name(%s) within service(%s) in' \
                    ' region_id(%s) not found' % (
                        subscription['product_name'], subscription['service'],
                        subscription['region_id'])
                LOG.warning(msg)
                return None
            except MultipleResultsFound:
                msg = 'Duplicated products with name(%s) within' \
                    'service(%s) in region_id(%s)' % (
                        subscription['product_name'], subscription['service'],
                        subscription['region_id'])
                LOG.error(msg)
                raise exception.DuplicatedProduct(reason=msg)

            quantity = subscription['resource_volume']
            project = self.get_project(context, subscription['project_id'])

            subscription = sa_models.Subscription(
                subscription_id=uuidutils.generate_uuid(),
                type=subscription['type'],
                product_id=product.product_id,
                unit_price=product.unit_price,
                order_id=subscription['order_id'],
                user_id=subscription['user_id'],
                project_id=subscription['project_id'],
                region_id=subscription['region_id'],
                domain_id=project.domain_id,
            )

            session.add(subscription)

        return self._row_to_db_subscription_model(subscription)

    def update_subscription(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            subs = model_query(
                context, sa_models.Subscription, session=session).\
                filter_by(order_id=kwargs['order_id']).\
                filter_by(type=kwargs['change_to']).\
                with_lockmode('update').all()

            for sub in subs:
                sub.quantity = kwargs['quantity']

    def update_flavor_subscription(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            try:
                if kwargs['old_flavor']:
                    old_product = model_query(
                        context, sa_models.Product, session=session).\
                        filter_by(name=kwargs['old_flavor']).\
                        filter_by(service=kwargs['service']).\
                        filter_by(region_id=kwargs['region_id']).\
                        filter_by(deleted=False).\
                        with_lockmode('update').one()
                new_product = model_query(
                    context, sa_models.Product, session=session).\
                    filter_by(name=kwargs['new_flavor']).\
                    filter_by(service=kwargs['service']).\
                    filter_by(region_id=kwargs['region_id']).\
                    filter_by(deleted=False).\
                    with_lockmode('update').one()
            except NoResultFound:
                msg = "Product with name(%s/%s) within service(%s) in "
                "region_id(%s) not found" % \
                    (kwargs['old_flavor'], kwargs['new_flavor'],
                     kwargs['service'], kwargs['region_id'])
                LOG.error(msg)
                return None
            except MultipleResultsFound:
                msg = "Duplicated products with name(%s/%s) within "
                "service(%s) in region_id(%s)" % \
                    (kwargs['old_flavor'], kwargs['new_flavor'],
                     kwargs['service'], kwargs['region_id'])
                LOG.error(msg)
                raise exception.DuplicatedProduct(reason=msg)

            try:
                if kwargs['old_flavor']:
                    sub = model_query(
                        context, sa_models.Subscription, session=session).\
                        filter_by(order_id=kwargs['order_id']).\
                        filter_by(product_id=old_product.product_id).\
                        filter_by(type=kwargs['change_to']).\
                        with_lockmode('update').one()
                else:
                    subs = model_query(
                        context, sa_models.Subscription, session=session).\
                        filter_by(order_id=kwargs['order_id']).\
                        filter_by(type=kwargs['change_to']).\
                        all()
                    sub = None
                    for s in subs:
                        p = model_query(
                            context, sa_models.Product, session=session).\
                            filter_by(product_id=s.product_id).one()
                        if p.name.startswith('instance'):
                            sub = s
                            break
                    if not sub:
                        return None
            except NoResultFound:
                msg = "Subscription with order_id(%s), type(%s) not found" % \
                    (kwargs['order_id'], kwargs['change_to'])
                LOG.error(msg)
                return None
            sub.unit_price = new_product.unit_price
            sub.product_id = new_product.product_id

    @require_context
    def get_subscriptions_by_order_id(self, context, order_id, user_id=None,
                                      type=None, product_id=None):
        query = model_query(context, sa_models.Subscription).\
            filter_by(order_id=order_id)
        if type:
            query = query.filter_by(type=type)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if product_id:
            query = query.filter_by(product_id=product_id)
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
            query = query.filter(
                sa_models.Subscription.created_at >= start_time)
            query = query.filter(
                sa_models.Subscription.created_at < end_time)

        ref = paginate_query(context, sa_models.Subscription,
                             limit=limit, offset=offset,
                             sort_key=sort_key, sort_dir=sort_dir,
                             query=query)

        return (self._row_to_db_subscription_model(r) for r in ref)

    @require_context
    def get_bill(self, context, bill_id):
        session = db_session.get_session()
        with session.begin():
            query = model_query(context, sa_models.Bill)
            ref = query.filter_by(bill_id=bill_id).one()
        return self._row_to_db_bill_model(ref)

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
        query = get_session().query(sa_models.Bill).\
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
        query = get_session().query(
            sa_models.Bill,
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
    def get_bills_sum(self, context, region_id=None, start_time=None,
                      end_time=None, order_id=None, user_id=None,
                      project_id=None, type=None):
        query = get_session().query(
            sa_models.Bill,
            func.sum(sa_models.Bill.total_price).label('sum'))

        if order_id:
            query = query.filter_by(order_id=order_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if project_id:
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

    def create_account(self, context, account):
        session = db_session.get_session()
        with session.begin():
            account_ref = sa_models.Account()
            account_ref.update(account.as_dict())
            session.add(account_ref)
        return self._row_to_db_account_model(account_ref)

    @require_context
    def get_account(self, context, user_id, project_id=None):
        if project_id:
            query = get_session().query(sa_models.Account).\
                filter_by(project_id=project_id)
        else:
            query = get_session().query(sa_models.Account).\
                filter_by(user_id=user_id)
        try:
            ref = query.one()
        except NoResultFound:
            raise exception.AccountNotFound(user_id=user_id)
        return self._row_to_db_account_model(ref)

    def delete_account(self, context, user_id):
        """delete the account and projects"""

        session = db_session.get_session()
        with session.begin():
            try:
                account = session.query(sa_models.Account).\
                    filter_by(user_id=user_id).one()
            except NoResultFound:
                raise exception.AccountNotFound(user_id=user_id)

            # delete the account
            session.delete(account)

            # delete the projects which are related to the account
            projects = session.query(sa_models.Project).\
                filter_by(user_id=user_id).all()
            for project in projects:
                session.delete(project)

            # delete the user_projects which were related to the account
            user_projects = session.query(sa_models.UserProject).\
                filter_by(user_id=user_id).all()
            for user_project in user_projects:
                session.delete(user_project)

    def get_invitees(self, context, inviter, limit=None, offset=None):
        query = get_session().query(sa_models.Account).\
            filter_by(inviter=inviter)

        total_count = len(query.all())

        result = paginate_query(context, sa_models.Account,
                                limit=limit, offset=offset,
                                query=query)

        return (self._row_to_db_account_model(r) for r in result), total_count

    def get_accounts(self, context, user_id=None, read_deleted=False,
                     owed=None, limit=None, offset=None,
                     sort_key=None, sort_dir=None, active_from=None):
        query = get_session().query(sa_models.Account)
        if owed is not None:
            query = query.filter_by(owed=owed)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if active_from:
            query = query.filter(sa_models.Account.updated_at > active_from)
        if not read_deleted:
            query = query.filter_by(deleted=False)

        result = paginate_query(context, sa_models.Account,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_account_model(r) for r in result)

    def get_accounts_count(self, context, read_deleted=False,
                           user_id=None, owed=None, active_from=None):
        query = get_session().query(sa_models.Account,
                                    func.count(sa_models.Account.id).label('count'))
        if owed is not None:
            query = query.filter_by(owed=owed)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if active_from:
            query = query.filter(sa_models.Account.updated_at > active_from)
        if not read_deleted:
            query = query.filter_by(deleted=False)

        return query.one().count or 0

    def change_account_level(self, context, user_id, level, project_id=None):
        session = db_session.get_session()
        with session.begin():
            account = session.query(sa_models.Account).\
                filter_by(user_id=user_id).\
                with_lockmode('update').one()
            account.level = level

        return self._row_to_db_account_model(account)

    def update_account(self, context, user_id, project_id=None,
                       operator=None, **data):
        """Do the charge charge account trick
        """
        session = db_session.get_session()
        with session.begin():
            account = session.query(sa_models.Account).\
                filter_by(user_id=user_id).\
                with_lockmode('update').one()
            account.balance += data['value']

            if account.balance >= 0:
                account.owed = False

            is_first_charge = False
            if data.get('type') == 'money' and not account.charged:
                account.charged = True
                is_first_charge = True

            # add charge records
            if not data.get('charge_time'):
                charge_time = datetime.datetime.utcnow()
            else:
                charge_time = timeutils.parse_isotime(data['charge_time'])

            charge = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                      user_id=account.user_id,
                                      domain_id=account.domain_id,
                                      value=data['value'],
                                      type=data.get('type'),
                                      come_from=data.get('come_from'),
                                      trading_number=data.get(
                                          'trading_number'),
                                      charge_time=charge_time,
                                      operator=operator,
                                      remarks=data.get('remarks'))
            session.add(charge)

            if data.get('invitee'):
                invitee = session.query(sa_models.Account).\
                    filter_by(user_id=data.get('invitee')).\
                    with_lockmode('update').one()
                invitee.reward_value = data['value']

        return self._row_to_db_charge_model(charge), is_first_charge

    @require_admin_context
    def deduct_account(self, context, user_id, deduct=True, **data):
        """Deduct account by user_id
        """
        session = db_session.get_session()
        with session.begin():
            if deduct:
                account = session.query(sa_models.Account).\
                    filter_by(user_id=user_id).\
                    with_lockmode('update').one()
                account.balance -= data['money']

            deduct = sa_models.Deduct(req_id=data['reqId'],
                                      deduct_id=uuidutils.generate_uuid(),
                                      type=data.get('type'),
                                      money=data['money'],
                                      remark=data.get('remark'),
                                      order_id=data['extData']['order_id'])
            session.add(deduct)
        return self._row_to_db_deduct_model(deduct)

    @require_admin_context
    def get_deduct(self, context, req_id):
        """Get deduct by deduct id
        """
        try:
            deduct = get_session().query(sa_models.Deduct).\
                filter_by(req_id=req_id).\
                one()
        except NoResultFound:
            raise exception.DeductNotFound(req_id=req_id)
        return self._row_to_db_deduct_model(deduct)

    def set_charged_orders(self, context, user_id, project_id=None):
        """Set owed orders to charged
        """
        session = db_session.get_session()
        with session.begin():
            # set owed order in all regions to charged
            if project_id:
                query = session.query(sa_models.Order).\
                    filter_by(project_id=project_id).\
                    filter_by(owed=True)
            else:
                query = session.query(sa_models.Order).\
                    filter_by(user_id=user_id).\
                    filter_by(owed=True)

            orders = query.filter(
                not_(sa_models.Order.status == const.STATE_DELETED)).all()

            for order in orders:
                order.owed = False
                order.date_time = None
                order.charged = True

    def reset_charged_orders(self, context, order_ids):
        session = db_session.get_session()
        with session.begin():
            for order_id in order_ids:
                try:
                    order = session.query(sa_models.Order).\
                        filter_by(order_id=order_id).\
                        one()
                except NoResultFound:
                    continue
                order.charged = False

    def get_charges(self, context, user_id=None, project_id=None, type=None,
                    start_time=None, end_time=None,
                    limit=None, offset=None, sort_key=None, sort_dir=None):
        query = get_session().query(sa_models.Charge)

        if project_id:
            query = query.filter_by(project_id=project_id)

        if user_id:
            query = query.filter_by(user_id=user_id)

        if type:
            query = query.filter_by(type=type)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Charge.charge_time >= start_time,
                                 sa_models.Charge.charge_time < end_time)

        result = paginate_query(context, sa_models.Charge,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_charge_model(r) for r in result)

    def get_charges_price_and_count(self, context, user_id=None,
                                    project_id=None, type=None,
                                    start_time=None, end_time=None):
        query = get_session().query(
            sa_models.Charge,
            func.count(sa_models.Charge.id).label('count'),
            func.sum(sa_models.Charge.value).label('sum'))

        if project_id:
            query = query.filter_by(project_id=project_id)

        if user_id:
            query = query.filter_by(user_id=user_id)

        if type:
            query = query.filter_by(type=type)

        if all([start_time, end_time]):
            query = query.filter(sa_models.Charge.charge_time >= start_time,
                                 sa_models.Charge.charge_time < end_time)

        return query.one().sum or 0, query.one().count or 0

    def create_project(self, context, project):
        session = db_session.get_session()
        with session.begin():
            project_ref = sa_models.Project(**project.as_dict())
            user_project_ref = sa_models.UserProject(**project.as_dict())
            session.add(project_ref)
            session.add(user_project_ref)
        return self._row_to_db_project_model(project_ref)

    @require_context
    def get_billing_owner(self, context, project_id):
        try:
            project = model_query(context, sa_models.Project).\
                filter_by(project_id=project_id).one()
        except NoResultFound:
            raise exception.ProjectNotFound(project_id=project_id)

        try:
            account = model_query(context, sa_models.Account).\
                filter_by(user_id=project.user_id).one()
        except NoResultFound:
            raise exception.AccountNotFound(user_id=project.user_id)

        return self._row_to_db_account_model(account)

    @require_admin_context
    def freeze_balance(self, context, project_id, total_price):
        session = db_session.get_session()
        with session.begin():
            try:
                project = model_query(context, sa_models.Project).\
                    filter_by(project_id=project_id).one()
            except NoResultFound:
                raise exception.ProjectNotFound(project_id=project_id)

            try:
                account = session.query(sa_models.Account).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.AccountNotFound(user_id=project.user_id)

            if account.balance < total_price and account.level != 9:
                raise exception.NotSufficientFund(user_id=project.user_id,
                                                  project_id=project_id)

            account.balance -= total_price
            account.frozen_balance += total_price

        return self._row_to_db_account_model(account)

    @require_admin_context
    def unfreeze_balance(self, context, project_id, total_price):
        session = db_session.get_session()
        with session.begin():
            try:
                project = model_query(context, sa_models.Project).\
                    filter_by(project_id=project_id).one()
            except NoResultFound:
                raise exception.ProjectNotFound(project_id=project_id)

            try:
                account = session.query(sa_models.Account).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.AccountNotFound(user_id=project.user_id)

            if account.frozen_balance < total_price:
                raise exception.NotSufficientFrozenBalance(
                    user_id=project.user_id, project_id=project_id)

            account.balance += total_price
            account.frozen_balance -= total_price

        return self._row_to_db_account_model(account)

    @require_context
    def get_project(self, context, project_id):
        try:
            project = get_session().query(sa_models.Project).\
                filter_by(project_id=project_id).one()
        except NoResultFound:
            raise exception.ProjectNotFound(project_id=project_id)

        return self._row_to_db_project_model(project)

    @require_context
    def get_user_projects(self, context, user_id=None,
                          limit=None, offset=None):
        # get user's all historical projects
        query = model_query(context, sa_models.UserProject)
        if user_id:
            query = query.filter_by(user_id=user_id)
        user_projects = query.all()

        result = []

        # get project consumption
        for u in user_projects:
            try:
                p = model_query(context, sa_models.Project).\
                    filter_by(project_id=u.project_id).\
                    filter_by(user_id=u.user_id).\
                    one()
            except NoResultFound:
                p = None

            up = db_models.UserProject(
                user_id=user_id,
                project_id=u.project_id,
                user_consumption=u.consumption,
                project_consumption=p.consumption if p else u.consumption,
                is_historical=False if p else True)
            result.append(up)

        return result

    @require_context
    def get_projects_by_project_ids(self, context, project_ids):
        projects = get_session().query(sa_models.Project).\
            filter(sa_models.Project.project_id.in_(project_ids)).\
            all()
        return (self._row_to_db_project_model(p) for p in projects)

    @require_context
    def get_projects(self, context, user_id=None, active_from=None):
        query = model_query(context, sa_models.Project)

        if user_id:
            query = query.filter_by(user_id=user_id)
        if active_from:
            query = query.filter(sa_models.Project.updated_at > active_from)

        projects = query.all()

        return (self._row_to_db_project_model(p) for p in projects)

    def change_billing_owner(self, context, project_id, user_id):
        session = db_session.get_session()
        with session.begin():
            # ensure user exists
            try:
                model_query(context, sa_models.Account).\
                    filter_by(user_id=user_id).one()
            except NoResultFound:
                LOG.error("Could not find the user: %s" % user_id)
                raise exception.AccountNotFound(user_id=user_id)

            # ensure project exists
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s' % project_id)
                raise exception.ProjectNotFound(project_id=project_id)

            # change user_id of all orders belongs to this project
            orders = model_query(context, sa_models.Order, session=session).\
                filter_by(project_id=project_id).\
                with_lockmode('update').all()
            for order in orders:
                order.user_id = user_id

            # change payer of this project
            project.user_id = user_id

            # add/update relationship between user and project
            try:
                user_project = model_query(
                    context, sa_models.UserProject, session=session).\
                    filter_by(user_id=user_id).\
                    filter_by(project_id=project_id).\
                    one()
                user_project.updated_at = timeutils.utcnow()
            except NoResultFound:
                session.add(sa_models.UserProject(user_id=user_id,
                                                  project_id=project_id,
                                                  consumption='0',
                                                  domain_id=project.domain_id))

    @require_admin_context
    def update_bill(self, context, order_id, external_balance=None):
        """Update the latest bill, there are three type of results:
        0, Update bill successfully, including account is owed and order is
           owed, or account is not owed and balance is greater than 0
        1, Suspend to update bill, but set order to owed, that is account is
           owed and order is not owed
        2, Update bill successfully, but set account to owed, that is account
           is not owed and balance is less than 0
        """
        session = db_session.get_session()
        result = {'type': -1, 'resource_owed': False}
        with session.begin():
            # Get order
            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=order_id).\
                with_lockmode('update').one()

            # Update the latest bill
            try:
                bill = model_query(context, sa_models.Bill, session=session).\
                    filter_by(order_id=order_id).\
                    order_by(desc(sa_models.Bill.id)).all()[0]
            except IndexError:
                LOG.warning('There is no latest bill for the order: %s',
                            order_id)
                return result

            action_time = bill.end_time
            now = timeutils.utcnow() + datetime.timedelta(
                seconds=cfg.CONF.master.allow_delay_seconds)

            if action_time > now:
                LOG.warn('The latest bill end_time(%s) of the order(%s) is '
                         'greater than utc now(%s)',
                         bill.end_time, order_id, now)
                return result

            # get project
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=order.project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s', order.project_id)
                raise exception.ProjectNotFound(project_id=order.project_id)

            if project.user_id != bill.user_id:
                # billing owner of this project has been changed
                new_bill = sa_models.Bill(
                    bill_id=uuidutils.generate_uuid(),
                    start_time=action_time,
                    end_time=action_time + datetime.timedelta(hours=1),
                    type=order.type,
                    status=const.BILL_PAYED,
                    unit_price=order.unit_price,
                    unit=order.unit,
                    total_price=order.unit_price,
                    order_id=order.order_id,
                    resource_id=order.resource_id,
                    remarks="The Billing Owner Has Changed",
                    user_id=project.user_id,
                    project_id=order.project_id,
                    region_id=order.region_id,
                    domain_id=order.domain_id)
                session.add(new_bill)
            else:
                # update the latest bill
                bill.end_time += datetime.timedelta(hours=1)
                bill.total_price += order.unit_price
                bill.updated_at = datetime.datetime.utcnow()

            # Update order
            cron_time = action_time + datetime.timedelta(hours=1)
            order.total_price += order.unit_price
            order.cron_time = cron_time
            order.updated_at = datetime.datetime.utcnow()

            # Update project and user_project
            try:
                user_project = model_query(
                    context, sa_models.UserProject, session=session).\
                    filter_by(project_id=order.project_id).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error("Could not find the relationship between user(%s) "
                          "and project(%s)",
                          project.user_id, order.project_id)
                raise exception.UserProjectNotFound(
                    user_id=project.user_id,
                    project_id=order.project_id)
            project.consumption += order.unit_price
            project.updated_at = datetime.datetime.utcnow()
            user_project.consumption += order.unit_price
            user_project.updated_at = datetime.datetime.utcnow()

            # Update account
            try:
                account = model_query(
                    context, sa_models.Account, session=session).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the account: %s', project.user_id)
                raise exception.AccountNotFound(user_id=project.user_id)

            # override account balance before deducting
            if external_balance is not None:
                external_balance = quantize(
                    external_balance)
                account.balance = external_balance

            account.balance -= order.unit_price
            account.consumption += order.unit_price
            account.updated_at = datetime.datetime.utcnow()

            result['user_id'] = account.user_id
            result['project_id'] = project.project_id
            result['resource_type'] = order.type
            result['resource_name'] = order.resource_name
            result['resource_id'] = order.resource_id
            result['region_id'] = order.region_id
            result['type'] = const.BILL_NORMAL

            if not cfg.CONF.enable_owe:
                return result

            # Account is owed
            if self._check_if_account_first_owed(account):
                account.owed = True
                result['type'] = const.BILL_ACCOUNT_OWED
            # Order is owed
            elif self._check_if_order_first_owed(account, order):
                reserved_days = gringutils.cal_reserved_days(account.level)
                date_time = (datetime.datetime.utcnow() +
                             datetime.timedelta(days=reserved_days))
                order.date_time = date_time
                order.owed = True
                result['type'] = const.BILL_ORDER_OWED
                result['date_time'] = date_time
            # Account is charged but order is still owed
            elif self._check_if_account_charged(account, order):
                result['type'] = const.BILL_OWED_ACCOUNT_CHARGED
                order.owed = False
                order.date_time = None
                order.charged = False

            if order.owed:
                result['resource_owed'] = True

            return result

    @require_admin_context
    def create_bill(self, context, order_id, action_time=None,
                    remarks=None, end_time=None,
                    external_balance=None):
        """Create a bill

        There are three type of results:
        0, Create bill successfully, including account is owed and order is
           owed, or account is not owed and balance is greater than 0
        1, Suspend to create bill, but set order to owed, that is account is
           owed and order is not owed
        2, Create bill successfully, but set account to owed, that is account
           is not owed and balance is less than 0
        """
        session = db_session.get_session()
        result = {'type': -1, 'resource_owed': False}
        with session.begin():
            # Get order
            order = model_query(context, sa_models.Order, session=session).\
                filter_by(order_id=order_id).\
                with_lockmode('update').one()

            if order.status == const.STATE_CHANGING:
                return result

            if not action_time:
                action_time = order.cron_time

            now = timeutils.utcnow() + datetime.timedelta(
                seconds=cfg.CONF.master.allow_delay_seconds)

            if action_time > now:
                LOG.warn('The action_time(%s) of the order(%s) if greater '
                         'than utc now(%s)',
                         action_time, order_id, now)
                return result

            # get project
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=order.project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s', order.project_id)
                raise exception.ProjectNotFound(project_id=order.project_id)

            # get account
            try:
                account = model_query(
                    context, sa_models.Account, session=session).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the account: %s', project.user_id)
                raise exception.AccountNotFound(user_id=project.user_id)

            # override account balance before deducting
            if external_balance is not None:
                external_balance = quantize(external_balance)
                account.balance = external_balance

            result['user_id'] = account.user_id
            result['project_id'] = project.project_id
            result['resource_type'] = order.type
            result['resource_name'] = order.resource_name
            result['resource_id'] = order.resource_id
            result['region_id'] = order.region_id

            if not order.unit or order.unit == 'hour':
                next_cron_time = end_time or \
                    action_time + datetime.timedelta(hours=1)
                total_price = order.unit_price
            else:
                # NOTE(suo): If order doesn't activate auto-renew, when the period
                # is expired, we regard it as owed even if there is enough balance.
                if not order.renew:
                    reserved_days = gringutils.cal_reserved_days(account.level)
                    date_time = (datetime.datetime.utcnow() +
                                 datetime.timedelta(days=reserved_days))
                    order.date_time = date_time
                    order.status = const.STATE_STOPPED
                    order.updated_at = datetime.datetime.utcnow()
                    order.owed = True
                    result['resource_owed'] = True
                    result['type'] = const.BILL_ORDER_OWED
                    result['date_time'] = date_time
                    return result

                months = gringutils.to_months(order.renew_method,
                                              order.renew_period)
                next_cron_time = gringutils.add_months(action_time, months)
                total_price = order.unit_price * order.renew_period

                if account.balance < total_price and account.level != 9:
                    reserved_days = gringutils.cal_reserved_days(account.level)
                    date_time = (datetime.datetime.utcnow() +
                                 datetime.timedelta(days=reserved_days))
                    order.date_time = date_time
                    order.status = const.STATE_STOPPED
                    order.updated_at = datetime.datetime.utcnow()
                    order.owed = True
                    result['resource_owed'] = True
                    result['type'] = const.BILL_ORDER_OWED
                    result['date_time'] = date_time
                    return result

            bill = sa_models.Bill(
                bill_id=uuidutils.generate_uuid(),
                start_time=action_time,
                end_time=next_cron_time,
                type=order.type,
                status=const.BILL_PAYED,
                unit_price=order.unit_price,
                unit=order.unit,
                total_price=total_price,
                order_id=order.order_id,
                resource_id=order.resource_id,
                remarks=remarks,
                user_id=project.user_id,
                project_id=order.project_id,
                region_id=order.region_id,
                domain_id=order.domain_id)
            session.add(bill)

            # if end_time is specified, it means the action is stopping
            # the instance, so there is no need to deduct account, creating
            # a new bill is enough.
            if end_time:
                return result

            # Update order
            order.total_price += total_price
            order.cron_time = next_cron_time
            order.updated_at = datetime.datetime.utcnow()

            # Update project and user_project
            try:
                user_project = model_query(
                    context, sa_models.UserProject, session=session).\
                    filter_by(project_id=order.project_id).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the relationship between user(%s) '
                          'and project(%s)',
                          project.user_id, order.project_id)
                raise exception.UserProjectNotFound(
                    user_id=project.user_id,
                    project_id=order.project_id)
            project.consumption += total_price
            project.updated_at = datetime.datetime.utcnow()
            user_project.consumption += total_price
            user_project.updated_at = datetime.datetime.utcnow()

            # Update account
            account.balance -= total_price
            account.consumption += total_price
            account.updated_at = datetime.datetime.utcnow()

            result['type'] = const.BILL_NORMAL

            if not cfg.CONF.enable_owe:
                return result

            if order.unit in ['month', 'year']:
                return result

            # Account is owed
            if self._check_if_account_first_owed(account):
                account.owed = True
                result['type'] = const.BILL_ACCOUNT_OWED
            # Order is owed
            elif self._check_if_order_first_owed(account, order):
                reserved_days = gringutils.cal_reserved_days(account.level)
                date_time = (datetime.datetime.utcnow() +
                             datetime.timedelta(days=reserved_days))
                order.date_time = date_time
                order.owed = True
                result['type'] = const.BILL_ORDER_OWED
                result['date_time'] = date_time
            # Account is charged but order is still owed
            elif self._check_if_account_charged(account, order):
                result['type'] = const.BILL_OWED_ACCOUNT_CHARGED
                order.owed = False
                order.date_time = None
                order.charged = False

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
    def close_bill(self, context, order_id, action_time,
                   external_balance=None):
        session = db_session.get_session()
        result = {'type': -1, 'resource_owed': False}
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
                LOG.warning('There is no latest bill for the order: %s',
                            order_id)
                return result

            if action_time >= bill.end_time:
                return result

            delta = quantize(
                timeutils.delta_seconds(action_time, bill.end_time) / 3600.0
            )

            more_fee = quantize(delta * order.unit_price)
            bill.end_time = action_time
            bill.total_price -= more_fee
            bill.updated_at = datetime.datetime.utcnow()

            # Update the order
            order.total_price -= more_fee
            order.status = const.STATE_CHANGING
            order.updated_at = datetime.datetime.utcnow()

            # Update project
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=order.project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s', order.project_id)
                raise exception.ProjectNotFound(project_id=order.project_id)

            project.consumption -= more_fee
            project.updated_at = datetime.datetime.utcnow()

            # Update user_project
            try:
                user_project = model_query(
                    context, sa_models.UserProject, session=session).\
                    filter_by(project_id=order.project_id).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the relationship between user(%s) '
                          'and project(%s)',
                          project.user_id, order.project_id)
                raise exception.UserProjectNotFound(
                    user_id=project.user_id,
                    project_id=order.project_id)
            user_project.consumption -= more_fee
            user_project.updated_at = datetime.datetime.utcnow()

            # Update the account
            try:
                account = model_query(
                    context, sa_models.Account, session=session).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').\
                    one()
            except NoResultFound:
                LOG.error('Could not find the account: %s' % order.project_id)
                raise exception.AccountNotFound(project_id=order.project_id)

            # override account balance before deducting
            if external_balance is not None:
                external_balance = quantize(external_balance)
                account.balance = external_balance

            account.balance += more_fee
            account.consumption -= more_fee
            account.updated_at = datetime.datetime.utcnow()

            result['user_id'] = account.user_id
            result['project_id'] = project.project_id
            result['resource_type'] = order.type
            result['resource_name'] = order.resource_name
            result['resource_id'] = order.resource_id
            result['region_id'] = order.region_id
            result['type'] = const.BILL_NORMAL

            if not cfg.CONF.enable_owe:
                return result

            if account.owed and account.balance > 0:
                result['type'] = const.BILL_ACCOUNT_NOT_OWED
                account.owed = False

            # deleted by people
            if order.owed and action_time < order.date_time:
                result['resource_owed'] = True

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
            account = model_query(
                context, sa_models.Account, session=session).\
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

    @require_context
    def create_precharge(self, context, **kwargs):
        session = db_session.get_session()
        with session.begin():
            operator_id = context.user_id
            for i in xrange(kwargs['number']):
                while True:
                    try:
                        session.add(
                            sa_models.PreCharge(
                                code=gringutils.random_str(),
                                price=kwargs['price'],
                                operator_id=operator_id,
                                remarks=kwargs['remarks'],
                                expired_at=kwargs['expired_at'])
                        )
                    except db_exception.DBDuplicateEntry:
                        continue
                    else:
                        break

    def get_precharges(self, context, user_id=None, limit=None, offset=None,
                       sort_key=None, sort_dir=None):
        query = model_query(context, sa_models.PreCharge).\
            filter_by(deleted=False)

        if user_id:
            query = query.filter_by(user_id=user_id)

        result = paginate_query(context, sa_models.PreCharge,
                                limit=limit, offset=offset,
                                sort_key=sort_key, sort_dir=sort_dir,
                                query=query)

        return (self._row_to_db_precharge_model(r) for r in result)

    def get_precharges_count(self, context, user_id=None):
        query = model_query(context, sa_models.PreCharge,
                            func.count(sa_models.PreCharge.id).
                            label('count')).filter_by(deleted=False)

        if user_id:
            query = query.filter_by(user_id=user_id)

        try:
            result = query.one()
        except (NoResultFound):
            return 0
        return result.count

    def delete_precharge(self, context, code):
        session = db_session.get_session()
        with session.begin():
            try:
                precharge = model_query(
                    context, sa_models.PreCharge, session=session).\
                    filter_by(deleted=False).\
                    filter_by(code=code).one()
            except NoResultFound:
                raise exception.PreChargeNotFound(precharge_code=code)
            precharge.deleted = True
            precharge.deleted_at = datetime.datetime.utcnow()

    def get_precharge_by_code(self, context, code):
        try:
            precharge = model_query(context, sa_models.PreCharge).\
                filter_by(deleted=False).\
                filter_by(code=code).one()
        except NoResultFound:
            LOG.warning('The precharge %s not found', code)
            raise exception.PreChargeNotFound(precharge_code=code)
        return self._row_to_db_precharge_model(precharge)

    def dispatch_precharge(self, context, code, remarks=None):
        session = db_session.get_session()
        with session.begin():
            try:
                precharge = model_query(
                    context, sa_models.PreCharge, session=session).\
                    filter_by(deleted=False).\
                    filter_by(code=code).one()
            except NoResultFound:
                raise exception.PreChargeNotFound(precharge_code=code)

            if precharge.used:
                raise exception.PreChargeHasUsed(precharge_code=code)

            if precharge.dispatched:
                raise exception.PreChargeHasDispatched(precharge_code=code)

            precharge.dispatched = True
            precharge.remarks = remarks

        return self._row_to_db_precharge_model(precharge)

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

            try:
                account = model_query(
                    context, sa_models.Account, session=session).\
                    filter_by(user_id=user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.AccountNotFound(user_id=user_id)

            account.balance += precharge.price
            if account.balance >= 0:
                account.owed = False

            # Add charge records
            charge_time = datetime.datetime.utcnow()
            charge = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                      user_id=account.user_id,
                                      project_id=account.project_id,
                                      domain_id=account.domain_id,
                                      value=precharge.price,
                                      type='coupon',
                                      come_from="coupon",
                                      charge_time=charge_time,
                                      operator=account.user_id,
                                      remarks='coupon')
            session.add(charge)

            # Update precharge
            precharge.used = True
            precharge.user_id = user_id
            precharge.project_id = project_id
            precharge.domain_id = account.domain_id

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

            bills = session.query(sa_models.Bill).\
                filter_by(order_id=new_order.order_id)
            for bill in bills:
                session.delete(bill)

            session.delete(new_order)

    @require_context
    def fix_stopped_order(self, context, order_id):
        session = db_session.get_session()
        with session.begin():
            order = session.query(sa_models.Order).\
                filter_by(order_id=order_id).one()
            bills = session.query(sa_models.Bill).\
                filter_by(order_id=order_id).\
                order_by(desc(sa_models.Bill.id)).all()
            account = session.query(sa_models.Account).\
                filter_by(project_id=order.project_id).one()

            more_fee = quantize('0')
            add_new_bill = True

            for bill in bills:
                if bill.total_price == quantize('0.0020') or \
                        bill.total_price == quantize('0.0400') or \
                        bill.total_price == quantize('0.0800'):
                    more_fee += bill.total_price
                if bill.total_price == quantize('0.0000'):
                    add_new_bill = False
                    cron_time = bill.end_time
                    break
                if (bill.total_price != quantize('0.0020') and
                        bill.total_price != quantize('0.0400') and
                        bill.total_price != quantize('0.0800')) or \
                        bill.remarks == 'Sytstem Adjust':
                    start_time = bill.end_time
                    cron_time = bill.end_time + datetime.timedelta(days=30)
                    break
                session.delete(bill)

            if add_new_bill:
                bill = sa_models.Bill(
                    bill_id=uuidutils.generate_uuid(),
                    start_time=start_time,
                    end_time=start_time + datetime.timedelta(days=30),
                    type=order.type,
                    status=const.BILL_PAYED,
                    unit_price=quantize('0.0000'),
                    unit=order.unit,
                    total_price=quantize('0.0000'),
                    order_id=order.order_id,
                    resource_id=order.resource_id,
                    remarks='Instance Has Been Stopped',
                    user_id=order.user_id,
                    project_id=order.project_id,
                    region_id=order.region_id)
                session.add(bill)

            order.unit_price = quantize('0.0000')
            order.cron_time = cron_time

            order.total_price -= more_fee
            account.balance += more_fee
            account.consumption -= more_fee

    def transfer_money(self, cxt, data):
        session = db_session.get_session()
        with session.begin():
            account_to = session.query(sa_models.Account).\
                filter_by(user_id=data.user_id_to).\
                with_lockmode('update').one()
            account_from = session.query(sa_models.Account).\
                filter_by(user_id=data.user_id_from).\
                with_lockmode('update').one()

            if cxt.domain_id != account_to.domain_id or \
                    cxt.domain_id != account_from.domain_id or \
                    account_to.domain_id != account_from.domain_id:
                raise exception.NotAuthorized()

            if account_from.balance <= 0:
                raise exception.NoBalanceToTransfer(value=account_from.balance)

            if account_from.balance < data.money:
                raise exception.InvalidTransferMoneyValue(value=data.money)

            account_to.balance += data.money
            account_from.balance -= data.money

            remarks = data.remarks if data.remarks != wsme.Unset else None
            charge_time = datetime.datetime.utcnow()
            charge_to = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                         user_id=account_to.user_id,
                                         project_id=account_to.project_id,
                                         domain_id=account_to.domain_id,
                                         value=data.money,
                                         type="transfer",
                                         come_from="transfer",
                                         charge_time=charge_time,
                                         operator=cxt.user_id,
                                         remarks=remarks)
            session.add(charge_to)

            charge_from = sa_models.Charge(charge_id=uuidutils.generate_uuid(),
                                           user_id=account_from.user_id,
                                           project_id=account_from.project_id,
                                           domain_id=account_from.domain_id,
                                           value=-data.money,
                                           type="transfer",
                                           come_from="transfer",
                                           charge_time=charge_time,
                                           operator=cxt.user_id,
                                           remarks=remarks)
            session.add(charge_from)

    def set_accounts_salesperson(self, context, user_id_list, sales_id):
        session = db_session.get_session()
        with session.begin():
            # make sure sales_id is a valid account
            try:
                session.query(sa_models.Account).filter_by(
                    user_id=sales_id).with_lockmode('read').one()
            except (NoResultFound):
                LOG.warning(
                    'Salesperson %s does not have an account', sales_id)
                raise exception.AccountNotFound(user_id=sales_id)

            for user_id in user_id_list:
                try:
                    account = session.query(sa_models.Account).filter_by(
                        user_id=user_id).with_lockmode('update').one()
                    account.sales_id = sales_id
                except (NoResultFound):
                    LOG.warning('Account %s does not exist', user_id)
                    raise exception.AccountNotFound(user_id=user_id)

    def get_salesperson_amount(self, context, sales_id):
        session = db_session.get_session()
        query = session.query(
            sa_models.Account,
            func.count(sa_models.Account.id).label('count'),
            func.sum(sa_models.Account.consumption).label('sales_amount'))
        query = query.filter_by(sales_id=sales_id)
        try:
            result = query.one()
        except (NoResultFound):
            # This salesperson has no customer
            return 0, 0

        return result.count, result.sales_amount

    def get_salesperson_customer_accounts(self, context, sales_id,
                                          offset=None, limit=None):
        session = db_session.get_session()
        query = session.query(sa_models.Account).filter_by(
            sales_id=sales_id)
        try:
            result = paginate_query(
                context, sa_models.Account, query=query,
                offset=offset, limit=limit
            )
            return (self._row_to_db_account_model(a) for a in result)
        except (NoResultFound):
            # This salesperson has no customer
            return ()

    def activate_auto_renew(self, context, order_id, renew):
        """Activate or update auto renew

        We should ensure unit, unit_price, renew_method and renew_period
        is consistent, for example, if unit is month, then unit_price is
        must be the one month's price, not one year, and renew_method is
        also must be month, and renew_period actually specifies the how
        many months.

        So we must re-caculate the unit_price if the renew_method is changed.
        """
        session = db_session.get_session()
        with session.begin():
            try:
                order = model_query(
                    context, sa_models.Order, session=session).\
                    filter_by(order_id=order_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.OrderNotFound(order_id=order_id)

            if not order.unit or order.unit == 'hour':
                raise exception.OrderRenewError(
                    err="Hourly billing resources can't be renewed")

            if order.status == const.STATE_DELETED:
                raise exception.OrderRenewError(
                    err="Deleted resource can't be renewed")

            order.renew = True
            order.renew_method = renew.method
            order.renew_period = renew.period
            order.updated_at = datetime.datetime.utcnow()

            if renew.method != order.unit:
                new_unit_price = 0
                subs = model_query(
                    context, sa_models.Subscription, session=session).\
                    filter_by(order_id=order_id).\
                    filter_by(type=const.STATE_RUNNING).\
                    with_lockmode('read').all()
                for sub in subs:
                    unit_price = jsonutils.loads(sub.unit_price)
                    price_data = pricing.get_price_data(
                        unit_price, order.renew_method)
                    new_unit_price += pricing.calculate_price(
                        sub.quantity, price_data)
                order.unit = renew.method
                order.unit_price = new_unit_price

        return self._row_to_db_order_model(order)

    def switch_auto_renew(self, context, order_id, action):
        session = db_session.get_session()
        with session.begin():
            try:
                order = model_query(
                    context, sa_models.Order, session=session).\
                    filter_by(order_id=order_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.OrderNotFound(order_id=order_id)

            if not order.unit or order.unit == 'hour':
                raise exception.OrderRenewError(
                    err="Hourly billing resources can't be renewed")

            if order.status == const.STATE_DELETED:
                raise exception.OrderRenewError(
                    err="Deleted resource can't be renewed")

            if not order.renew_method or not order.renew_period:
                raise exception.OrderRenewError(
                    err="The order's auto renew has not been activated")

            if action == 'start':
                order.renew = True
            elif action == 'stop':
                order.renew = False
            order.updated_at = datetime.datetime.utcnow()
        return self._row_to_db_order_model(order)

    def renew_order(self, context, order_id, renew):
        session = db_session.get_session()
        with session.begin():
            try:
                order = model_query(
                    context, sa_models.Order, session=session).\
                    filter_by(order_id=order_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                raise exception.OrderNotFound(order_id=order_id)

            if not order.unit or order.unit == 'hour':
                raise exception.OrderRenewError(
                    err="Hourly billing resources can't be renewed")

            if order.status == const.STATE_DELETED:
                raise exception.OrderRenewError(
                    err="Deleted resource can't be renewed")

            if not order.cron_time:
                raise exception.OrderRenewError(err="Order cron_time is None")

            # get project
            try:
                project = model_query(
                    context, sa_models.Project, session=session).\
                    filter_by(project_id=order.project_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the project: %s', order.project_id)
                raise exception.ProjectNotFound(project_id=order.project_id)

            # get account
            try:
                account = model_query(
                    context, sa_models.Account, session=session).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the account: %s', project.user_id)
                raise exception.AccountNotFound(user_id=project.user_id)

            # calculate unit price
            if renew.method != order.unit:
                subs = model_query(
                    context, sa_models.Subscription, session=session).\
                    filter_by(order_id=order_id).\
                    filter_by(type=const.STATE_RUNNING).\
                    with_lockmode('read').all()
                unit_price = 0
                for sub in subs:
                    unit_price = jsonutils.loads(sub.unit_price)
                    price_data = pricing.get_price_data(
                        unit_price, renew.method)
                    unit_price += pricing.calculate_price(
                        sub.quantity, price_data)
            else:
                unit_price = order.unit_price

            total_price = unit_price * renew.period

            if account.balance < total_price and account.level != 9:
                raise exception.NotSufficientFund(user_id=project.user_id,
                                                  project_id=order.project_id)

            # create bill
            if renew.period > 1:
                remarks = "Renew for %s %ss" % \
                        (renew.period, renew.method)
            else:
                remarks = "Renew for %s %s" % \
                        (renew.period, renew.method)

            months = gringutils.to_months(renew.method, renew.period)
            end_time = gringutils.add_months(order.cron_time, months)
            bill = sa_models.Bill(
                bill_id=uuidutils.generate_uuid(),
                start_time=order.cron_time,
                end_time=end_time,
                type=order.type,
                status=const.BILL_PAYED,
                unit_price=unit_price,
                unit=renew.method,
                total_price=total_price,
                order_id=order.order_id,
                resource_id=order.resource_id,
                remarks=remarks,
                user_id=project.user_id,
                project_id=order.project_id,
                region_id=order.region_id,
                domain_id=order.domain_id)
            session.add(bill)

            if renew.auto:
                order.renew = True
                order.renew_method = renew.method
                order.renew_period = renew.period
                order.unit = renew.method
                order.unit_price = unit_price

            order.total_price += total_price
            order.cron_time = end_time
            order.date_time = None
            order.status = const.STATE_RUNNING
            order.owed = False
            order.updated_at = datetime.datetime.utcnow()

            # Update project and user_project
            try:
                user_project = model_query(
                    context, sa_models.UserProject, session=session).\
                    filter_by(project_id=order.project_id).\
                    filter_by(user_id=project.user_id).\
                    with_lockmode('update').one()
            except NoResultFound:
                LOG.error('Could not find the relationship between user(%s) '
                          'and project(%s)',
                          project.user_id, order.project_id)
                raise exception.UserProjectNotFound(
                    user_id=project.user_id,
                    project_id=order.project_id)
            project.consumption += total_price
            project.updated_at = datetime.datetime.utcnow()
            user_project.consumption += total_price
            user_project.updated_at = datetime.datetime.utcnow()

            # Update account
            account.balance -= total_price
            account.consumption += total_price
            account.updated_at = datetime.datetime.utcnow()

        return self._row_to_db_order_model(order), total_price
