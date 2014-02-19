from gringotts.tests.api import FunctionalTest


class TestBase(FunctionalTest):

    def test_bad_uri(self):
        response = self.get_json('/bad/path',
                                 expect_errors=True,
                                 headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "application/json")
