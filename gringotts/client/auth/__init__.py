import abc
import six


@six.add_metaclass(abc.ABCMeta)
class BaseAuthPlugin(object):

    @abc.abstractmethod
    def get_auth_headers(self, **kwargs):
        pass

    @abc.abstractmethod
    def get_endpoint(self):
        pass

    def filter_params(self, params):
        return params
