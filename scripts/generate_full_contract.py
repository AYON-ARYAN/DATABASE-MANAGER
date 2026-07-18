#!/usr/bin/env python3
"""Auto-generates full_api_contract.yaml — an OpenAPI 3.0 contract covering
every real /api route in the app, not just the 6 hand-curated ones in
api_contract.yaml.

Broad coverage, not deep fidelity: request bodies are permissive (any JSON
object) and only the two response shapes the app's own auth guard actually
guarantees are asserted — 401 Unauthorized (exact schema; every /api route
enforces this identically via app.py's require_login()) and 200 (permissive
schema, since real body shapes vary per endpoint and this layer trades
per-endpoint fidelity for full route breadth). See CONTRACT_SCOPE.md for the
two-tier rationale — api_contract.yaml stays the deep, hand-curated layer for
the 6 endpoints external consumers actually depend on.

Also writes examples_full/ — one generic 200 + 401 example JSON per
operation. Specmatic will not exercise a securitySchemes-gated 200/401 pair
without at least one example to anchor the token substitution on (confirmed
empirically: a schema-only run against this contract got 0/80, every "200"
case receiving 401 and every "401" case skipped with "Examples Required").
The examples are mechanically generated (placeholder path params, empty
bodies), not hand-authored — same broad-not-deep tradeoff as the contract
itself.

Run:
    python scripts/generate_full_contract.py
Writes: full_api_contract.yaml, examples_full/*.json (repo root)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GROQ_API_KEY", "contract-generation-placeholder")

from app import app  # noqa: E402  (import after sys.path/env setup, matches app.py's own style)

# Exact paths only — do NOT use startswith, "/api/command" is a prefix of
# "/api/command-center/execute-raw" which must NOT be excluded.
GOVERNED_PATHS = {
    "/api/auth/login",
    "/api/auth/session",
    "/api/connections",
    "/api/command",
    "/api/execute",
    "/api/undo",
}


def flask_path_to_openapi(rule):
    return re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule)


def collect_routes():
    routes = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api"):
            continue
        path = flask_path_to_openapi(rule.rule)
        if path in GOVERNED_PATHS:
            continue
        methods = sorted(m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS"))
        routes.setdefault(path, set()).update(methods)
    return dict(sorted(routes.items()))


def path_params(path):
    return re.findall(r"\{([^}]+)\}", path)


def emit_operation(method, path):
    lines = [f"    {method.lower()}:"]
    lines.append(f'      summary: "{method} {path}"')
    # Per-operation security (not a document-root default) — matches api_contract.yaml's
    # proven pattern. A root-level `security:` key was tried first and Specmatic's test
    # engine did not inject the configured bearer token for the positive-auth case with it
    # (every "200" test got 401 instead) — confirmed by comparing against api_contract.yaml,
    # which declares `security: [{ bearerAuth: [] }]` on every operation individually.
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
        # required: true (not false) — Flask's request.json 415s on a body-less
        # request on nearly every handler in this app, so `required: false` just
        # invites Specmatic to generate a "body omitted" boundary case that fails
        # for a reason unrelated to auth/routing. Every real client sends a body.
        lines.append("      requestBody:")
        lines.append("        required: true")
        lines.append("        content:")
        lines.append("          application/json:")
        lines.append("            schema:")
        lines.append("              type: object")
    lines.append("      responses:")
    lines.append('        "200":')
    lines.append("          description: Success (shape varies by endpoint — see api_contract.yaml for hand-curated deep contracts)")
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


def slugify(method, path):
    name = path.strip("/").replace("/", "_")
    name = re.sub(r"[{}]", "", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return f"{name}_{method.lower()}"


def concrete_path(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def write_examples(routes, examples_dir):
    os.makedirs(examples_dir, exist_ok=True)
    count = 0
    for path, methods in routes.items():
        for method in sorted(methods):
            slug = slugify(method, path)
            request = {"method": method, "path": concrete_path(path),
                       "headers": {"Authorization": "Bearer specmatic-ci-token"}}
            if method in ("POST", "PUT", "DELETE", "PATCH"):
                request["body"] = {}

            ok = {"http-request": request, "http-response": {"status": 200}}
            with open(os.path.join(examples_dir, f"{slug}_200.json"), "w") as f:
                json.dump(ok, f)
                f.write("\n")

            bad_request = dict(request, headers={"Authorization": "Bearer not-the-ci-token"})
            unauthorized = {"http-request": bad_request,
                             "http-response": {"status": 401, "body": {"error": "Unauthorized"}}}
            with open(os.path.join(examples_dir, f"{slug}_401.json"), "w") as f:
                json.dump(unauthorized, f)
                f.write("\n")
            count += 2
    return count


def main():
    routes = collect_routes()

    out = []
    out.append("openapi: 3.0.3")
    out.append("info:")
    out.append("  title: Meridian Data — Full API Surface (auto-generated)")
    out.append('  version: "1.0.0"')
    out.append("  description: >")
    out.append("    Auto-generated from the live Flask route table (app.url_map) by")
    out.append("    scripts/generate_full_contract.py. Covers every /api route so contract")
    out.append("    testing exercises the FULL attack surface, not just the 6 hand-curated")
    out.append("    endpoints in api_contract.yaml. Broad coverage, not deep fidelity — see")
    out.append("    CONTRACT_SCOPE.md for the two-tier rationale. Regenerate after adding or")
    out.append("    removing routes: python scripts/generate_full_contract.py")
    out.append("paths:")
    for path, methods in routes.items():
        out.append(f"  {path}:")
        for method in sorted(methods):
            out.append(emit_operation(method, path))
    out.append("components:")
    out.append("  securitySchemes:")
    out.append("    bearerAuth:")
    out.append("      type: http")
    out.append("      scheme: bearer")

    text = "\n".join(out) + "\n"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo_root, "full_api_contract.yaml")
    with open(out_path, "w") as f:
        f.write(text)
    op_count = sum(len(m) for m in routes.values())

    examples_dir = os.path.join(repo_root, "examples_full")
    example_count = write_examples(routes, examples_dir)

    print(f"Wrote {out_path} — {len(routes)} paths, {op_count} operations")
    print(f"Wrote {example_count} example files to {examples_dir}")


if __name__ == "__main__":
    main()
