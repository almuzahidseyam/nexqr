import base64
import io
import json
from unittest.mock import patch, MagicMock
from PIL import Image
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from .models import DynamicQR, DailyBudget
from .views import reserve_budget
from .artistic import generate_art, bounded_response

TEST_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class OwnershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user(
            "alice", password="a-test-only-long-password"
        )
        cls.bob = get_user_model().objects.create_user(
            "bob", password="a-test-only-long-password", is_staff=True
        )
        cls.owned = DynamicQR.objects.create(
            owner=cls.alice,
            name="Alice private name",
            original_url="https://example.com",
        )
        cls.legacy = DynamicQR.objects.create(
            name="Legacy unassigned", original_url="https://example.org"
        )

    def test_anonymous_cannot_manage_or_generate(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(
            self.client.get(
                reverse("analytics_view", args=[self.owned.short_code])
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post("/generate/", {"url": "https://example.com"}).status_code,
            401,
        )
        self.assertEqual(self.client.get("/generate/").status_code, 405)
        self.assertEqual(DynamicQR.objects.count(), 2)

    def test_owner_boundary_including_staff_and_legacy(self):
        self.client.force_login(self.bob)
        response = self.client.get("/")
        self.assertNotContains(response, "Alice private name")
        self.assertNotContains(response, "Legacy unassigned")
        for entry in [self.owned, self.legacy]:
            self.assertEqual(
                self.client.get(
                    reverse("analytics_view", args=[entry.short_code])
                ).status_code,
                404,
            )
        self.client.force_login(self.alice)
        self.assertContains(self.client.get("/"), "Alice private name")
        self.assertNotContains(self.client.get("/"), "Legacy unassigned")
        self.assertEqual(
            self.client.get(
                reverse("analytics_view", args=[self.owned.short_code])
            ).status_code,
            200,
        )

    def test_public_existing_links_continue_without_personal_tracking(self):
        for entry in [self.owned, self.legacy]:
            response = self.client.get(
                reverse("redirect_qr", args=[entry.short_code]),
                HTTP_X_FORWARDED_FOR="1.2.3.4",
                HTTP_USER_AGENT="Mobile sensitive identifier",
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, entry.original_url)
            scan = entry.scans.get()
            self.assertIsNone(scan.ip_address)
            self.assertIsNone(scan.user_agent)
            self.assertEqual(scan.device_type, "Mobile")

    def test_generation_owns_records_and_produces_real_png(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            "/generate/",
            {
                "type": "dynamic",
                "url": "https://example.net",
                "name": "New owned code",
                "owner": self.bob.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        entry = DynamicQR.objects.get(name="New owned code")
        self.assertEqual(entry.owner, self.alice)
        with Image.open(
            io.BytesIO(base64.b64decode(response.json()["qr_image"].split(",")[1]))
        ) as image:
            self.assertEqual(image.format, "PNG")
            image.verify()
        before = DynamicQR.objects.count()
        self.assertEqual(
            self.client.post(
                "/generate/", {"type": "standard", "url": "https://example.net"}
            ).status_code,
            200,
        )
        self.assertEqual(DynamicQR.objects.count(), before)

    def test_csrf_is_required_and_valid_form_token_works(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        self.assertEqual(
            client.post("/generate/", {"url": "https://example.com"}).status_code, 403
        )
        client.get("/")
        response = client.post(
            "/generate/",
            {
                "url": "https://example.com",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_form_inputs_are_escaped_and_invalid_urls_rejected(self):
        self.client.force_login(self.alice)
        self.assertNotContains(
            self.client.get("/", {"name": "<script>alert(1)</script>"}),
            "<script>alert(1)</script>",
        )
        for url in [
            "javascript:alert(1)",
            "ftp://example.com",
            "https://user:pass@example.com",
            "https://example.com/" + "a" * 2000,
        ]:
            self.assertEqual(
                self.client.post("/generate/", {"url": url}).status_code, 400
            )
        self.assertEqual(
            self.client.post("/generate/", {"type": "unknown"}).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                "/generate/", {"type": "secure", "encrypted_payload": "x" * 10001}
            ).status_code,
            400,
        )

    @override_settings(QR_DAILY_LIMIT=2)
    def test_per_user_budget_and_retired_extension_endpoint(self):
        self.client.force_login(self.alice)
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    "/generate/", {"url": "https://example.com"}
                ).status_code,
                200,
            )
        self.assertEqual(
            self.client.post("/generate/", {"url": "https://example.com"}).status_code,
            429,
        )
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.post("/generate/", {"url": "https://example.com"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/generate/",
                {"url": "https://example.com"},
                HTTP_ORIGIN="chrome-extension://anything",
            ).status_code,
            410,
        )

    @patch("core.views.generate_art")
    @override_settings(
        ARTISTIC_ENABLED=True,
        REPLICATE_API_TOKEN="fixture",
        REPLICATE_MODEL_VERSION="a" * 64,
        ARTISTIC_DAILY_LIMIT=1,
    )
    def test_artistic_requires_staff_and_global_budget(self, art):
        data = {
            "type": "artistic",
            "url": "https://example.com",
            "prompt": "green garden",
        }
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post("/generate/", data).status_code, 403)
        art.assert_not_called()
        self.client.force_login(self.bob)
        art.return_value = b"fixture-image"
        self.assertEqual(self.client.post("/generate/", data).status_code, 200)
        self.assertEqual(self.client.post("/generate/", data).status_code, 429)
        art.assert_called_once()

    @patch(
        "core.views.generate_art", side_effect=RuntimeError("private-provider-token")
    )
    @override_settings(
        ARTISTIC_ENABLED=True,
        REPLICATE_API_TOKEN="fixture",
        REPLICATE_MODEL_VERSION="a" * 64,
        ARTISTIC_DAILY_LIMIT=1,
    )
    def test_failed_provider_deletes_incomplete_row_but_keeps_budget(self, art):
        self.client.force_login(self.bob)
        count = DynamicQR.objects.count()
        response = self.client.post(
            "/generate/",
            {"type": "artistic", "url": "https://example.com", "prompt": "garden"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private-provider-token", response.content.decode())
        self.assertEqual(DynamicQR.objects.count(), count)
        self.assertEqual(DailyBudget.objects.get(key="artistic:global").used, 1)

    def test_encrypted_public_view_does_not_expose_management(self):
        secure = DynamicQR.objects.create(
            owner=self.alice,
            is_encrypted=True,
            encrypted_payload="</script><script>alert(1)</script>",
            name="Private title",
        )
        response = self.client.get(reverse("secure_view", args=[secure.short_code]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "Private title")


class BudgetTests(TestCase):
    def test_atomic_conditional_increment_cannot_exceed_limit(self):
        self.assertTrue(reserve_budget("test", 1))
        self.assertFalse(reserve_budget("test", 1))
        self.assertEqual(DailyBudget.objects.get(key="test").used, 1)


@override_settings(
    REPLICATE_API_TOKEN="test-only-secret", REPLICATE_MODEL_VERSION="a" * 64
)
class ProviderTests(TestCase):
    @patch("core.artistic.bounded_response")
    def test_fixed_hosts_no_token_on_image_request_and_png_conversion(self, response):
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "white").save(buffer, format="JPEG")
        response.side_effect = [
            json.dumps(
                {
                    "id": "abc",
                    "status": "succeeded",
                    "output": ["https://replicate.delivery/a.jpg"],
                }
            ).encode(),
            buffer.getvalue(),
        ]
        image = generate_art("https://example.com/r/code/", "garden")
        self.assertTrue(image.startswith(b"\x89PNG"))
        self.assertNotIn("headers", response.call_args_list[1].kwargs)
        self.assertEqual(
            response.call_args_list[0].kwargs["headers"]["Cancel-After"], "1m"
        )

    @patch("core.artistic.bounded_response")
    def test_reject_provider_image_redirect_destinations(self, response):
        for url in [
            "http://127.0.0.1/a",
            "https://replicate.delivery.evil.test/a",
            "https://user:pass@replicate.delivery/a",
            "https://replicate.delivery:8443/a",
        ]:
            response.reset_mock()
            response.return_value = json.dumps(
                {"id": "abc", "status": "succeeded", "output": [url]}
            ).encode()
            with self.assertRaises(ValueError):
                generate_art("https://example.com", "garden")
            self.assertEqual(response.call_count, 1)

    def test_download_rejects_redirects_and_oversize(self):
        session = MagicMock()
        response = session.request.return_value.__enter__.return_value
        response.status_code = 302
        with self.assertRaises(ValueError):
            bounded_response(session, "GET", "https://example.com", 5)
        self.assertFalse(session.request.call_args.kwargs["allow_redirects"])
        response.status_code = 200
        response.iter_content.return_value = [b"123456"]
        with self.assertRaises(ValueError):
            bounded_response(session, "GET", "https://example.com", 5)


class LegacyMigrationTests(TransactionTestCase):
    def test_existing_records_keep_code_and_become_unassigned(self):
        executor = MigrationExecutor(connection)
        old = [("core", "0003_dynamicqr_is_artistic_dynamicqr_prompt")]
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            apps.get_model("core", "DynamicQR").objects.create(
                name="Legacy migration fixture",
                short_code="old123",
                original_url="https://example.com",
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            row = DynamicQR.objects.get(short_code="old123")
            self.assertIsNone(row.owner_id)
            self.assertEqual(row.original_url, "https://example.com")
        finally:
            MigrationExecutor(connection).migrate(latest)
