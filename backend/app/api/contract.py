"""The stable part of the API and the check that 1.x keeps it.

Stable (until 2.0) are the operations an API key can reach (TOKEN_ROUTES) and the health check.
Everything else under /v1 serves the web app and may change in a minor release; the OpenAPI
document marks every operation with `x-pomale-stability`.

`breaking_changes(baseline, current)` compares two stable schemas (see `stable_schema`). Additions
are fine: new operations, new optional request fields, new response fields, new enum values. It
reports what would break an existing client: a missing operation, parameter or response field, a
new required request field, another type or format, a removed enum value, a response field that
can now be null, a request limit that became stricter, or another API key scope.
"""

import copy
from typing import Any

from app.services.token_service import TOKEN_ROUTES

STABLE_ROUTES: frozenset[tuple[str, str]] = frozenset(TOKEN_ROUTES) | {("GET", "/health")}
STABILITY_KEY = "x-pomale-stability"
INTERNAL_NOTE = "Internal: used by the web app, may change in a minor release."

_METHODS = ("get", "put", "post", "patch", "delete")
_REF_PREFIX = "#/components/schemas/"


def is_stable(method: str, path: str) -> bool:
    return (method.upper(), path) in STABLE_ROUTES


def _refs(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX):
            found.add(ref.removeprefix(_REF_PREFIX))
        for value in node.values():
            found |= _refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= _refs(value)
    return found


def stable_schema(schema: dict) -> dict:
    """Only the stable operations, with the component schemas they reference (transitively)."""
    paths: dict[str, dict] = {}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method in _METHODS and is_stable(method, path):
                paths.setdefault(path, {})[method] = copy.deepcopy(operation)
    components = schema.get("components", {}).get("schemas", {})
    needed: set[str] = set()
    todo = _refs(paths)
    while todo:
        name = todo.pop()
        if name in needed or name not in components:
            continue
        needed.add(name)
        todo |= _refs(components[name]) - needed
    return {
        "openapi": schema.get("openapi"),
        "paths": dict(sorted(paths.items())),
        "components": {"schemas": {name: copy.deepcopy(components[name]) for name in sorted(needed)}},
    }


class _Checker:
    def __init__(self, baseline: dict, current: dict):
        self.base_components = baseline.get("components", {}).get("schemas", {})
        self.cur_components = current.get("components", {}).get("schemas", {})
        self.problems: list[str] = []

    def _resolve(self, schema: dict | None, components: dict, seen: frozenset = frozenset()) -> dict:
        schema = schema or {}
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX) and ref not in seen:
            target = components.get(ref.removeprefix(_REF_PREFIX), {})
            return self._resolve(target, components, seen | {ref})
        return schema

    def _split(self, schema: dict | None, components: dict) -> tuple[dict, bool]:
        """(schema without its null alternative, whether null is allowed)"""
        schema = self._resolve(schema, components)
        options = schema.get("anyOf") or schema.get("oneOf")
        if options:
            non_null = [option for option in options if option.get("type") != "null"]
            nullable = len(non_null) < len(options)
            if len(non_null) == 1:
                inner, inner_nullable = self._split(non_null[0], components)
                return inner, nullable or inner_nullable
            return {"anyOf": non_null}, nullable
        return schema, schema.get("type") == "null"

    @staticmethod
    def _enum(schema: dict) -> set | None:
        if "const" in schema:
            return {schema["const"]}
        if "enum" in schema:
            return set(schema["enum"])
        return None

    def compare(self, base: dict | None, cur: dict | None, where: str, request: bool) -> None:
        base_schema, base_null = self._split(base, self.base_components)
        cur_schema, cur_null = self._split(cur, self.cur_components)
        if request and base_null and not cur_null:
            self.problems.append(f"{where}: null is no longer accepted")
        if not request and cur_null and not base_null:
            self.problems.append(f"{where}: can now be null")
        if "anyOf" in base_schema or "anyOf" in cur_schema:
            base_plain = self._plain(base_schema, self.base_components)
            if base_plain != self._plain(cur_schema, self.cur_components):
                self.problems.append(f"{where}: the alternatives changed")
            return
        for key in ("type", "format"):
            if base_schema.get(key) != cur_schema.get(key):
                self.problems.append(f"{where}: {key} {base_schema.get(key)!r} → {cur_schema.get(key)!r}")
                return
        base_enum, cur_enum = self._enum(base_schema), self._enum(cur_schema)
        if base_enum is not None and cur_enum is not None and base_enum - cur_enum:
            self.problems.append(f"{where}: values removed: {sorted(map(str, base_enum - cur_enum))}")
        if request and base_enum is None and cur_enum is not None:
            self.problems.append(f"{where}: now limited to {sorted(map(str, cur_enum))}")
        if request:
            self._limits(base_schema, cur_schema, where)
        if base_schema.get("type") == "array":
            self.compare(base_schema.get("items"), cur_schema.get("items"), f"{where}[]", request)
        if base_schema.get("type") == "object" or "properties" in base_schema:
            self._object(base_schema, cur_schema, where, request)

    def _plain(self, schema: Any, components: dict) -> Any:
        """A schema with every reference resolved, for comparing alternatives."""
        if isinstance(schema, dict):
            resolved = self._resolve(schema, components) if "$ref" in schema else schema
            return {
                key: self._plain(value, components)
                for key, value in resolved.items()
                if key not in ("title", "description")
            }
        if isinstance(schema, list):
            return [self._plain(value, components) for value in schema]
        return schema

    def _limits(self, base: dict, cur: dict, where: str) -> None:
        for key in ("maxLength", "maxItems", "maximum"):
            if key in cur and (key not in base or cur[key] < base[key]):
                self.problems.append(f"{where}: {key} {base.get(key)} → {cur[key]}")
        for key in ("minLength", "minItems", "minimum"):
            if key in cur and (key not in base or cur[key] > base[key]):
                self.problems.append(f"{where}: {key} {base.get(key)} → {cur[key]}")

    def _object(self, base: dict, cur: dict, where: str, request: bool) -> None:
        base_props, cur_props = base.get("properties", {}), cur.get("properties", {})
        base_required, cur_required = set(base.get("required", [])), set(cur.get("required", []))
        for name, prop in base_props.items():
            if name not in cur_props:
                self.problems.append(f"{where}.{name}: removed")
                continue
            self.compare(prop, cur_props[name], f"{where}.{name}", request)
            if not request and name in base_required and name not in cur_required:
                self.problems.append(f"{where}.{name}: no longer always present")
        if request:
            for name in sorted(cur_required - base_required):
                self.problems.append(f"{where}.{name}: new required field")

    def operation(self, base: dict, cur: dict, where: str) -> None:
        if base.get("security") != cur.get("security"):
            self.problems.append(f"{where}: security {base.get('security')} → {cur.get('security')}")
        cur_params = {(p["in"], p["name"]): p for p in cur.get("parameters", [])}
        base_params = {(p["in"], p["name"]): p for p in base.get("parameters", [])}
        for key, param in base_params.items():
            if key not in cur_params:
                self.problems.append(f"{where}: parameter {key[1]} ({key[0]}) removed")
                continue
            self.compare(param.get("schema"), cur_params[key].get("schema"), f"{where} {key[1]}", request=True)
        for key, param in cur_params.items():
            if param.get("required") and not base_params.get(key, {}).get("required"):
                self.problems.append(f"{where}: parameter {key[1]} ({key[0]}) is now required")
        base_body = base.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        cur_body = cur.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if cur.get("requestBody", {}).get("required") and not base.get("requestBody", {}).get("required"):
            self.problems.append(f"{where}: a request body is now required")
        if base_body is not None:
            if cur_body is None:
                self.problems.append(f"{where}: the request body is no longer read")
            else:
                self.compare(base_body, cur_body, f"{where} body", request=True)
        for status, response in base.get("responses", {}).items():
            if not status.startswith("2"):
                continue
            if status not in cur.get("responses", {}):
                self.problems.append(f"{where}: response {status} removed")
                continue
            base_content = response.get("content", {})
            cur_content = cur["responses"][status].get("content", {})
            for media_type, body in base_content.items():
                if media_type not in cur_content:
                    self.problems.append(f"{where}: response {status} {media_type} removed")
                    continue
                self.compare(body.get("schema"), cur_content[media_type].get("schema"), f"{where} {status}", False)


def breaking_changes(baseline: dict, current: dict) -> list[str]:
    checker = _Checker(baseline, current)
    for path, operations in baseline["paths"].items():
        for method, operation in operations.items():
            where = f"{method.upper()} {path}"
            current_operation = current["paths"].get(path, {}).get(method)
            if current_operation is None:
                checker.problems.append(f"{where}: removed")
                continue
            checker.operation(operation, current_operation, where)
    return checker.problems
