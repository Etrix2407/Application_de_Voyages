from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.models import Destination

from .factories import TEST_MEDIA_ROOT, TemporaryMediaMixin, create_country, create_destination, make_image


class DestinationPhotoTests(TemporaryMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(create_agent())
        self.country = create_country()

    def create(self, photo):
        return self.client.post(
            reverse("manage_create_destination", args=[self.country.pk]),
            {"name": "Kyoto", "description": "Temples.", "active": "on", "photo": photo},
        )

    def test_upload_saves_photo_under_random_name(self):
        response = self.create(make_image("Photo de Marie Dupont.png"))

        self.assertEqual(response.status_code, 302)
        photo = Destination.objects.get().photo
        self.assertTrue(photo.name.startswith("destinations/"))
        self.assertNotIn("Marie", photo.name)
        self.assertTrue((TEST_MEDIA_ROOT / photo.name).exists())

    def test_jpeg_png_and_webp_accepted(self):
        for name, image_format in [("a.jpg", "JPEG"), ("b.png", "PNG"), ("c.webp", "WEBP")]:
            with self.subTest(image_format=image_format):
                self.assertEqual(self.create(make_image(name, image_format)).status_code, 302)

    def test_invalid_files_rejected(self):
        cases = {
            "texte renommé en .jpg": SimpleUploadedFile("faux.jpg", b"pas une image", "image/jpeg"),
            "GIF": make_image("anim.gif", "GIF"),
            "GIF renommé en .jpg": make_image("anim.jpg", "GIF"),
        }
        for reason, photo in cases.items():
            with self.subTest(reason=reason):
                response = self.create(photo)

                self.assertEqual(response.status_code, 200)
                self.assertFalse(Destination.objects.exists())

    def test_photo_over_size_limit_rejected(self):
        with mock.patch("catalog.validators.MAX_PHOTO_SIZE", 10):
            response = self.create(make_image())

        self.assertContains(response, "5 Mo")
        self.assertFalse(Destination.objects.exists())

    def test_replacing_photo_deletes_old_file(self):
        destination = create_destination(self.country, photo=make_image("ancienne.png"))
        old_file = TEST_MEDIA_ROOT / destination.photo.name

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("manage_edit_destination", args=[destination.pk]),
                {"name": "Kyoto", "description": "x", "active": "on", "photo": make_image("nouvelle.png")},
            )

        destination.refresh_from_db()
        self.assertFalse(old_file.exists())
        self.assertTrue((TEST_MEDIA_ROOT / destination.photo.name).exists())

    def test_deleting_destination_deletes_photo(self):
        destination = create_destination(self.country, photo=make_image())
        photo_file = TEST_MEDIA_ROOT / destination.photo.name

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("manage_delete_destination", args=[destination.pk]))

        self.assertFalse(photo_file.exists())

    def test_photo_shown_to_clients(self):
        destination = create_destination(self.country, "Kyoto", photo=make_image())
        self.client.force_login(create_client())

        response = self.client.get(reverse("destination_detail", args=[destination.pk]))

        self.assertContains(response, f'src="{destination.photo.url}"')
        self.assertContains(response, 'alt="Photo : Kyoto"')
