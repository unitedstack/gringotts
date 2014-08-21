import pecan
import wsme

from pecan import rest
from pecan import request
from wsmeext.pecan import wsexpose


class FixController(rest.RestController):
    """For one single order, getting its detail consumptions
    """
    @wsexpose(None)
    def get(self):
        """Return this order's detail
        """
        conn = pecan.request.db_conn
        resource_ids = []

        f = open('/tmp/resources.log')
        resources = f.readlines()
        f.close()

        for r in resources:
            resource_ids.append(r.strip('\n'))

        for resource_id in resource_ids:
            conn.fix_resource(request.context, resource_id)
