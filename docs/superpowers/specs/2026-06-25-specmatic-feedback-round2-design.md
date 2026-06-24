# Specmatic Feedback Round 2 — Design Spec

Date: 2026-06-25 · Branch: `react_build` · Repo: AYON-ARYAN/DATABASE-MANAGER

## Context
Saachi Kaup (Specmatic) reviewed the challenge submission and replied with 4 concrete
suggestions. This spec implements all four, captures the new findings, updates the blog,
and prepares a reply.

## Saachi's suggestions → work items

### 1. Inline + external examples
- Add inline `examples:` to key operations in `api_contract.yaml` (`/api/command`,
  `/api/auth/login`) — drives richer contract tests and lifelike stubs.
- Add a Specmatic external-examples directory (JSON example files) per the
  `features/external_examples` convention.
- Refs: docs.specmatic.io inline-examples + external_examples.

### 2. Schema-resiliency tests
- Run Specmatic resiliency / generative testing against the live API to mutate requests
  (missing required, null, wrong-type, extra keys) and surface edge cases.
- Ref: github.com/specmatic/labs/tree/main/schema-resiliency-testing.
- Capture the issues found → blog findings.

### 3. Mock the LLM provider with Specmatic (showcase)
- Meridian calls Groq via the OpenAI-compatible `/openai/v1/chat/completions` (core/llm.py).
- New `llm_contract.yaml` (OpenAI chat-completions shape) with an inline example returning
  a realistic SQL completion. Ref: OpenAI openapi.yaml.
- Make the Groq base URL env-overridable: `core/llm.py` + `core/llm_manager.py` read
  `GROQ_API_URL` from env (default = real Groq URL). No behaviour change in prod.
- `specmatic stub llm_contract.yaml` → point app at it in tests → NL-to-SQL runs
  deterministically, offline, zero tokens. Specmatic virtualizes the AI dependency.

### 4. Contract + resiliency tests in CI
- Extend `.github/workflows/contract.yml`: keep contract test, add the resiliency run,
  add the LLM-stub-backed app test (boots stub, runs `/api/command` with no real tokens).

## Components / boundaries
- `api_contract.yaml` — gains inline examples (no shape changes to the API itself).
- `examples/` — external example JSON files (presentation/data only).
- `llm_contract.yaml` — NEW, describes the upstream LLM provider Meridian consumes.
- `core/llm.py`, `core/llm_manager.py` — one-line env-override for the Groq URL; default
  preserves production behaviour.
- `.github/workflows/contract.yml` — adds 2 steps (resiliency, llm-stub test).
- Scripts under `specmatic_challenge/` or repo root for the local runs (reproducible).

## Blog + reply
- Blog: add sections on resiliency findings + the "mock the LLM with Specmatic" pattern.
- Reply to Saachi (SMTP) once everything is verified green: what each suggestion surfaced,
  repo/branch links, updated blog attached.

## Verification (evidence before reply)
1. Contract test GREEN (with examples).
2. Resiliency run completes; findings captured to a file.
3. LLM-stub test: app returns SQL via the Specmatic stub with NO external call / 0 tokens.
4. Push → GitHub Actions CI GREEN.
Only then draft + send the reply.

## Out of scope
- No API behaviour changes. No new heavyweight deps. Secret-scan before any push.
- Production still calls the real Groq/Ollama (env override only affects tests).
