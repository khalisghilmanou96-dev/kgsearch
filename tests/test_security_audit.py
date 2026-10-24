import inspect
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawler"))

import frontier_runner
import safe_http
from frontier_runner import robots_allowed
from general_index import extract_page
from network_safety import validate_url


class SecurityAudit(unittest.TestCase):

    def test_private_destinations(self):
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/",
            "http://localhost/",
            "file:///etc/passwd",
            "http://user:password@example.com/",
            "http://example.com:8080/",
        ):
            with self.subTest(url=url):
                with self.assertRaises((ValueError, OSError)):
                    validate_url(url)

    def test_dns_rebinding_blocked_at_connection(self):
        fake_dns = [(
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("127.0.0.1", 443),
        )]
        with patch("socket.getaddrinfo", return_value=fake_dns):
            with patch("socket.socket") as fake_socket:
                with self.assertRaises(OSError):
                    safe_http.guarded_create_connection(
                        ("example.com", 443)
                    )
                fake_socket.assert_not_called()

    def test_mixed_dns_answers_blocked(self):
        fake_dns = [
            (socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, "", ("93.184.215.14", 443)),
            (socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, "", ("192.168.1.1", 443)),
        ]
        with patch("socket.getaddrinfo", return_value=fake_dns):
            with patch("socket.socket") as fake_socket:
                with self.assertRaises(OSError):
                    safe_http.guarded_create_connection(
                        ("example.com", 443)
                    )
                fake_socket.assert_not_called()

    def test_proxy_environment_disabled(self):
        session = safe_http.create_session()
        self.assertFalse(session.trust_env)
        self.assertIsInstance(
            session.get_adapter("https://"),
            safe_http.SafeHTTPAdapter
        )

    def test_robots_disallow(self):
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.text = (
            "User-agent: *\nDisallow: /private/\n"
        )
        self.assertFalse(robots_allowed(
            session, "https://example.com/private/page"
        ))
        self.assertTrue(robots_allowed(
            session, "https://example.com/public/page"
        ))

    def test_robots_redirect_refused(self):
        session = Mock()
        session.get.return_value.status_code = 301
        self.assertFalse(robots_allowed(
            session, "https://example.com/private"
        ))
        self.assertFalse(
            session.get.call_args.kwargs["allow_redirects"]
        )

    def test_robots_server_failure_refused(self):
        session = Mock()
        session.get.return_value.status_code = 503
        self.assertFalse(robots_allowed(
            session, "https://example.com/private"
        ))

    def test_meta_noindex(self):
        html = (
            "<html><head>"
            "<meta name='robots' content='noindex'>"
            "</head><body>Private content</body></html>"
        )
        self.assertIsNone(extract_page(
            "https://example.com/private", html
        ))

    def test_crawler_does_not_follow_redirects(self):
        source = inspect.getsource(frontier_runner.run)
        self.assertIn("allow_redirects=False", source)
        self.assertIn("validate_url(candidate_url)", source)

    def test_crawler_size_and_header_protection(self):
        source = inspect.getsource(frontier_runner.run)
        self.assertIn("2_000_001", source)
        self.assertIn("2_000_000", source)
        self.assertIn("Content-Length", source)
        self.assertIn("X-Robots-Tag", source)
        self.assertIn("noindex", source)


if __name__ == "__main__":
    unittest.main()
