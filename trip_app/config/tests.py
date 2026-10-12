import re
from datetime import timedelta

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from common.text import duration_text


class HomeTests(TestCase):
    def test_page_in_french(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<html lang="fr">')

    def test_browser_spellcheck_disabled(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<body spellcheck="false">')

    def test_site_name_in_title_header_and_footer(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "<title>Accueil — Horizons Lointains</title>", html=False)
        self.assertContains(response, "Horizons Lointains", count=3)


class MenuCurrentPageTests(TestCase):
    def test_menu_marks_only_the_displayed_page(self):
        # Les filtres de l'adresse (?keyword=…) ne changent pas la page affichée.
        response = self.client.get(reverse("search"), {"keyword": "plage"})

        self.assertContains(response, 'aria-current="page"', count=1)
        self.assertContains(response, f'<a href="{reverse("search")}" aria-current="page">Rechercher</a>', html=True)


class SecurityHeaderTests(TestCase):
    def test_content_security_policy_forbids_inline_scripts_and_framing(self):
        response = self.client.get(reverse("home"))

        policy = response.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)


class ErrorPageTests(TestCase):
    def test_readable_not_found_page(self):
        response = self.client.get("/page-qui-n-existe-pas/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page introuvable", status_code=404)


class TemplateCommentTests(SimpleTestCase):
    def test_no_hash_comment_spans_several_lines(self):
        # {# … #} ne vaut que sur une ligne : au-delà, le texte s'affiche dans la page (et un « <form> »
        # cité dans ce texte fait ignorer le vrai formulaire par le navigateur).
        offending_lines = []
        for path in sorted((settings.BASE_DIR / "templates").rglob("*.html")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "{#" in line and "#}" not in line:
                    offending_lines.append(f"{path.relative_to(settings.BASE_DIR)}:{number}")
        self.assertEqual(offending_lines, [])


class LoginPageMarkupTests(TestCase):
    def test_login_page_has_a_single_form(self):
        html = self.client.get(reverse("login")).content.decode()

        self.assertEqual(html.count("<form"), 1)
        self.assertNotIn("{#", html)

class ErrorReportTests(SimpleTestCase):
    def test_error_report_hides_posted_fields_and_cookies(self):
        from django.test import RequestFactory
        from django.views.debug import get_exception_reporter_filter

        request = RequestFactory().post("/comptes/inscription/", {"email": "marie@example.com", "password1": "s3cret"})
        request.COOKIES["sessionid"] = "abc"
        reporter_filter = get_exception_reporter_filter(request)

        self.assertEqual(set(reporter_filter.get_post_parameters(request).values()), {"********************"})
        self.assertEqual(reporter_filter.get_safe_cookies(request), {"sessionid": "********************"})


class DurationTextTests(SimpleTestCase):
    def test_durations_in_words(self):
        cases = {
            timedelta(minutes=1): "une minute",
            timedelta(hours=1): "une heure",
            timedelta(hours=24): "24 heures",  # les délais annoncés en heures le restent
            timedelta(hours=72): "3 jours",
        }
        for duration, text in cases.items():
            with self.subTest(text=text):
                self.assertEqual(duration_text(duration), text)

    def test_less_than_a_minute_refused(self):
        with self.assertRaises(ValueError):
            duration_text(timedelta(seconds=30))


class DarkModeColorsTests(SimpleTestCase):
    def test_both_dark_mode_blocks_stay_identical(self):
        # Couleurs sombres écrites deux fois (réglage de l'appareil, choix du bouton) : CSS ne peut pas
        # les réunir sans JavaScript. Une couleur changée d'un seul côté donnerait deux modes sombres.
        css = (settings.BASE_DIR / "static" / "css" / "style.css").read_text(encoding="utf-8")
        blocks = re.findall(r':root(?::not\(\[data-theme="light"\]\)|\[data-theme="dark"\]) \{(.*?)\}', css, re.S)
        declarations = [sorted(re.findall(r"(--[\w-]+|color-scheme):\s*([^;]+);", block)) for block in blocks]

        self.assertEqual(len(declarations), 2)
        self.assertEqual(declarations[0], declarations[1])
