from django.test import TestCase

from accounts.services.client_search import matching_clients, search_words

from .factories import create_agent, create_client


class ClientSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.marie = create_client("marie.dupre@example.com", first_name="Marie", last_name="Dupré")
        create_agent("marie.agent@example.com", first_name="Marie", last_name="Dupré")

    def matches(self, query):
        return list(matching_clients(search_words(query))) == [self.marie]

    def test_ignores_accents_and_case(self):
        self.assertTrue(self.matches("DUPRE"))
        self.assertTrue(self.matches("dupré"))

    def test_all_words_must_match(self):
        self.assertTrue(self.matches("marie dupre"))
        self.assertFalse(self.matches("marie martin"))

    def test_searches_email(self):
        self.assertTrue(self.matches("dupre@example"))

    def test_empty_query_has_no_words(self):
        self.assertEqual(search_words("   "), [])
        self.assertEqual(search_words(None), [])
