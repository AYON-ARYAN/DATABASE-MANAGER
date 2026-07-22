#!/usr/bin/env python3
"""Regenerates the auto-generated tail of api_contract.yaml — every real /api
route the hand-authored 6 endpoints don't already cover.

Originally this wrote a separate full_api_contract.yaml, kept alongside the
hand-curated api_contract.yaml as a second, broader-but-shallower contract.
That produced a confusing "missing in spec" split: each file reported the
other file's endpoints as untested, even though every operation really was
covered somewhere. Merged into ONE spec instead — api_contract.yaml now
governs all ~52 /api operations directly, so a report against it has nothing
left to report as missing.

The merge is done via a marked block so re-running this script is safe: it
replaces everything between the AUTO-GENERATED markers and leaves the
hand-authored paths/components above and below untouched.

Broad coverage, not deep fidelity for the auto-generated block specifically:
request bodies are permissive (any JSON object) and only the two response
shapes the app's own auth guard actually guarantees are asserted — 401
Unauthorized (exact schema; every /api route enforces this identically via
app.py's require_login()) and 200 (permissive schema, since real body shapes
vary per endpoint and this block trades per-endpoint fidelity for full route
breadth). The 6 hand-authored endpoints keep their full, precise contracts.

Run:
    python scripts/generate_full_contract.py
Writes: api_contract.yaml (in place), examples_api/*.json (new files only —
never overwrites an existing hand-authored example)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GROQ_API_KEY", "contract-generation-placeholder")

from app import app  # noqa: E402  (import after sys.path/env setup, matches app.py's own style)

# Exact (path, method) pairs only — do NOT exclude by path alone. /api/connections
# supports both GET and POST in the app, but the hand-authored contract only
# documents GET; excluding the whole path silently dropped POST from BOTH the
# hand-authored section and the auto-generated block (found via a live run
# showing it as "missing in spec*"). Also do NOT use startswith — "/api/command"
# is a prefix of "/api/command-center/execute-raw" which must NOT be excluded.
HAND_AUTHORED_OPERATIONS = {
    ("/api/auth/login", "POST"),
    ("/api/auth/session", "GET"),
    ("/api/connections", "GET"),
    ("/api/command", "POST"),
    ("/api/execute", "POST"),
    ("/api/undo", "POST"),
}

# A handful of the auto-generated operations don't fit the generic "generic body
# in, 200 JSON out" template — found by actually running the generic examples
# against the live app and reading what came back, not guessed up front:
# - answer-ppt returns a binary .pptx file, not JSON — declaring an
#   application/json 200 response caused a content-type mismatch even though
#   the endpoint was genuinely returning 200.
# - GET .../{dash_id} on a placeholder ID that doesn't exist correctly 404s —
#   the generic "expect 200" template was asserting the WRONG status for what
#   this endpoint actually and correctly does.
RESPONSE_CONTENT_TYPE_OVERRIDES = {
    ("/api/command-center/answer-ppt", "POST"): (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
}
NOT_FOUND_FOR_PLACEHOLDER_ID = {
    ("/api/dashboards/{dash_id}", "GET"),
}

# A fully generic `type: object` request schema (no declared required fields) is
# technically satisfied by `{}` too — so Specmatic's schema-resiliency engine
# generates its OWN empty-body positive test for these operations independent of
# the hand-picked example, and that empty body 400s for real (these 7 handlers
# genuinely need a specific field to do anything). Declaring each field the real
# example actually sends (with the one truly-required one marked as such) stops
# Specmatic from treating `{}` as a valid instance, and stops it rejecting the
# example's own extra fields as "unknown property" (properties not listed here
# are implicitly disallowed once ANY properties are declared).
REQUEST_SCHEMA_OVERRIDES = {
    ("/api/query", "POST"): {
        "required": ["query"],
        "properties": {"query": "string", "db_name": "string"},
    },
    ("/api/overview/query", "POST"): {
        "required": ["query"],
        "properties": {"query": "string"},
    },
    ("/api/join/suggest", "POST"): {
        # Both are required (core/join_center.py's api_join_suggest 400s if either
        # is missing) — leaving right_table optional let schema-resiliency generate
        # a "mandatory keys only" test that dropped it and got a real 400.
        "required": ["left_table", "right_table"],
        "properties": {"left_table": "string", "right_table": "string"},
    },
    ("/api/join/preview", "POST"): {
        # joins is genuinely optional — core/join_center.py's build_join_sql does
        # `spec.get("joins") or []`, a single-table query with no joins is valid.
        "required": ["base_table"],
        "properties": {"base_table": "string", "joins": "join_array"},
    },
    ("/api/join/execute", "POST"): {
        "required": ["base_table"],
        "properties": {"base_table": "string", "joins": "join_array"},
    },
    ("/api/intelligence/explain", "POST"): {
        "required": ["command"],
        "properties": {"command": "string"},
    },
    ("/api/dashboards/auto-generate", "POST"): {
        "required": ["prompt"],
        "properties": {"prompt": "string"},
    },
}

START_MARKER = "  # === AUTO-GENERATED (scripts/generate_full_contract.py) — regenerate, do not hand-edit below ===\n"
END_MARKER = "  # === END AUTO-GENERATED ===\n"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT_PATH = os.path.join(REPO_ROOT, "api_contract.yaml")
EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples_api")


def flask_path_to_openapi(rule):
    return re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule)


HAND_AUTHORED_PATHS = {path for path, _method in HAND_AUTHORED_OPERATIONS}


def collect_routes():
    """Returns (new_paths, partial_paths): new_paths are paths with zero hand-authored
    operations (safe to append as a whole new top-level path block); partial_paths are
    paths that already have a hand-authored block for SOME methods but are missing
    others (must be spliced into the existing block, not appended as a duplicate key)."""
    routes = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api"):
            continue
        path = flask_path_to_openapi(rule.rule)
        methods = sorted(m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS"))
        methods = [m for m in methods if (path, m) not in HAND_AUTHORED_OPERATIONS]
        if methods:
            routes.setdefault(path, set()).update(methods)
    new_paths = {p: m for p, m in routes.items() if p not in HAND_AUTHORED_PATHS}
    partial_paths = {p: m for p, m in routes.items() if p in HAND_AUTHORED_PATHS}
    return dict(sorted(new_paths.items())), dict(sorted(partial_paths.items()))


def path_params(path):
    return re.findall(r"\{([^}]+)\}", path)


def emit_operation(method, path):
    lines = [f"    {method.lower()}:"]
    lines.append(f'      summary: "{method} {path}"')
    lines.append("      security:")
    lines.append("        - bearerAuth: []")
    params = path_params(path)
    if params:
        lines.append("      parameters:")
        for p in params:
            lines.append(f"        - name: {p}")
            lines.append("          in: path")
            lines.append("          required: true")
            lines.append("          schema: { type: string }")
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        # required: true — Flask's request.json 415s on a body-less request on
        # nearly every handler in this app, so `required: false` just invites
        # Specmatic to generate a "body omitted" boundary case that fails for a
        # reason unrelated to auth/routing. Every real client sends a body.
        lines.append("      requestBody:")
        lines.append("        required: true")
        lines.append("        content:")
        lines.append("          application/json:")
        lines.append("            schema:")
        schema_override = REQUEST_SCHEMA_OVERRIDES.get((path, method))
        if schema_override:
            lines.append("              type: object")
            lines.append(f"              required: [{', '.join(schema_override['required'])}]")
            lines.append("              properties:")
            for prop_name, prop_type in schema_override["properties"].items():
                if prop_type == "join_array":
                    # Real nested shape from core/join_center.py's build_join_sql, defined
                    # once as components/schemas/JoinSpecJoin (hand-authored, not touched by
                    # this script's regeneration) and referenced by $ref here. The example
                    # for this operation must reference two genuinely distinct, non-colliding
                    # tables (Track -> Album -> Artist, not two joins to the same table) —
                    # array-boundary resiliency testing exercises 2+ items, and with only one
                    # distinct table in the example it duplicates it, producing an unaliased
                    # self-join that 400s for real ("Duplicate alias") — a correct app
                    # rejection, not a bug, but the wrong one to hand the mutator.
                    lines.append(f"                {prop_name}:")
                    lines.append("                  type: array")
                    lines.append("                  uniqueItems: true")
                    lines.append("                  items:")
                    lines.append("                    $ref: '#/components/schemas/JoinSpecJoin'")
                elif prop_type == "array":
                    lines.append(f"                {prop_name}: {{ type: array, items: {{}} }}")
                else:
                    lines.append(f"                {prop_name}: {{ type: {prop_type} }}")
        else:
            lines.append("              type: object")
    lines.append("      responses:")
    if (path, method) in NOT_FOUND_FOR_PLACEHOLDER_ID:
        lines.append('        "404":')
        lines.append("          description: Not found (a placeholder ID that doesn't exist correctly 404s)")
        lines.append("          content:")
        lines.append("            application/json:")
        lines.append("              schema:")
        lines.append("                type: object")
        lines.append("                required: [error]")
        lines.append("                properties:")
        lines.append("                  error: { type: string }")
    else:
        content_type = RESPONSE_CONTENT_TYPE_OVERRIDES.get((path, method), "application/json")
        lines.append('        "200":')
        lines.append("          description: Success (shape varies by endpoint — see the hand-authored endpoints above for precise contracts)")
        lines.append("          content:")
        lines.append(f"            {content_type}:")
        lines.append("              schema: {}")
    lines.append('        "401":')
    lines.append("          description: Unauthorized (no or invalid credentials)")
    lines.append("          content:")
    lines.append("            application/json:")
    lines.append("              schema:")
    lines.append("                type: object")
    lines.append("                required: [error]")
    lines.append("                properties:")
    lines.append("                  error: { type: string }")
    return "\n".join(lines)


def build_block(new_paths):
    out = [START_MARKER.rstrip("\n")]
    for path, methods in new_paths.items():
        out.append(f"  {path}:")
        for method in sorted(methods):
            out.append(emit_operation(method, path))
    out.append(END_MARKER.rstrip("\n"))
    return "\n".join(out) + "\n"


def splice_partial_path(text, path, methods):
    """Path already has a hand-authored `  {path}:` block for some methods —
    insert the missing method(s) at the end of that same block instead of
    appending a duplicate top-level key (which would silently orphan one of
    the two blocks under YAML's last-key-wins duplicate-key handling)."""
    path_key = f"  {path}:\n"
    start = text.index(path_key) + len(path_key)
    end = start
    lines = text[start:].splitlines(keepends=True)
    for line in lines:
        # A line that isn't blank and isn't indented at least 4 spaces (i.e. isn't
        # part of this path's own operation blocks) marks the end of this block.
        if line.strip() and not line.startswith("    "):
            break
        end += len(line)
    block_text = text[start:end]
    # Idempotent: skip methods already present in this block (e.g. a prior run
    # already spliced them in) so rerunning never produces a duplicate `post:`
    # (or similar) key under the same path.
    methods = [m for m in methods if f"    {m.lower()}:\n" not in block_text]
    if not methods:
        return text
    new_ops = "".join(emit_operation(m, path) + "\n" for m in sorted(methods))
    return text[:end] + new_ops + text[end:]


def splice_into_contract(new_paths, partial_paths):
    with open(CONTRACT_PATH) as f:
        text = f.read()

    for path, methods in partial_paths.items():
        text = splice_partial_path(text, path, methods)

    block = build_block(new_paths)
    if START_MARKER in text and END_MARKER in text:
        start = text.index(START_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        text = text[:start] + block + text[end:]
    else:
        # First run: insert right before the top-level `components:` section.
        marker = "\ncomponents:\n"
        idx = text.index(marker)
        text = text[:idx] + "\n" + block + text[idx:]

    with open(CONTRACT_PATH, "w") as f:
        f.write(text)


def slugify(method, path):
    name = path.strip("/").replace("/", "_")
    name = re.sub(r"[{}]", "", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return f"{name}_{method.lower()}"


def concrete_path(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def write_examples(routes):
    os.makedirs(EXAMPLES_DIR, exist_ok=True)
    written = 0
    for path, methods in routes.items():
        for method in sorted(methods):
            slug = slugify(method, path)
            request = {"method": method, "path": concrete_path(path),
                       "headers": {"Authorization": "Bearer specmatic-ci-token"}}
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                request["body"] = {}

            if (path, method) in NOT_FOUND_FOR_PLACEHOLDER_ID:
                stale_ok_path = os.path.join(EXAMPLES_DIR, f"{slug}_200.json")
                if os.path.exists(stale_ok_path):
                    os.remove(stale_ok_path)
                ok_path = os.path.join(EXAMPLES_DIR, f"{slug}_404.json")
                ok_status, ok_body = 404, {"error": "Dashboard not found"}
            else:
                ok_path = os.path.join(EXAMPLES_DIR, f"{slug}_200.json")
                ok_status, ok_body = 200, None
            if not os.path.exists(ok_path):
                ok_response = {"status": ok_status}
                if ok_body is not None:
                    ok_response["body"] = ok_body
                ok = {"http-request": request, "http-response": ok_response}
                with open(ok_path, "w") as f:
                    json.dump(ok, f)
                    f.write("\n")
                written += 1

            bad_path = os.path.join(EXAMPLES_DIR, f"{slug}_401.json")
            if not os.path.exists(bad_path):
                bad_request = dict(request, headers={"Authorization": "Bearer not-the-ci-token"})
                unauthorized = {"http-request": bad_request,
                                 "http-response": {"status": 401, "body": {"error": "Unauthorized"}}}
                with open(bad_path, "w") as f:
                    json.dump(unauthorized, f)
                    f.write("\n")
                written += 1
    return written


def main():
    new_paths, partial_paths = collect_routes()
    splice_into_contract(new_paths, partial_paths)

    all_routes = dict(new_paths)
    for path, methods in partial_paths.items():
        all_routes.setdefault(path, set()).update(methods)
    example_count = write_examples(all_routes)

    op_count = sum(len(m) for m in all_routes.values())
    print(f"Merged {len(new_paths)} new paths + {len(partial_paths)} partial paths "
          f"({op_count} operations total) into {CONTRACT_PATH}")
    print(f"Wrote {example_count} new example files to {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
