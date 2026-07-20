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
        lines.append("              type: object")
    lines.append("      responses:")
    lines.append('        "200":')
    lines.append("          description: Success (shape varies by endpoint — see the hand-authored endpoints above for precise contracts)")
    lines.append("          content:")
    lines.append("            application/json:")
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

            ok_path = os.path.join(EXAMPLES_DIR, f"{slug}_200.json")
            if not os.path.exists(ok_path):
                ok = {"http-request": request, "http-response": {"status": 200}}
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
