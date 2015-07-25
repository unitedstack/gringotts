
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
