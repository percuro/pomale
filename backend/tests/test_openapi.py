"""The API description: only openapi.json, switchable with API_DOCS, with API keys marked."""

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app
from app.services.token_service import TOKEN_ROUTES


class OpenApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_schema_is_served_and_docs_pages_are_not(self):
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.get("/redoc").status_code, 404)
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["servers"], [{"url": "/api"}])
        self.assertEqual(set(schema["components"]["securitySchemes"]), {"session", "apiKey"})
        self.assertNotIn("/openapi.json", schema["paths"])

    def test_operations_reachable_with_a_key_are_marked(self):
        schema = self.client.get("/openapi.json").json()
        for (method, path), scope in TOKEN_ROUTES.items():
            if path not in schema["paths"]:
                continue  # export.json follows with the JSON export
            operation = schema["paths"][path][method.lower()]
            self.assertIn({"apiKey": [scope]}, operation["security"], path)
            self.assertIn(f"API key: scope `{scope}`.", operation["description"], path)
        self.assertNotIn("security", schema["paths"]["/v1/account"]["patch"])

    def test_api_docs_false_hides_the_schema(self):
        with mock.patch.dict(os.environ, {"API_DOCS": "false"}):
            response = self.client.get("/openapi.json")
        self.assertEqual((response.status_code, response.json()["code"]), (404, "http.404"))


if __name__ == "__main__":
    unittest.main()
