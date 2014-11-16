from gringotts.tests import api


class FunctionalTest(api.FunctionalTest):
    PATH_PREFIX = '/v2'
