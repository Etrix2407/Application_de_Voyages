"""Envoi des e-mails dans les tests (partagé par toutes les applications)."""

from unittest import mock


def _run_now(func, robust=False):
    func()


class SendEmailsImmediately:
    """À placer avant TestCase : les e-mails partent tout de suite, comme hors transaction sur le site.

    Un TestCase n'achève jamais sa transaction : sans ce réglage, les envois prévus après sa
    validation (on_commit) n'auraient jamais lieu. L'envoi après validation est vérifié dans test_emails.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        patcher = mock.patch("accounts.services.emails.on_commit", _run_now)
        patcher.start()
        cls.addClassCleanup(patcher.stop)
