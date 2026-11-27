"""The 1.x promise: the stable API (app/api/contract.py) stays compatible with the 1.0 baseline.

The baseline tests/fixtures/openapi-1.0.json is written once for 1.0.0 and never rewritten in 1.x.
If this test fails, the change breaks scripts, shortcuts or home automations: make it additive
instead (a new optional field, a new operation) or keep it for 2.0.
"""

import copy
import json
import re
import unittest
from pathlib import Path

from app.api.contract import INTERNAL_NOTE, STABILITY_KEY, STABLE_ROUTES, breaking_changes, stable_schema
from app.main import app
from app.services.token_service import TOKEN_ROUTES

BASELINE = Path(__file__).parent / "fixtures" / "openapi-1.0.json"
ROOT = Path(__file__).resolve().parents[2]


def documented_error_codes() -> set[str]:
    text = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    section = text.split("\n## Errors", 1)[1].split("\n## ", 1)[0]
    codes: set[str] = set()
    for line in section.splitlines():
        if line.startswith("| ") and not line.startswith("| Status"):
            codes |= set(re.findall(r"`([a-z_]+(?:\.[a-z_]+)?)`", line.split("|")[2]))
    return codes


def current() -> dict:
    return stable_schema(app.openapi())


class ApiContractTest(unittest.TestCase):
    def test_the_stable_api_is_compatible_with_1_0(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(breaking_changes(baseline, current()), [])

    def test_every_operation_is_marked_stable_or_internal(self):
        schema = app.openapi()
        stable = set()
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                marker = operation[STABILITY_KEY]
                self.assertIn(marker, ("stable", "internal"), (method, path))
                if marker == "stable":
                    stable.add((method.upper(), path))
                else:
                    self.assertIn(INTERNAL_NOTE, operation["description"], (method, path))
        self.assertEqual(stable, set(STABLE_ROUTES))
        self.assertTrue(set(TOKEN_ROUTES) <= stable)
        self.assertIn(("GET", "/health"), stable)

    def test_the_stable_schema_has_only_stable_operations_and_their_components(self):
        schema = current()
        operations = {(method.upper(), path) for path, ops in schema["paths"].items() for method in ops}
        self.assertEqual(operations, set(STABLE_ROUTES))
        self.assertIn("TodayRead", schema["components"]["schemas"])
        self.assertNotIn("TokenRead", schema["components"]["schemas"])


class ErrorCodesTest(unittest.TestCase):
    def test_every_documented_code_is_still_raised(self):
        codes = documented_error_codes()
        self.assertGreaterEqual(len(codes), 15)
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "backend" / "app").rglob("*.py"))
        missing = {code for code in codes if f'"{code}"' not in source}
        self.assertEqual(missing, set())


class BreakingChangesTest(unittest.TestCase):
    """The checker itself: every kind of break is found, additions are not."""

    def setUp(self):
        self.base = current()

    def changed(self, mutate) -> list[str]:
        schema = copy.deepcopy(self.base)
        mutate(schema)
        return breaking_changes(self.base, schema)

    def components(self, schema: dict) -> dict:
        return schema["components"]["schemas"]

    def test_no_change_no_problem(self):
        self.assertEqual(breaking_changes(self.base, copy.deepcopy(self.base)), [])

    def test_additions_are_allowed(self):
        def add(schema):
            today = self.components(schema)["TodayRead"]
            today["properties"]["streak"] = {"type": "integer"}
            today["required"].append("streak")
            self.components(schema)["CheckinUpdate"]["properties"]["source"] = {"type": "string"}
            self.components(schema)["DayRead"]["properties"]["state"]["enum"].append("skipped")
            schema["paths"]["/v1/reports"] = {"get": {"responses": {"200": {}}}}

        self.assertEqual(self.changed(add), [])

    def test_removed_operation(self):
        problems = self.changed(lambda s: s["paths"]["/v1/today"].pop("get"))
        self.assertIn("GET /v1/today: removed", problems)

    def test_removed_or_renamed_response_field(self):
        def rename(schema):
            props = self.components(schema)["TodayRead"]["properties"]
            props["text"] = props.pop("message")

        self.assertTrue(any("message: removed" in p for p in self.changed(rename)))

    def test_nested_response_field(self):
        def remove(schema):
            self.components(schema)["DayRead"]["properties"].pop("version")

        self.assertTrue(any("days[].version: removed" in p for p in self.changed(remove)))

    def test_response_field_becomes_nullable(self):
        def nullable(schema):
            props = self.components(schema)["TodayRead"]["properties"]
            props["due"] = {"anyOf": [props["due"], {"type": "null"}]}

        self.assertTrue(any("due: can now be null" in p for p in self.changed(nullable)))

    def test_other_type(self):
        def retype(schema):
            self.components(schema)["TodayRead"]["properties"]["due"]["type"] = "string"

        self.assertTrue(any("due: type 'integer' → 'string'" in p for p in self.changed(retype)))

    def test_removed_enum_value(self):
        def shrink(schema):
            self.components(schema)["DayRead"]["properties"]["state"]["enum"].remove("partial")

        self.assertTrue(any("values removed: ['partial']" in p for p in self.changed(shrink)))

    def test_new_required_request_field(self):
        def require(schema):
            update = self.components(schema)["CheckinUpdate"]
            update["properties"]["source"] = {"type": "string"}
            update["required"] = [*update.get("required", []), "source"]

        self.assertTrue(any("source: new required field" in p for p in self.changed(require)))

    def test_stricter_request_limit(self):
        def limit(schema):
            note = self.components(schema)["NoteUpdate"]["properties"]["note"]["anyOf"][0]
            note["maxLength"] = 100

        self.assertTrue(any("maxLength 500 → 100" in p for p in self.changed(limit)))

    def test_removed_or_required_parameter(self):
        def params(schema):
            operation = schema["paths"]["/v1/days"]["get"]
            operation["parameters"] = [p for p in operation["parameters"] if p["name"] != "from"]
            operation["parameters"].append({"in": "query", "name": "habit", "required": True, "schema": {}})

        problems = self.changed(params)
        self.assertIn("GET /v1/days: parameter from (query) removed", problems)
        self.assertIn("GET /v1/days: parameter habit (query) is now required", problems)

    def test_other_key_scope(self):
        def scope(schema):
            schema["paths"]["/v1/today"]["get"]["security"] = [{"session": []}, {"apiKey": ["checkin"]}]

        self.assertTrue(any(p.startswith("GET /v1/today: security") for p in self.changed(scope)))


if __name__ == "__main__":
    unittest.main()
