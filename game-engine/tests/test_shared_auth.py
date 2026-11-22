"""game-engine uses the shared token check (shared/tquest_auth.py): plain usernames in dev, signed tokens in prod."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from fastapi.testclient import TestClient
    from game_engine import app as appmod
    from game_engine.store import MemoryStore
    import tquest_auth
    HAVE_WEB = True
except ImportError:
    HAVE_WEB = False

SECRET = "k" * 32


@unittest.skipUnless(HAVE_WEB, "fastapi not installed")
class SharedAuthTests(unittest.TestCase):
    def setUp(self):
        appmod.set_store(MemoryStore())
        self.c = TestClient(appmod.app)

    def test_dev_accepts_plain_username(self):
        with patch.dict(os.environ, {"APP_ENV": "dev"}):
            self.assertEqual(self.c.get("/me/rank", headers={"Authorization": "Bearer ann"}).status_code, 200)

    def test_prod_needs_signed_token(self):
        with patch.dict(os.environ, {"APP_ENV": "prod", "TOKEN_SECRET": SECRET}):
            self.assertEqual(self.c.get("/me/rank", headers={"Authorization": "Bearer ann"}).status_code, 401)
            self.assertEqual(self.c.get("/me/rank").status_code, 401)
            good = tquest_auth.issue_token("annTwo", SECRET)
            self.assertEqual(self.c.get("/me/rank", headers={"Authorization": "Bearer " + good}).status_code, 200)
            old = tquest_auth.issue_token("annTwo", SECRET, ttl_s=1, now=1)
            self.assertEqual(self.c.get("/me/rank", headers={"Authorization": "Bearer " + old}).status_code, 401)
            bad = tquest_auth.issue_token("annTwo", "z" * 32)
            self.assertEqual(self.c.get("/me/rank", headers={"Authorization": "Bearer " + bad}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
