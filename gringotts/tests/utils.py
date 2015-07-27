
"""Useful utilities for tests."""

import datetime

import six
import testtools


def remove_microsecond(adatetime):
    adatetime = datetime.datetime(year=adatetime.year,
                                  month=adatetime.month,
                                  day=adatetime.day,
                                  hour=adatetime.hour,
                                  minute=adatetime.minute,
                                  second=adatetime.second)
    return adatetime


def wip(message, run=True):
    """Mark a test as work in progress.

    Based on code by Nat Pryce:
    https://gist.github.com/npryce/997195#file-wip-py

    The test will always be run. If the test fails then a TestSkipped
    exception is raised. If the test passes an AssertionError exception
    is raised so that the developer knows they made the test pass. This
    is a reminder to remove the decorator.

    :param message: a string message to help clarify why the test is
                    marked as a work in progress
    :param run: whether or not to run test before raise AssertionError

    usage:
      >>> @wip('waiting on bug #000000')
      >>> def test():
      >>>     pass

    """

    def _wip(f):
        @six.wraps(f)
        def run_test(*args, **kwargs):
            if not run:
                raise testtools.testcase.TestSkipped(
                    'work in process test skipped: ' + message)
            try:
                f(*args, **kwargs)
            except Exception:
                raise testtools.testcase.TestSkipped(
                    'work in progress test failed: ' + message)

            raise AssertionError('work in progress test passed: ' + message)

        return run_test

    return _wip


class PricingTestMixin(object):

    @staticmethod
    def build_segmented_price_data(base_price, price_list):
        price = {
            'base_price': base_price,
            'type': 'segmented',
            'segmented': price_list
        }
        return price


class ServiceTestMixin(object):

    @staticmethod
    def build_project_info_from_keystone(
            project_name, project_id, domain_id,
            billing_owner_id, billing_owner_name,
            project_owner_id, project_owner_name,
            project_creator_id, project_creator_name):

        p = {
            'description': None,
            'name': project_name,
            'id': project_id,
            'domain_id': domain_id,
            'created_at': '2015-01-01 00:00:00',
        }
        users = {
            'billing_owner': {
                'id': billing_owner_id,
                'name': billing_owner_name,
            },
            'project_owner': {
                'id': project_owner_id,
                'name': project_owner_name,
            },
            'project_creator': {
                'id': project_creator_id,
                'name': project_creator_name,
            }
        }
        p['users'] = users

        return p

    @staticmethod
    def build_uos_user_info_from_keystone(
            user_id, name, email='email@example.com',
            real_name='real name', mobile_number='13012345678',
            company='company'):

        user = {
            'id': user_id,
            'name': name,
            'email': email,
            'real_name': real_name,
            'mobile_number': mobile_number,
            'company': company,
        }
        return user
