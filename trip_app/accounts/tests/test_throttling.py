import tempfile
import time
from unittest import mock

from django.test import SimpleTestCase, override_settings

from accounts.services.throttling import Limiter


class FileCacheWindowTests(SimpleTestCase):
    """Le cache de production (fichiers) : la fenêtre doit durer `window_seconds`, pas 5 minutes."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        backend = "django.core.cache.backends.filebased.FileBasedCache"
        settings_override = override_settings(CACHES={"default": {"BACKEND": backend, "LOCATION": folder.name}})
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.limiter = Limiter("test-window", max_attempts=2, window_seconds=15 * 60)
        self.start = time.time()

    def at(self, seconds: float):
        """Horloge figée `seconds` après le début (lue par le limiteur comme par le cache)."""
        return mock.patch("time.time", return_value=self.start + seconds)

    def test_window_lasts_window_seconds(self):
        with self.at(0):
            self.limiter.record("marie@example.com")
        with self.at(60):
            self.limiter.record("marie@example.com")

        with self.at(14 * 60):
            self.assertTrue(self.limiter.is_locked("marie@example.com"))
        with self.at(15 * 60 + 1):
            self.assertFalse(self.limiter.is_locked("marie@example.com"))

    def test_reserve_refuses_once_limit_reached(self):
        with self.at(0):
            results = [self.limiter.reserve("marie@example.com") for _ in range(3)]

        self.assertEqual(results, [True, True, False])
