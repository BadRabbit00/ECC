import tempfile
import unittest
from pathlib import Path

from helpers import call


def post(path: Path, content: str | None = None, *, raw: bytes | None = None, tool="Write", root=None):
    if raw is not None:
        path.write_bytes(raw)
    elif content is not None:
        path.write_text(content)
    ti = {"file_path": str(path), "content": content or ""} if tool == "Write" else \
        {"file_path": str(path), "old_string": "a", "new_string": content or ""}
    return call("check_written", tool, ti, cwd=root or path.parent, project=root or path.parent)


def blocked(r):
    return r.get("decision") == "block"


def context(r):
    return r.get("hookSpecificOutput", {}).get("additionalContext", "")


class TestEncoding(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_bom_stripped(self):
        p = self.d / "a.py"
        self.assertFalse(blocked(post(p, raw=b"\xef\xbb\xbfprint(1)\n")))
        self.assertEqual(p.read_bytes(), b"print(1)\n")

    def test_mixed_endings_normalised(self):
        p = self.d / "a.py"
        post(p, raw=b"a\r\nb\nc\r\n")
        self.assertEqual(p.read_bytes(), b"a\nb\nc\n")

    def test_pure_crlf_kept_and_bat_kept(self):
        p = self.d / "a.txt"
        post(p, raw=b"a\r\nb\r\n")
        self.assertEqual(p.read_bytes(), b"a\r\nb\r\n")
        b = self.d / "run.bat"
        post(b, raw=b"a\r\nb\n")
        self.assertEqual(b.read_bytes(), b"a\r\nb\n")

    def test_not_utf8_blocks(self):
        self.assertTrue(blocked(post(self.d / "a.py", raw="привет".encode("cp1251"))))

    def test_binary_ignored(self):
        self.assertFalse(blocked(post(self.d / "a.png", raw=b"\x89PNG\x00\x01\xff")))


class TestSecrets(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "src").mkdir()
        (self.d / "test").mkdir()

    def w(self, rel, content, tool="Write"):
        return post(self.d / rel, content, tool=tool, root=self.d)

    def test_blocks_real_formats(self):
        for c in ['KEY = "AKIAIOSFODNN7EXAMPLE"', "-----BEGIN OPENSSH PRIVATE KEY-----\nabc",
                  'token = "ghp_' + "a" * 36 + '"', 'client = Anthropic(api_key="sk-ant-' + "x" * 30 + '")',
                  'DB_URL = "postgresql://app:Sup3rS3cret@db:5432/app"', 'password = "hunter2hunter2"',
                  'JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.c2lnbmF0dXJlLXNpZ25hdHVyZQ"']:
            with self.subTest(c=c):
                self.assertTrue(blocked(self.w("src/config.py", c)), c)

    def test_edit_checks_new_string(self):
        self.assertTrue(blocked(self.w("src/config.py", 'password = "hunter2hunter2"', tool="Edit")))

    def test_placeholders_pass(self):
        for c in ['password = os.environ["DB_PASSWORD"]', 'DB_PASSWORD="change-me-db"',
                  'url = "postgresql://app:${DB_PASSWORD}@db/app"', 'token = settings.api_token',
                  'password: "<your-password>"', 'api_key = "example-key-123"']:
            with self.subTest(c=c):
                self.assertFalse(blocked(self.w("src/config.py", c)), c)

    def test_env_file_is_the_right_place(self):
        self.assertFalse(blocked(self.w(".env", "DB_PASSWORD=hunter2hunter2\nTOKEN=ghp_" + "a" * 36)))
        self.assertTrue(blocked(self.w(".env.example", "TOKEN=ghp_" + "a" * 36)))

    def test_tests_may_hold_fake_passwords_not_keys(self):
        self.assertFalse(blocked(self.w("test/test_auth.py", 'password = "correct-horse-battery"')))
        self.assertTrue(blocked(self.w("test/test_auth.py", "-----BEGIN EC PRIVATE KEY-----")))

    def test_docs_example_jwt_ok(self):
        self.assertFalse(blocked(self.w("API.md",
            "Authorization: Bearer eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnbmF0dXJlLXNpZ25hdHVyZQ")))


class TestComposeLint(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_compose_advice(self):
        c = """services:
  db:
    image: postgres
    ports:
      - "5432:5432"
  cache:
    image: redis:latest
  api:
    image: ghcr.io/me/api:sha-1
    ports:
      - "127.0.0.1:${API_HOST_PORT:-18000}:8000"
    depends_on:
      - db
"""
        r = post(self.d / "compose.yaml", c)
        ctx = context(r)
        self.assertFalse(blocked(r))
        self.assertIn("R-COMPOSE-PINNED", ctx)
        self.assertIn("postgres", ctx)
        self.assertIn("redis:latest", ctx)
        self.assertNotIn("ghcr.io/me/api", ctx)
        self.assertIn("): 5432:5432.", ctx)      # only the unbound port is listed
        self.assertIn("R-COMPOSE-HEALTH", ctx)

    def test_good_compose_silent(self):
        c = """services:
  db:
    image: postgres:17-alpine
    healthcheck: { test: ["CMD", "pg_isready"] }
  api:
    image: ${API_IMAGE:-ghcr.io/me/api:dev}
    depends_on:
      db: { condition: service_healthy }
"""
        self.assertEqual(post(self.d / "compose.yaml", c), {})

    def test_dockerfile(self):
        c = "FROM python:latest AS build\nRUN true\nFROM gcr.io/distroless/python3\nENV API_TOKEN=abc\nCMD python app.py\n"
        ctx = context(post(self.d / "Dockerfile", c))
        for rule in ["R-COMPOSE-PINNED", "R-COMPOSE-NONROOT", "exec form", "R-SECRET-NOT-IN-ARTIFACTS"]:
            self.assertIn(rule, ctx)

    def test_good_dockerfile_silent(self):
        c = ("FROM python:3.12-slim AS build\nRUN true\nFROM gcr.io/distroless/python3-debian12:nonroot\n"
             "COPY --from=build /app /app\nUSER 65532\nCMD [\"/app/run\"]\n")
        self.assertEqual(post(self.d / "Dockerfile", c), {})


if __name__ == "__main__":
    unittest.main()
