import pecan
import wsme
import datetime
import itertools

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts import constants as const
from gringotts.api import acl
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


class ProjectController(rest.RestController):
    """Manages operations on project
    """

    _custom_actions = {
        'billing_owner': ['PUT'],
        'get_billing_owner': ['GET'],
        'estimate': ['GET'],
    }

    def __init__(self, project_id):
        self._id = project_id

    def _project(self):
        self.conn = pecan.request.db_conn
        try:
            project = self.conn.get_project(request.context,
                                            project_id=self._id)
        except Exception as e:
            LOG.error('project %s not found' % self._id)
            raise exception.ProjectNotFound(project_id=self._id)
        return project

    @wsexpose(models.Project)
    def get(self):
        """Return this project"""
        return models.Project.from_db_model(self._project())

    @wsexpose(None, wtypes.text)
    def billing_owner(self, user_id):
        """Change billing_owner of this project"""
        self.conn = pecan.request.db_conn
        self.conn.change_billing_owner(request.context,
                                       project_id=self._id,
                                       user_id=user_id)

    @wsexpose(models.UserAccount)
    def get_billing_owner(self):
        self.conn = pecan.request.db_conn
        account = self.conn.get_project_billing_owner(request.context, self._id)
        return models.UserAccount.from_db_model(account)

    @wsexpose(models.Summaries, wtypes.text)
    def estimate(self, region_id=None):
        """Get estimation of specified project and region
        """
        limit_user_id, __ = acl.get_limited_to_accountant(request.headers)

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
                                         read_deleted=False))

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
    """Manages operations on the projects collection
    """
    @pecan.expose()
    def _lookup(self, project_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ProjectController(project_id), remainder

    @wsexpose([models.UserProject], wtypes.text, wtypes.text)
    def get_all(self, user_id=None, type=None):
        """Get all projects
        """
        user_id = acl.get_limited_to_user(request.headers) or user_id

        self.conn = pecan.request.db_conn
        result = []

        if not type or type.lower() == 'pay':
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

            projects = keystone.get_projects_by_project_ids(project_ids)

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
            k_projects = keystone.get_projects_by_user(user_id)
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
            g_projects = list(self.conn.get_projects(request.context, user_id=user_id))
            project_ids = [p.project_id for p in g_projects]

            if not project_ids:
                LOG.warn('User %s has no payed projects' % user_id)
                return []

            k_projects = keystone.get_projects_by_project_ids(project_ids)

            for k, g in itertools.product(k_projects, g_projects):
                if k['id'] == g.project_id:
                    up = models.UserProject(project_id=g.project_id,
                                            project_name=k['name'],
                                            domain_id=g.domain_id,
                                            billing_owner=dict(user_id=g.user_id))
                    result.append(up)

        return result

    @wsexpose(None, body=models.Project)
    def post(self, data):
        """Create a new project
        """
        conn = pecan.request.db_conn
        try:
            project = db_models.Project(**data.as_dict())
            return conn.create_project(request.context, project)
        except Exception:
            LOG.exception('Fail to create project: %s' % data.as_dict())
            raise exception.ProjectCreateFailed(project_id=data.project_id,
                                                user_id=data.user_id)
