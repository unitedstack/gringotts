import pecan
import wsme

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose
from wsme import types as wtypes

from oslo_config import cfg

from gringotts import constants as const
from gringotts.api import app
from gringotts.api.v2 import models
from gringotts.db import models as db_models
from gringotts.openstack.common import log
from gringotts import utils as gringutils
from gringotts import exception


LOG = log.getLogger(__name__)


class BillingOwnerController(rest.RestController):

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


class ProjectController(rest.RestController):
    """Manages operations on project."""

    def __init__(self, project_id, external_client):
        self._id = project_id
        self.external_client = external_client

    def _project(self):
        self.conn = pecan.request.db_conn
        try:
            project = self.conn.get_project(request.context,
                                            project_id=self._id)
        except Exception as e:
            LOG.error('project %s no found' % self._id)
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


class ProjectsController(rest.RestController):
    """Manages operations on the accounts collection."""

    def __init__(self):
        self.external_client = app.external_client()

    @pecan.expose()
    def _lookup(self, project_id, *remainder):
        if remainder and not remainder[-1]:
            remainder = remainder[:-1]
        return ProjectController(project_id, self.external_client), remainder

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
