import pecan
import wsme
import datetime
import itertools

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo.config import cfg

from gringotts.api import acl
from gringotts import exception
from gringotts import utils as gringutils
from gringotts.api.v1 import models
from gringotts.db import models as db_models
from gringotts.services import keystone
from gringotts.checker import notifier
from gringotts.openstack.common import log
from gringotts.openstack.common import uuidutils
from gringotts.openstack.common import timeutils

OPTS = []

CONF = cfg.CONF
CONF.register_opts(OPTS)

LOG = log.getLogger(__name__)


class ProjectController(rest.RestController):
    """Manages operations on project
    """

    _custom_actions = {
        'billing_owner': ['PUT'],
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

    @wsexpose(models.Project, wtypes.text)
    def billing_owner(self, user_id):
        """Change billing_owner of this project"""
        self.conn = pecan.request.db_conn
        project = self.conn.change_billing_owner(request.context,
                                                 project_id=self._id,
                                                 user_id=user_id)
        return project


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
        if user_id is None:
            user_id = request.headers.get('X-User-Id')

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
