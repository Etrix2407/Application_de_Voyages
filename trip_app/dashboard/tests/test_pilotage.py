import time
from datetime import date
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_admin
from dashboard.services.cache import CACHE_DURATION, pilotage_snapshot
from dashboard.services.periods import DateBasis, Shortcut, custom_period, shortcut_period

# L'accès (administrateur seulement) est vérifié par la matrice d'accès (config/test_access.py).


class PilotageCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.march = custom_period(date(2026, 3, 1), date(2026, 3, 31))

    def test_computed_once_per_hour(self):
        started = time.time()
        with mock.patch("dashboard.services.cache.build_pilotage", return_value={}) as build:
            first = pilotage_snapshot(self.march)
            with mock.patch("time.time", return_value=started + CACHE_DURATION - 60):
                self.assertEqual(pilotage_snapshot(self.march), first)
            self.assertEqual(build.call_count, 1)

            with mock.patch("time.time", return_value=started + CACHE_DURATION + 60):
                pilotage_snapshot(self.march)
            self.assertEqual(build.call_count, 2)

    def test_one_entry_per_period(self):
        with mock.patch("dashboard.services.cache.build_pilotage", return_value={}) as build:
            pilotage_snapshot(self.march)
            pilotage_snapshot(custom_period(date(2026, 3, 1), date(2026, 3, 31), DateBasis.DEPARTURE))
            # Mêmes dates, mais comparé au mois civil précédent et non aux 31 jours d'avant.
            pilotage_snapshot(shortcut_period(Shortcut.THIS_MONTH, today=date(2026, 3, 15)))

        self.assertEqual(build.call_count, 3)


class PilotagePageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(create_admin())

    def test_shows_period_comparison_and_update_time(self):
        response = self.client.get(
            reverse("pilotage_dashboard"),
            {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.DEPARTURE, "start": "2026-03-01", "end": "2026-03-10"},
        )

        self.assertContains(response, "du 1 mars 2026 au 10 mars 2026 (la période choisie)")
        self.assertContains(response, "selon la date de départ")
        self.assertContains(response, "du 19 février 2026 au 28 février 2026 (la période précédente)")
        self.assertContains(response, "Dernière mise à jour : le ")

    def test_invalid_period_shows_errors_and_this_month(self):
        response = self.client.get(
            reverse("pilotage_dashboard"), {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.ORDERED}
        )

        self.assertContains(response, "Obligatoire pour une période personnalisée.")
        self.assertContains(response, "(ce mois-ci)")
