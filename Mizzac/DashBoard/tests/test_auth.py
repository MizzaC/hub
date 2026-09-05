from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationPagesTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("dashboard:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")

    def test_signup_page_renders(self):
        response = self.client.get(reverse("dashboard:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscription")

    def test_logout_uses_post(self):
        user = get_user_model().objects.create_user(username="alice", password="test-pass")
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("dashboard:logout")).status_code, 405)
        response = self.client.post(reverse("dashboard:logout"))

        self.assertRedirects(response, reverse("dashboard:login"))

