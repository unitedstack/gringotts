import pecan
import wsme
import datetime
import itertools

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo_config import cfg

from gringotts import constants as const
from gringotts.api import acl
from gringotts.api import app
from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.services import keystone
from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils


LOG = log.getLogger(__name__)


class BillingOwnerController(rest.RestController):

    _custom_actions = {
        'freeze': ['PUT'],
        'unfreeze': ['PUT'],
    }

    def __init__(self, project_id, external_client):
        self.project_id = project_id
        self.external_client = external_client

    @wsexpose(None, wtypes.text)
    def put(self, user_id):
        """Change billing_owner of this project."""
        self.conn = pecan.request.db_conn
        self.conn.change_billing_owner(request.context,
                                       project_id=self.project_id,
                                       user_id=user_id)

    @wsexpose(models.UserAccount)
    def get(self):
        self.conn = pecan.request.db_conn
        account = self.conn.get_billing_owner(request.context,
                                                      self.project_id)
        try:
            if cfg.CONF.external_billing.enable:
                external_balance = self.external_client.get_external_balance(
                    account.user_id)['data'][0]['money']
                account.balance = gringutils._quantize_decimal(
                    external_balance)
        except Exception:
            LOG.exception("Fail to get external balance of the account: %s" % \
                account.user_id)
        return models.UserAccount.from_db_model(account)

    @wsexpose(models.BalanceFrozenResult, body=models.BalanceFrozenBody)
    def freeze(self, data):
        self.conn = pecan.request.db_conn
        try:
            account = self.conn.freeze_balance(request.context,
                                               self.project_id,
                                               data.total_price)
        except (exception.ProjectNotFound, exception.AccountNotFound):
            raise
        except exception.NotSufficientFund:
            raise
        except Exception:
            msg = "Fail to freeze balance %s of the project_id %s" % \
                (data.total_price, self.project_id)
            LOG.exception(msg)
            raise exception.GringottsException(message=msg)

        return models.BalanceFrozenResult(user_id=account.user_id,
                                          project_id=account.project_id,
                                          balance=account.balance,
                                          frozen_balance=account.frozen_balance)

    @wsexpose(models.BalanceFrozenResult, body=models.BalanceFrozenBody)
    def unfreeze(self, data):
        self.conn = pecan.request.db_conn
        try:
            account = self.conn.unfreeze_balance(request.context,
                                                 self.project_id,
                                                 data.total_price)
        except (exception.ProjectNotFound, exception.AccountNotFound):
            raise
        except exception.NotSufficientFrozenBalance:
            raise
        except Exception:
            msg = "Fail to unfreeze balance %s of the project_id %s" % \
                (data.total_price, self.project_id)
            LOG.exception(msg)
            raise exception.GringottsException(message=msg)

        return models.BalanceFrozenResult(user_id=account.user_id,
                                          project_id=account.project_id,
                                          balance=account.balance,
                                          frozen_balance=account.frozen_balance)


class ProjectController(rest.RestController):
    """Manages operations on project."""

    _custom_actions = {
        'estimate': ['GET'],
    }

    def __init__(self, project_id, external_client):
        self._id = project_id
        self.external_client = external_client

    def _project(self):
        self.conn = pecan.request.db_conn
        try:
            project = self.conn.get_project(request.context,
                                            project_id=self._id)
        except Exception as e:
            LOG.error('project %s not found' % self._id)
            raise exception.ProjectNotFound(project_id=self._id)
        return project

    @pecan.expose()
    def _lookup(self, subpath, *remainder):
        if subpath == 'billing_owner':
            return (BillingOwnerController(self._id, self.external_client),
                    remainder)

    @wsexpose(models.Project)
    def get(self):
        """Return this project."""
        return models.Project.from_db_model(self._project())

    @wsexpose(models.Summaries, wtypes.text)
    def estimate(self, region_id=None):
        """Get estimation of specified project and region."""
        limit_user_id = acl.get_limited_to_user(request.headers,
                                                'project_estimate')

        if limit_user_id: # normal user
            projects = keystone.get_projects_by_user(limit_user_id)
            _project_ids = [project['id'] for project in projects]
            project_ids = [self._id] if self._id in _project_ids else []
        else: # accountant
            project_ids = [self._id]

        # good way to go
        conn = pecan.request.db_conn

        # Get all orders of this particular context one time
        orders_db = list(conn.get_orders(request.context,
                                         project_ids=project_ids,
                                         region_id=region_id,
                                         read_deleted=False,
                                         bill_methods=['hour']))

        total_price = gringutils._quantize_decimal(0)
        total_count = 0
        summaries = []

        # loop all order types
        for order_type in const.ORDER_TYPE:

            order_total_price = gringutils._quantize_decimal(0)
            order_total_count = 0

            # One user's order records will not be very large, so we can
            # traverse them directly
            for order in orders_db:
                if order.type != order_type:
                    continue
                order_total_price += order.unit_price * 24
                order_total_count += 1

            summaries.append(models.Summary.transform(total_count=order_total_count,
                                                      order_type=order_type,
                                                      total_price=order_total_price))
            total_price += order_total_price
            total_count += order_total_count

        return models.Summaries.transform(total_price=total_price,
                                          total_count=total_count,
                                          summaries=summaries)


class ProjectsController(rest.RestController):
    """Manages operations on the projects collection."""

    def __init__(self):
        self.external_client = app.external_client()

    @pecan.expose()
    def _lookup(self, project_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ProjectController(project_id, self.external_client), remainder

    @wsexpose([models.UserProject], wtypes.text, wtypes.text, wtypes.text)
    def get_all(self, user_id=None, type=None, duration=None):
        """Get all projects."""
        user_id = acl.get_limited_to_user(request.headers,
                                          'projects_get') or user_id
        self.conn = pecan.request.db_conn
        result = []

        if not type or type.lower() == 'pay':
            # if admin call this api, limit to admin's user_id
            if not user_id:
                user_id = request.context.user_id

            try:
                user_projects = self.conn.get_user_projects(request.context,
                                                            user_id=user_id)
            except Exception as e:
                LOG.exception('Fail to get all projects')
                raise exception.DBError(reason=e)

            project_ids = [up.project_id for up in user_projects]

            if not project_ids:
                LOG.warn('User %s has no payed projects' % user_id)
                return []

            projects = self._list_keystone_projects()

            for u, p in itertools.product(user_projects, projects):
                if u.project_id == p['id']:
                    billing_owner = p['users']['billing_owner']
                    project_owner = p['users']['project_owner']
                    project_creator = p['users']['project_creator']
                    up = models.UserProject(user_id=user_id,
                                            project_id=u.project_id,
                                            project_name=p['name'],
                                            user_consumption=u.user_consumption,
                                            project_consumption=u.project_consumption,
                                            billing_owner=dict(user_id=billing_owner.get('id') if billing_owner else None,
                                                               user_name=billing_owner.get('name') if billing_owner else None),
                                            project_owner=dict(user_id=project_owner.get('id') if project_owner else None,
                                                               user_name=project_owner.get('name') if project_owner else None),
                                            project_creator=dict(user_id=project_creator.get('id') if project_creator else None,
                                                                 user_name=project_creator.get('name') if project_creator else None),
                                            is_historical=u.is_historical,
                                            created_at=timeutils.parse_isotime(p['created_at']) if p['created_at'] else None)
                    result.append(up)
        elif type.lower() == 'all':
            # if admin call this api, limit to admin's user_id
            if not user_id:
                user_id = request.context.user_id

            k_projects = keystone.get_project_list(name=user_id)
            project_ids = [p['id'] for p in k_projects]

            if not project_ids:
                LOG.warn('User %s has no projects' % user_id)
                return []

            try:
                g_projects = self.conn.get_projects_by_project_ids(request.context,
                                                                   project_ids)
            except Exception as e:
                LOG.exception('Fail to get all projects')
                raise exception.DBError(reason=e)
            for k, g in itertools.product(k_projects, g_projects):
                if k['id'] == g.project_id:
                    billing_owner = k['users']['billing_owner']
                    project_owner = k['users']['project_owner']
                    project_creator = k['users']['project_creator']
                    up = models.UserProject(user_id=user_id,
                                            project_id=g.project_id,
                                            project_name=k['name'],
                                            project_consumption=g.consumption,
                                            billing_owner=dict(user_id=billing_owner.get('id') if billing_owner else None,
                                                               user_name=billing_owner.get('name') if billing_owner else None),
                                            project_owner=dict(user_id=project_owner.get('id') if project_owner else None,
                                                               user_name=project_owner.get('name') if project_owner else None),
                                            project_creator=dict(user_id=project_creator.get('id') if project_creator else None,
                                                                 user_name=project_creator.get('name') if project_creator else None),
                                            is_historical=False,
                                            created_at=timeutils.parse_isotime(k['created_at']) if k['created_at'] else None)
                    result.append(up)

        elif type.lower() == 'simple':
            duration = gringutils.normalize_timedelta(duration)
            if duration:
                active_from = datetime.datetime.utcnow() - duration
            else:
                active_from = None
            g_projects = list(self.conn.get_projects(request.context,
                                                     user_id=user_id,
                                                     active_from=active_from))
            project_ids = [p.project_id for p in g_projects]

            if not project_ids:
                LOG.warn('User %s has no payed projects' % user_id)
                return []

            k_projects = self._list_keystone_projects()

            for k, g in itertools.product(k_projects, g_projects):
                if k.id == g.project_id:
                    up = models.UserProject(project_id=g.project_id,
                                            project_name=k.name,
                                            domain_id=g.domain_id,
                                            billing_owner=dict(user_id=g.user_id))
                    result.append(up)

        return result

    def _list_keystone_projects(self):
        projects = []
        domain_ids = \
            [domain.id for domain in keystone.get_domain_list()]
        for domain_id in domain_ids:
            projects.extend(keystone.get_project_list(domain_id))
        return projects

    @wsexpose(None, body=models.Project)
    def post(self, data):
        """Create a new project."""
        conn = pecan.request.db_conn
        try:
            project = db_models.Project(**data.as_dict())
            return conn.create_project(request.context, project)
        except Exception:
            LOG.exception('Fail to create project: %s' % data.as_dict())
            raise exception.ProjectCreateFailed(project_id=data.project_id,
                                                user_id=data.user_id)
