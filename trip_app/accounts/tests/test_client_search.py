from django.test import SimpleTestCase

from accounts.models import User
from accounts.services.client_search import client_matches, search_words


class ClientSearchTests(SimpleTestCase):
    marie = User(first_name="Marie", last_name="Dupré", email="marie.dupre@example.com")

    def matches(self, query):
        return client_matches(self.marie, search_words(query))

    def test_ignores_accents_and_case(self):
        self.assertTrue(self.matches("DUPRE"))
        self.assertTrue(self.matches("dupré"))

    def test_all_words_must_match(self):
        self.assertTrue(self.matches("marie dupre"))
        self.assertFalse(self.matches("marie martin"))

    def test_searches_email(self):
        self.assertTrue(self.matches("example.com"))

    def test_empty_query_has_no_words(self):
        self.assertEqual(search_words("   "), [])
        self.assertEqual(search_words(None), [])
