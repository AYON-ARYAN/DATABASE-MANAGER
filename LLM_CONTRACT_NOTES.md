# `llm_contract.yaml` — deviations from the real provider spec

Meridian Data calls **Groq**, which exposes an **OpenAI-compatible** Chat Completions API
(`POST /openai/v1/chat/completions`). `llm_contract.yaml` is a **deliberately reduced** local
version of that API, written so Specmatic can *stub* the provider in tests (service
virtualization) — deterministic, offline, zero-token.

Reference spec: OpenAI OpenAPI — https://raw.githubusercontent.com/openai/openai-openapi/refs/heads/master/openapi.yaml

The guiding rule: **the contract should describe exactly what Meridian actually sends and
reads — no more.** A stub only needs to be faithful on the surface the consumer touches.
Every reduction below is driven by `core/llm.py::_call_groq`, which sends
`{model, messages:[{role, content}], temperature}` and reads
`choices[0].message.content` plus `usage` and `model`.

## Deviations and why

| # | Real OpenAI/Groq spec | This contract | Why |
|---|---|---|---|
| 1 | Dozens of endpoints (models, embeddings, files, …) | Only `POST /openai/v1/chat/completions` | It's the **only** endpoint Meridian calls. |
| 2 | Request supports many optional fields: `top_p`, `n`, `stream`, `stop`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `logit_bias`, `seed`, `tools`, `tool_choice`, `response_format`, `user`, … | Request = `{ model, messages, temperature }` only | Meridian sends exactly these three (`_call_groq`). Extra optional fields are irrelevant to the stub. |
| 3 | `message.content` may be a string **or** an array of content parts; messages may carry `name`, `tool_calls`, etc. | `message = { role: string, content: string }` | Meridian builds plain `{role, content}` string messages and never uses parts/tool-calls. |
| 4 | `choices[].logprobs`, and `finish_reason` enum incl. `tool_calls`, `content_filter`, … | `choices[] = { index, message, finish_reason }`; `finish_reason` left as a free string | The app reads only `choices[0].message.content`; `logprobs` is unused. |
| 5 | `usage` includes `prompt_tokens_details`, `completion_tokens_details`, … | `usage = { prompt_tokens, completion_tokens, total_tokens }` | Those three are all Meridian logs (`core/metrics.log_call`). |
| 6 | Many response fields optional | `required: [id, object, model, choices, usage]` (and `message.content` required) | The stub **guarantees** the fields the app depends on, so a contract-valid stub can never produce a response the app can't parse. |
| 7 | `servers: api.openai.com / api.groq.com` | `servers: http://localhost:9090` | It's a **local stub**; the app is pointed here in tests via `GROQ_API_URL`. |
| 8 | (n/a) | Added inline request/response **examples** (`nlToSql`) | Not part of the upstream spec — added so the stub returns a realistic, deterministic `SELECT …` for a matching request (per earlier review feedback on examples). |
| 9 | `Authorization: Bearer <key>` | `securitySchemes.bearerAuth` (http bearer) | Faithful to the real API: Meridian sends a Bearer token, and the stub accepts it. |

## Net effect
The stub is faithful on **every field Meridian actually exchanges** with the provider, and
omits only fields the app never sends or reads. If Meridian later starts using more of the
API (e.g. streaming or tool-calls), the contract should be extended to match before relying
on the stub for those paths.
