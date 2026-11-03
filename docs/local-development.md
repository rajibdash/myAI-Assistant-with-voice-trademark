# First runnable increment: reviewed sources to PowerPoint

## Implemented behavior

This increment provides a FastAPI API, immutable plain-text sources with explicit
rights references and approval/withdrawal, citation-linked evidence slides,
hash-bound deck approval, SQLite persistence, idempotency, redacted audit events,
and an actual Node.js/TypeScript PptxGenJS renderer. No paid service is necessary
for the default path. `/health` is liveness, not proof of provider readiness.

Drafting is deliberately **extractive**, not autonomous factual authorship.
Each slide contains one exact source excerpt, a source-derived title, source ID,
full source hash, and zero-based, end-exclusive character offsets. The source is
trimmed at ingestion before hashing. Speaker notes retain the exact excerpt;
the visible slide collapses whitespace for layout. A stable deck hash binds all
titles, citations and slide order. PowerPoint bytes have a separate SHA256.

Checking that text occurs in a source does **not** establish truth, completeness,
context, currency, rights, or contradiction-free evidence. The owner must review
sources and every selected excerpt. All sources pinned to a presentation must
remain approved, even those not selected by the generator. Withdrawal blocks
approval and subsequent export; it cannot retract already downloaded files.

The optional OpenAI adapter only selects exact excerpts. It cannot provide
paraphrased facts, change the voice, execute code, or call tools. Off-source output
is rejected, not silently corrected or substituted with the default generator.
Free-form authored slides and model-written narration will need the fuller claim
ledger and evaluation gates before introduction.

## Setup

Prerequisites: Python 3.12, Node.js 22+, and npm. Run from the repository root.
The checked-in Python lock captures the development/test environment; the npm
lock captures renderer dependencies.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
npm --prefix workers/render ci --ignore-scripts --no-audit --no-fund
npm --prefix workers/render run build
export PRESENTATION_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
presentation-api
```

The server binds to `127.0.0.1:8000`, uses **one process**, and stores private local
state in `.local-data/assistant.sqlite3`. Override its path with
`PRESENTATION_DATABASE`. Keep the token secret; never commit it. The API refuses
missing/weak tokens. Protected endpoints require `Authorization: Bearer <token>`;
OpenAPI/Swagger documentation and liveness are public locally and contain no
stored content. No CORS origins are enabled.

In another activated terminal with the **same** `PRESENTATION_API_TOKEN`:

```bash
python examples/demo.py
```

Review the synthetic source, type `approve-source`, review the draft, and type
`approve-deck`. The client checks the returned artifact hash and writes
`.local-data/demo.pptx` without overwriting existing files. A cancelled review
leaves the source/draft unapproved. Use `--output .local-data/another-demo.pptx`
for a later run. The synthetic demo does not call OpenAI.

Interactive routes are documented at `http://127.0.0.1:8000/docs`. Use its
**Authorize** control to supply the bearer token. Source creation and presentation
generation require an `Idempotency-Key` of 8-128 visible ASCII characters. Reusing
a key with an identical payload returns the current resource; changing the payload
returns 409. Approval and withdrawal are themselves idempotent.

## Available API

| Route | Behavior |
|---|---|
| `POST /v1/sources` | Create pending text source; bounded title, content and rights reference |
| `GET /v1/sources/{id}` | Inspect exact normalized source and hash |
| `POST /v1/sources/{id}/approve` | Supply `expected_hash` and `reviewed: true` after human review |
| `POST /v1/sources/{id}/withdraw` | Irreversibly withdraw that source ID; submit a new source for corrections |
| `POST /v1/presentations` | Synchronously create a draft from approved `source_ids`; returns current presentation |
| `GET /v1/presentations/{id}` | Inspect state, requested generator/version, deck, hash, and failure code |
| `POST /v1/presentations/{id}/approve` | Supply exact `deck_hash` as `expected_hash` and `reviewed: true` |
| `GET /v1/presentations/{id}/pptx` | Require current approval/evidence, render, recheck, and download editable PPTX |
| `GET /v1/audit` | Local-owner audit metadata, no raw source text |

Example presentation body:

```json
{
  "title": "Quarterly evidence review",
  "source_ids": ["0123456789abcdef0123456789abcdef"],
  "slide_count": 5,
  "generator": "extractive"
}
```

IDs in this example are illustrative; use those returned by the API. Input allows
1-10 unique sources, at most 50,000 combined source characters, and 1-12 slides.
`slide_count` is an upper bound: shorter sources may produce fewer unique slides.
The extractive selector walks bounded excerpts in source order using round-robin
source coverage; it is not a relevance search or a summarization model.
Selections must preserve whole whitespace-delimited tokens, including punctuation,
so a substring cannot turn `42.5` into `4`. A token longer than the 280-character
excerpt limit produces an explicit error rather than being cut in half.

Errors contain stable `code`, safe `message`, `request_id`, and `retryable`.
Missing auth returns 401; missing records 404; hash/state/idempotency conflicts
409; invalid contracts/evidence 422; unavailable configured components 503; and
provider/renderer failures 502 or 504. Validation responses never echo raw input.

Generation is synchronous in this increment. Reservations are persisted before
provider work, so concurrent repeated keys cannot spend twice. Replaying a failed
request returns its failed resource and does not retry the provider. A fresh key
is an explicit new attempt and may incur a second charge. Startup marks interrupted
`generating` records failed; reconcile any uncertain vendor completion/billing
before intentionally resubmitting. Do not start multiple API workers against this
local database. Rendering is synchronous with a 30-second timeout and no retry.

## Optional OpenAI evidence selection

Set `OPENAI_API_KEY` **only on the server**, restart it, and deliberately set the
presentation's `generator` to `openai`. Select a supported model with
`PRESENTATION_OPENAI_MODEL` (default recommendation: `gpt-5.4`). Confirm account
access, pricing, regional/data terms, and Structured Outputs compatibility first.
The API will send approved source content to OpenAI only for that explicit path.
`store: false` is requested; that does not override the provider's contractual
logging/retention policies.

The adapter calls the Responses endpoint with a strict JSON Schema, no tools,
at most 4,000 output tokens, and a 60-second HTTP timeout. It rejects refusal,
incomplete/malformed output, unsupported quotes, and excessive slide count. There
is **no automatic paid retry** or model fallback. Input/output bounds limit request
size, but do not constitute a monetary budget manager. Keep paid use supervised
until cost reservation/reconciliation is implemented.

Unit tests use HTTP fixtures, **not** the paid API. The configured/requested model
ID and prompt version are recorded, not independently verified resolved model
identity. Live model qualification and exact resolved-version provenance remain
required before production. Missing credentials return an explicit configuration
error when `openai` is requested; they never enable fake provider success.

## Validation

After building the renderer:

```bash
ruff check app tests examples
ruff format --check app tests examples
mypy app
pytest
```

The tests cover contract bounds/control characters, exact citations and hashes,
source and deck approval, idempotency/concurrent reservations, withdrawal during
generation/render, persistence/restart recovery, auth and redacted errors,
OpenAI request/response contracts and failures, renderer failures, and actual PPTX
ZIP/XML content, notes, provenance and integrity.

`presentation-schema` regenerates `contracts/deck.schema.json` from Pydantic.
`npm --prefix workers/render run build` regenerates the TypeScript declarations
and compiles the worker. CI checks for generated-contract drift before running
the same lint/type/test commands, with no paid-provider credentials.

These are foundation tests, not the 200-case full-product corpus or evidence that
the full quality/SLO gates are met. PowerPoint desktop/web visual rendering,
reading order, font availability, multilingual/RTL layout and user acceptance
still need actual-player checks. The current bounded 16:9 evidence template is
an English-first development baseline, not a certified accessible layout engine.
There is no signed artifact manifest yet; response hashes establish integrity,
not trusted issuer provenance.

## Delivery status and open decisions

The full design remains the roadmap. This increment is **parts of M1 and M2**,
not completion of those milestones or the entire product.

| Stage | Implemented now | Still required |
|---|---|---|
| M0: decisions/rights | Required source rights reference and explicit local review | Owner/provider verification, deployment/language/cost/SLO sign-off |
| M1: grounded content | Immutable text, exact evidence, approvals, tests | Sandboxed file ingestion, collection publishing, Postgres/pgvector retrieval, claim-level factual evaluation and text Q&A |
| M2: slides | Typed deck/schema, PPTX renderer, source footers/notes | React owner/audience UI, richer templates/charts, correction workflow, actual-player/accessibility qualification |
| M3: voice | Not implemented | Owner verification, consent lifecycle, private TTS integration, pronunciation, audio checks, revocation and stop |
| M4: automated media | Not implemented | Temporal workers, timeline/captions, Remotion/FFmpeg, budgets, immutable bundles and managed manifest signing |
| M5: live audience | Not implemented | STT, authenticated sessions, grounded Q&A, interruption/resume and moderator control |
| M6: production | Local CI only | OIDC/MFA/RBAC, tenant isolation, quotas, encryption, hardened storage/egress, migrations, monitoring, restore/deletion, canary and operational acceptance |

The target remains Python/TypeScript, PostgreSQL, Temporal and private object
storage. **SQLite and synchronous local calls are deliberate development-only
stepping stones**, not a replacement production architecture. No audience-facing
service, voice enrollment, webcam/avatar, or media generation is represented as
implemented.

The missing delivery information must be confirmed at the relevant stage:

| Decision/access needed | Blocks |
|---|---|
| Deployment host/cloud, data region, domain and identity provider | Production infrastructure/authentication and data-processing review |
| Intended owner, verified voice-provider account, permitted uses, consent expiry/revocation and enrollment completion | Any owner-voice synthesis; never collect recordings in Git |
| Launch language(s), voice pronunciations, brand template, slide/video formats and duration | Real media UX, layout/voice acceptance datasets and player support |
| Approved source collection, reviewers, freshness rules and high-impact topics | Retrieval/factual evaluation, any automatic publication |
| Per-job/monthly budget, approved provider plans/models and credentials provisioned privately | Live paid integration, spending gates and qualification |
| Audience/session concurrency, latency target, release approver and moderator | Live-system capacity and final acceptance |
| Retention/deletion, backup objectives, abuse contact and operational/support owners | Production/privacy and incident readiness |
| Optional avatar requirement and verified likeness rights | Avatar provider selection and its separate consent/performance qualification |

**Do not expose this increment publicly.** Its single bearer token is a local-owner
development credential, not tenant isolation, MFA or a complete abuse defense.
Local database/source content is not encrypted by the application; keep it on a
private protected development volume and use synthetic/non-sensitive data.
There are no production quotas, durable provider reconciliation, upload sandbox,
revocation epochs, retention enforcement or external security certification.
