from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api.v1.controller import V1Controller
from gringotts.api.v2.controller import V2Controller


class RootController(rest.RestController):

    v1 = V1Controller()
    v2 = V2Controller()
