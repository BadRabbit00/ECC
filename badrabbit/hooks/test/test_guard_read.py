import unittest

from helpers import call, denied


def read(path, tool="Read"):
    key = "path" if tool == "Grep" else "file_path"
    return call("guard_read", tool, {key: path, "pattern": "x"})


class TestRead(unittest.TestCase):
    def test_denied(self):
        for p in [".env", "/repo/api/.env.local", ".env.production", "certs/tls.key", "ca.pem",
                  "/home/a/.ssh/id_ed25519", "/home/a/.config/sops/age/keys.txt", "client.p12"]:
            with self.subTest(p=p):
                self.assertTrue(denied(read(p)), p)
        self.assertTrue(denied(read(".env", tool="Grep")))

    def test_allowed(self):
        for p in [".env.example", ".env.sample", "/home/a/.ssh/id_ed25519.pub", "public.pem", "jwt-public.pem",
                  "src/keys.py", "src/app/config.py", ".envrc", "docs/keys.md"]:
            with self.subTest(p=p):
                self.assertFalse(denied(read(p)), p)


if __name__ == "__main__":
    unittest.main()
