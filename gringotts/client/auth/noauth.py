from gringotts.client.auth import BaseAuthPlugin


class NoauthPlugin(BaseAuthPlugin):

    def __init__(self,
                 endpoint=None):
        self.endpoint = endpoint

    def get_auth_headers(self, **kwargs):
        return {'X-Auth-Method': 'Noauth'}

    def get_endpoint(self):
        return self.endpoint
