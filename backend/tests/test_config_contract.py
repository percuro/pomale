"""The settings are part of the 1.x promise: every variable pomale reads is documented in
docs/configuration.md, and everything documented there is read somewhere."""

import re
import unittest
from pathlib import Path

from app.config import REMOVED_SETTINGS

ROOT = Path(__file__).resolve().parents[2]
READS = re.compile(r'(?:getenv|env_bool|env_positive_int|environ\.get)\(\s*"([A-Z][A-Z0-9_]*)"')
# Read outside the Python code: by uvicorn, in the image's start command
READ_BY_THE_IMAGE = {"FORWARDED_ALLOW_IPS"}


def documented() -> set[str]:
    names: set[str] = set()
    for line in (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            first_cell = line.split("|")[1]
            names |= set(re.findall(r"`([A-Z][A-Z0-9_]*)`", first_cell))
    return names


def read_by_the_code() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        names |= set(READS.findall(path.read_text(encoding="utf-8")))
    return names - set(REMOVED_SETTINGS)


class ConfigContractTest(unittest.TestCase):
    def test_every_setting_is_documented(self):
        self.assertEqual(read_by_the_code() - documented(), set())

    def test_every_documented_setting_is_read(self):
        self.assertEqual(documented() - read_by_the_code() - READ_BY_THE_IMAGE, set())

    def test_the_image_passes_its_settings_on(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        for name in READ_BY_THE_IMAGE:
            self.assertIn(f"${{{name}", dockerfile)

    def test_removed_settings_are_not_documented_as_working(self):
        self.assertEqual(documented() & set(REMOVED_SETTINGS), set())


if __name__ == "__main__":
    unittest.main()
