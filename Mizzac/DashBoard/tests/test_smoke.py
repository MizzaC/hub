from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class SharedApplicationSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="smoke-user")

    def setUp(self):
        self.client.force_login(self.user)

    def test_root_keeps_dashboard_redirect(self):
        response = self.client.get("/", follow=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/dashboard/")

    def test_main_application_pages_render(self):
        route_names = [
            "dashboard:dashboard",
            "drunkboard:drunkboard",
            "gameboard:gameboard",
            "toolboard:toolboard",
        ]

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

    def test_referenced_local_styles_exist(self):
        for asset in ["css/styles.css", "FundBoard/style.css", "GameBoard/style.css"]:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

