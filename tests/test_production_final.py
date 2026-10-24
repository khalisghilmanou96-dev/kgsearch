import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawler"))

from frontier_runner import prioritize_domains, robots_allowed
from general_index import extract_page
from link_discovery import discover_links
from network_safety import validate_url


class ProductionFinalTests(unittest.TestCase):
    def test_private_urls(self):
        for url in (
            "http://127.0.0.1/",
            "http://192.168.1.1/",
            "http://localhost/",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url):
                with self.assertRaises((ValueError, OSError)):
                    validate_url(url)

    def test_robots_disallow(self):
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.text = (
            "User-agent: *\nDisallow: /private/\n"
        )
        self.assertFalse(
            robots_allowed(session, "https://example.com/private/page")
        )
        self.assertTrue(
            robots_allowed(session, "https://example.com/public/page")
        )

    def test_robots_unavailable_is_denied(self):
        session = Mock()
        session.get.return_value.status_code = 503
        self.assertFalse(
            robots_allowed(session, "https://example.com/page")
        )

    def test_meta_noindex(self):
        self.assertIsNone(extract_page(
            "https://example.com/",
            "<html><head><meta name='robots' content='noindex'></head>"
            "<body>Texte visible</body></html>",
        ))

    def test_tracking_deduplication(self):
        html = (
            '<a href="/page?utm_source=a">A</a>'
            '<a href="/page?utm_source=b">B</a>'
            '<a href="https://example.org/news">C</a>'
        )
        links = discover_links("https://example.com/", html)
        self.assertEqual(len(links), 2)

    def test_domain_diversity(self):
        rows = [
            ("https://a.example.com/1", None),
            ("https://a.example.com/2", None),
            ("https://b.example.org/1", None),
        ]
        ordered = prioritize_domains(rows)
        self.assertEqual(ordered[1][0], rows[2][0])


if __name__ == "__main__":
    unittest.main()
