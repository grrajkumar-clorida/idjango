from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from infra.views import PENDING_BREEZE_SESSION_KEY

User = get_user_model()

DESK_URL_NAMES = (
    "sma50-dashboard",
    "desk_review",
    "desk_orders",
    "desk_positions",
    "admin_dashboard",
    "stock_dashboard",
    "api:system_status",
)


class GuestPublicSiteTests(TestCase):
    def test_home_is_public_and_hides_desk_links(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sign in")
        self.assertContains(resp, reverse("login"))
        self.assertContains(resp, reverse("about"))
        self.assertContains(resp, "heroCarousel")
        self.assertContains(resp, "CCTV")
        self.assertContains(resp, "Car ECM")
        self.assertContains(resp, "AC service")
        self.assertContains(resp, "Python")
        self.assertContains(resp, "Ecommerce")
        self.assertContains(resp, "Digital marketing")
        self.assertContains(resp, "/static/img/slides/cctv.jpg")
        for name in ("sma50-dashboard", "desk_review", "desk_orders", "desk_positions"):
            self.assertNotContains(resp, reverse(name))

    def test_about_is_public(self):
        resp = self.client.get(reverse("about"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("desk_review"))

    def test_desk_urls_redirect_to_login(self):
        login_url = reverse("login")
        for name in DESK_URL_NAMES:
            url = reverse(name)
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, name)
            self.assertTrue(resp.url.startswith(login_url), name)

    def test_mutating_api_requires_login(self):
        resp = self.client.post(reverse("api:emergency_stop"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith(reverse("login")))


class AuthenticatedDeskNavTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gobiraj", password="pass-word-1")
        self.client.force_login(self.user)

    def test_home_shows_desk_links(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("sma50-dashboard"))
        self.assertContains(resp, reverse("desk_review"))
        self.assertContains(resp, reverse("desk_orders"))
        self.assertContains(resp, reverse("desk_positions"))
        self.assertContains(resp, "gobiraj")

    def test_logout_get_does_not_log_out(self):
        resp = self.client.get(reverse("logout"))
        self.assertEqual(resp.status_code, 405)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, reverse("desk_review"))

    def test_logout_post_returns_to_public_home(self):
        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("home"))
        home = self.client.get(reverse("home"))
        self.assertNotContains(home, reverse("desk_review"))
        self.assertContains(home, reverse("login"))


class LoginSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gobiraj", password="pass-word-1")

    def test_rejects_open_redirect(self):
        resp = self.client.post(
            reverse("login"),
            {
                "username": "gobiraj",
                "password": "pass-word-1",
                "next": "https://evil.example/",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("desk_review"))
        self.assertNotIn("evil.example", resp.url)

    def test_allows_local_next(self):
        resp = self.client.post(
            reverse("login"),
            {
                "username": "gobiraj",
                "password": "pass-word-1",
                "next": reverse("desk_positions"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("desk_positions"))

    def test_bad_password_does_not_reveal_user(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "gobiraj", "password": "wrong"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid username or password")
        self.assertNotContains(resp, "gobiraj does not exist")


class BreezeCallbackAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gobiraj", password="pass-word-1")

    @patch("infra.views.set_breeze_session")
    def test_guest_does_not_store_token(self, mock_set):
        resp = self.client.get("/?apisession=56456543")
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_not_called()
        self.assertEqual(
            self.client.session[PENDING_BREEZE_SESSION_KEY],
            "56456543",
        )
        self.assertTrue(resp.url.startswith(reverse("login")))

    @patch("infra.views.set_breeze_session")
    def test_login_applies_pending_token(self, mock_set):
        self.client.get("/?apisession=56456543")
        resp = self.client.post(
            reverse("login"),
            {"username": "gobiraj", "password": "pass-word-1"},
        )
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_called_once_with("56456543")
        self.assertNotIn(PENDING_BREEZE_SESSION_KEY, self.client.session)

    @patch("infra.views.set_breeze_session")
    @patch("infra.views.session_status", return_value={"source": "test", "preview": "x"})
    def test_authenticated_applies_token(self, _status, mock_set):
        self.client.force_login(self.user)
        resp = self.client.get("/?apisession=56456543")
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_called_once_with("56456543")

    @patch("infra.views.set_breeze_session")
    def test_invalid_token_rejected(self, mock_set):
        resp = self.client.get("/?apisession=bad token")
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_not_called()
        self.assertNotIn(PENDING_BREEZE_SESSION_KEY, self.client.session)


class ApiCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gobiraj", password="pass-word-1")
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.user)

    def test_emergency_stop_requires_csrf(self):
        resp = self.csrf_client.post(reverse("api:emergency_stop"))
        self.assertEqual(resp.status_code, 403)
