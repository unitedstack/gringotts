from pecan import rest
from wsmeext.pecan import wsexpose

from gringotts.api.noauth.controller import NoAuthController


class RootController(rest.RestController):

    noauth = NoAuthController()
