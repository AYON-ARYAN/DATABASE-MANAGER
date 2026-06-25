# Specmatic Feedback Round 3 — Design Spec

Date: 2026-06-25 · Repo: AYON-ARYAN/DATABASE-MANAGER · Deadline: reply by 3 PM

## Saachi's round-3 asks → work items

### 1. Raise contract-test coverage (was 50%)
- Root cause: `contract_public.yaml` documents `200` + `400`; the plain test covers only
  `200` (the `400` is an input-validation error, reachable only via negative tests) → 50%.
- Fix: CI's Specmatic step runs with `SPECMATIC_GENERATIVE_TESTS=true` so it covers both
  `200` (examples) and `400` (generative) → **100%**. Collapse the old separate
  non-generative + resiliency steps into one "Contract + resiliency" step that reports 100%.

### 2. README on main + merge branches to main
- Make `main` mirror `react_build` (complete, current version) — cleanest canonical branch.
- Write `README.md` documenting the THREE contracts and why each exists:
  - `api_contract.yaml` — full API source-of-truth + stub for the frontend
  - `contract_public.yaml` — the unauthenticated public surface exercised in CI
  - `llm_contract.yaml` — virtualizes the upstream LLM provider Meridian consumes
- Include a "How the LLM mock is used" section.

### 3. LLM mock fidelity + usage clarity
- `LLM_CONTRACT_NOTES.md`: table of every deviation of `llm_contract.yaml` from the real
  OpenAI/Groq `chat/completions` spec, and why each was necessary.
- README + blog: clarify exactly how the mock is wired (CI starts `specmatic stub`, app
  pointed at it via `GROQ_API_URL`, NL-to-SQL served offline; runs as its own step because
  it virtualizes a *dependency*, not the app's own API).

## Verification
- Local: contract+resiliency 100% coverage green; LLM-stub test passes.
- Push react_build → CI green. Mirror to main → CI green on main.
- Then send reply to Saachi (by 3 PM) addressing each point with the new run + coverage.

## Out of scope
- No API behaviour changes beyond what's already in. Secret-scan before push.
