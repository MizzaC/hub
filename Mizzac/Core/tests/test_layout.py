import json
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class CurrentPageLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("aria-current") == "page":
            self.current_links.append(attributes.get("href"))


class SharedTablerLayoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="layout-user")

    def setUp(self):
        self.client.force_login(self.user)

    def test_primary_pages_render_with_local_shared_shell(self):
        routes = [
            "dashboard:dashboard",
            "drunkboard:drunkboard",
            "gameboard:gameboard",
            "toolboard:toolboard",
            "fundboard:fundboard",
            "fundboard:portfolio",
            "fundboard:accounts",
            "fundboard:transactions",
            "fundboard:subscriptions",
            "fundboard:revenues",
        ]

        for route_name in routes:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                html = response.content.decode()

                self.assertEqual(response.status_code, 200)
                self.assertIn("core/base.html", [template.name for template in response.templates])
                self.assertIn("/static/core/vendor/tabler/tabler.min.css", html)
                self.assertIn("/static/core/vendor/tabler/tabler.min.js", html)
                self.assertIn("/static/core/vendor/apexcharts/apexcharts.min.js", html)
                self.assertIn("/static/core/js/charts.js", html)
                self.assertIn("/static/core/js/currency.js", html)
                self.assertIn("/static/core/js/theme.js", html)
                self.assertIn('id="main-content"', html)
                self.assertNotIn("cdn.jsdelivr.net", html)
                self.assertNotIn("bootstrap@5.1.3", html)

    def test_main_navigation_identifies_current_application(self):
        routes = [
            "dashboard:dashboard",
            "drunkboard:drunkboard",
            "gameboard:gameboard",
            "toolboard:toolboard",
            "fundboard:fundboard",
        ]

        for route_name in routes:
            with self.subTest(route_name=route_name):
                expected_path = reverse(route_name)
                parser = CurrentPageLinkParser()
                parser.feed(self.client.get(expected_path).content.decode())

                self.assertIn(expected_path, parser.current_links)

    def test_shell_exposes_accessible_responsive_and_theme_controls(self):
        response = self.client.get(reverse("fundboard:accounts"))

        self.assertContains(response, 'class="btn btn-primary skip-link"')
        self.assertContains(response, 'id="themeToggle"')
        self.assertContains(response, 'aria-pressed="false"')
        self.assertContains(response, 'data-bs-target="#main-navigation"')
        self.assertContains(response, 'data-bs-target="#fundboard-navigation"')
        self.assertContains(response, 'aria-label="Navigation FundBoard"')

    def test_authentication_pages_also_use_tabler_without_cdn(self):
        self.client.logout()

        for route_name in ["dashboard:login", "dashboard:signup"]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                html = response.content.decode()

                self.assertEqual(response.status_code, 200)
                self.assertIn("/static/core/vendor/tabler/tabler.min.css", html)
                self.assertIn('class="form-control"', html)
                self.assertNotIn("cdn.jsdelivr.net", html)

    def test_frontend_versions_are_locked(self):
        lock_path = Path(settings.BASE_DIR).parent / "package-lock.json"
        lock_data = json.loads(lock_path.read_text())
        packages = lock_data["packages"]

        self.assertEqual(packages["node_modules/@tabler/core"]["version"], "1.4.0")
        self.assertEqual(packages["node_modules/@tabler/icons"]["version"], "3.46.0")
        self.assertEqual(packages["node_modules/apexcharts"]["version"], "7.1.0")
        self.assertNotIn("node_modules/chart.js", packages)
        self.assertEqual(
            packages["node_modules/apexcharts"]["engines"]["node"],
            "^20.19.0 || ^22.12.0 || >=24.0.0",
        )

    def test_versioned_assets_and_licenses_are_collectable(self):
        assets = [
            "core/vendor/tabler/tabler.min.css",
            "core/vendor/tabler/tabler.min.js",
            "core/vendor/tabler/LICENSE",
            "core/vendor/tabler-icons/home.svg",
            "core/vendor/tabler-icons/LICENSE",
            "core/vendor/apexcharts/apexcharts.min.js",
            "core/vendor/apexcharts/LICENSE",
            "core/css/app.css",
            "core/js/charts.js",
            "core/js/currency.js",
            "core/js/theme.js",
        ]

        for asset in assets:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

    def test_shared_layout_loads_local_apexcharts_once(self):
        response = self.client.get(reverse("fundboard:subscriptions"))
        html = response.content.decode()

        self.assertEqual(html.count("/static/core/vendor/apexcharts/apexcharts.min.js"), 1)
        self.assertEqual(html.count("/static/core/js/charts.js"), 1)
        self.assertIn("MizzacCharts.mount", html)
        self.assertNotIn("/static/core/vendor/chartjs/", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
