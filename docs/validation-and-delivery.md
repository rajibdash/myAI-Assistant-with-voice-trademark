# Validation strategy and complete product delivery

**Status:** Full-product test and acceptance specification, not executed results
for the complete product. The repository now has a local API/PPTX increment and
automated tests; see [current validation coverage](local-development.md#validation).
Targets below remain initial full-product release criteria to ratify during M0,
not vendor performance promises or evidence those thresholds have been met.

## 1. Verify information, not just fluent output

Maintain a reviewed evaluation corpus with frozen source files/hashes, exact
supporting passages, expected facts/units/dates, allowed paraphrases, and expected
refusals. Keep evaluation authors separate from the prompt author where practical.
Use only authorized or synthetic data; never commit audience recordings or
enrollment samples.

Start with at least 200 curated cases: 80 supported factual questions, 40
unsupported/ambiguous questions, 30 numerical/table/date questions, 20 conflicting
or stale-source questions, 20 prompt-injection/abuse questions, and 10
tenant-isolation/authorization cases. Add at least 20 cases per additional supported
language and 10 representative presentation briefs. This is a starting dataset,
not proof that rare failures cannot occur.

For every fact in the shipped deck, script and generated answer:

1. Resolve the citation to an approved source hash and exact page/section/table
   cell. Verify the cited text supports the actual claim, not merely the topic.
2. Recalculate numbers and derived quantities deterministically; preserve units,
   denominator, rounding rules, timezone and as-of date.
3. Check source authority, freshness and contradictions. Store publication,
   retrieval and applicable dates separately. Re-fetch/re-review time-sensitive
   evidence according to its collection policy; never imply universal validity
   from an old citation.
4. Compare slides, spoken script, captions and charts for the same meaning and
   values. Narration must not add unsupported claims.
5. Escalate unresolved discrepancies. A second LLM's agreement is not independent
   factual verification, and a release score cannot excuse a known false claim.

Automated checks prove constrained properties; they cannot validate all possible
information or legal rights. High-impact/contested claims require qualified human
review and a documented risk policy. Re-run checks when source, prompt, model,
schema, pronunciation, renderer or policy versions change.

## 2. Layered test matrix

| Layer | Required coverage | Pass evidence |
|---|---|---|
| Static/type/schema | Python/TS typing, lint, dependency/secret scans, JSON Schema and OpenAPI compatibility | No blocking errors; generated contracts match |
| Unit | Claim references, numeric conversion, source expiry, approval hashes, budgets, state transitions, timeline math, consent/epoch checks | Boundary and negative cases pass deterministically |
| Property-based | Random slide/caption lengths, Unicode, timestamp monotonicity, malformed provider outputs, idempotency payloads | No invalid accepted state; failures are explicit |
| Provider contract | Structured-output refusal/truncation, STT errors, TTS streaming formats, quota/auth/timeouts, model/voice availability | Recorded synthetic fixtures plus opt-in live sandbox smoke tests |
| Integration | Real PostgreSQL/pgvector, object store, Temporal, migrations and worker cancellation | No cross-tenant results, duplicate publication or orphaned accessible files |
| Retrieval/factual evaluation | Frozen corpus, citations, numbers, contradictions, refusals and multilingual questions | Metrics in section 3; per-case report with traceable evidence |
| Visual/media | Slide previews, PPTX semantics, contrast/alt text, audio, caption alignment, render integrity | Automated report plus sampled human/player review |
| E2E | Brief -> evidence -> approval -> owner voice -> render -> release -> playback -> Q&A -> revoke | Playwright/browser and actual-player scenarios below |
| Load/soak | Target concurrent sessions, queued jobs, long decks, cancellation, provider limits | Agreed p95/p99 latency, cost and resource limits; no unbounded growth |
| Resilience | Worker crash, retry ambiguity, network loss, DB/storage errors, provider outage, revocation races | Correct recoverable/failed states; no unauthorized publication |
| Privacy/access control | RBAC, IDOR, socket auth, SSRF, prompt injection, deletion and retention | All critical access/authorization cases pass before launch |
| User acceptance | Owner voice, moderator workflow, audience comprehension, accessibility and disclosure | Recorded owner/moderator sign-off and known limitations |

Use mocked providers for routine PR tests. Keep live provider tests opt-in,
budget-capped, and restricted to a protected environment. A mock proves local
behavior, not provider compatibility or voice quality. Avoid exact string/pixel
assertions for stochastic model outputs; assert schemas, evidence and semantic
invariants. Deterministic template rendering may use reviewed image baselines.

## 3. Initial measurable acceptance gates

| Metric | Measurement and initial target |
|---|---|
| Artifact citation coverage | 100% of factual slide blocks and narration sentences map to verified claims; all reference IDs resolve |
| Artifact factual correctness | Zero known unsupported or materially incorrect claims in a release; any known material failure blocks publication regardless of aggregate score |
| Retrieval recall@5 | At least 95% of answerable evaluation questions retrieve at least one gold supporting passage in top five |
| Citation precision | At least 98% of evaluated factual answer claims are actually supported by their cited passages; abstentions excluded and reported separately |
| Grounded answer rate | At least 95% of answers to answerable cases have every factual claim supported; report answerable-case abstention rate separately |
| Unsupported-answer refusal recall | At least 98% of unsupported cases correctly abstain/escalate; 100% on curated critical-risk cases |
| Numerical fidelity | 100% exact agreement on tested values/units/dates after defined rounding; no invented chart values |
| Authorization/isolation | 100% denial on negative tenant, expired/revoked voice and unapproved-script cases; zero cross-tenant disclosures |
| Q&A latency | Initial p95 <= 5 s from confirmed final transcript/text to first authorized audible response, at 20 concurrent sessions; separately report STT, retrieval, generation, guarding and TTS |
| Stop/interruption | Browser playback stops within 250 ms p95 of local stop; server rejects new chunks/publication within 1 s p95 of committed revocation; test races |
| Caption alignment | At least 95% of sampled cue boundaries within 250 ms of the spoken phrase; monotonic cues, no negative durations, no cue beyond media end |
| Audio integrity | No unintended missing/duplicated narration, clipping or long silence; initial target -16 LUFS integrated, <= -1 dBTP true peak for final video, measured on representative exports |
| Owner voice quality | Owner mean >= 4/5 for identity, naturalness and pronunciation on at least 20 consented phrases per launch language; no critical name/number mispronunciation |
| Slide readability | No clipped/overlapping text in supported templates; target minimum 24 pt body and 32 pt titles at 16:9, with explicit exceptions reviewed; WCAG AA contrast in browser UI |
| Bundle integrity | All hashes verify; MP4 decodes fully; PPTX opens without repair; captions/transcript match approved script; total duration within +/-10% of agreed brief |
| Generation throughput | Initial staging target: 10-slide / 5-minute / 1080p deck completes within 15 minutes p95 on declared render hardware at declared queue load |
| Budget | 100% of jobs respect configured authorized ceiling/reservations; provider estimates and actual billing reconciled; uncertain paid retries require reconciliation |

These are product gates, not interchangeable with the README's illustrative
single `p95_latency_ms` value. Report denominators, raw counts, median/p95/p99,
test hardware/network, corpus version, model/config versions and confidence
intervals where meaningful. Small corpora cannot substantiate production-level
99.9% claims. Expand testing based on observed errors, languages and audience risk.

## 4. Concrete end-to-end acceptance scenarios

| ID | Scenario | Expected result |
|---|---|---|
| E01 | Approved brief and frozen sources, valid owner voice | Complete validated bundle, visible citations/disclosure, signed manifest; opens and plays |
| E02 | Missing source support or conflicting dates | Block affected claim/release and request source review; no invented answer |
| E03 | Wrong source ID, subtly wrong number, or narration-only added fact | Deterministic/semantic verification fails and prevents synthesis/publication |
| E04 | Expired consent before TTS, during stream, after cache creation, before publish | Deny/stop each path; cache cannot bypass current authorization |
| E05 | Repeat `POST` with same idempotency key; then change payload | Same job returned for same payload; changed payload receives conflict |
| E06 | Worker dies after vendor accepts synthesis, before result is recorded | Reconcile uncertain vendor attempt; no blind duplicate paid job |
| E07 | Provider 429, 5xx, timeout or wrong audio format | Bounded safe retries; explicit failure/status or approved text-only behavior |
| E08 | Owner changes one script sentence after approval | Approval invalidated; affected audio/captions/render rebuilt and revalidated |
| E09 | Audience interrupts while chunks are in flight | Old turn discarded; playback stops; no delayed old speech after reconnect |
| E10 | Audience Q&A then resume presentation | No overlapping speech; resume from saved slide/time bookmark |
| E11 | Malicious document says to reveal secrets or change voice | Content treated as untrusted evidence; no unauthorized tool/voice access |
| E12 | Another tenant guesses IDs or submits arbitrary provider voice ID | Access denied in API, retrieval, storage and sockets; no metadata leakage |
| E13 | Unicode/RTL, long titles, charts, missing fonts, short/long narration | Correct language rendering or explicit unsupported-language block; no silent overflow |
| E14 | Corrupt media, missing caption file or invalid artifact hash | Release blocked; partially generated objects remain inaccessible |
| E15 | Moderator stop and publish occur concurrently | State/version/epoch check prevents new publication; existing session stops |
| E16 | Retention expires or owner requests deletion | Index/cache/object/provider deletion tracked; backup policy and outstanding copies disclosed |
| E17 | Keyboard-only/screen-reader audience; mic permission denied | Accessible navigation, text Q&A, captions and clear consent state |
| E18 | Source is updated or withdrawn after an existing release | Preserve audit lineage; flag/withdraw affected release under policy; never silently rewrite its evidence |
| E19 | Spending ceiling reached during queued/retried work | Further spend blocked; actionable pause; reserved/actual cost reconciled |
| E20 | Automatic-publication policy expired or destination changed | Human approval required; no policy bypass from old configuration |

## 5. Voice, caption, slide and player validation

Use owner-approved recordings only in restricted evaluation storage. Test names,
acronyms, technical jargon, currency, dates, numbers, pauses, emotional neutrality,
and each launch language. Include quiet/noisy rooms, reverberation, varied
microphones, accents, packet loss and playback echo for audience STT. Measure WER
and critical entity error rate, but have people inspect errors that change meaning.
Voice similarity scores are not an authentication mechanism or proof of consent.

Decode synthesized audio and measure actual duration/sample rate. Check loudness
and true peak after final mix/encoding, not only on individual clips. A transcript
comparison can detect omissions but is not conclusive; forced alignment and human
sampling must inspect uncertainty and critical numbers.

Test MP4, PPTX, captions and browser presentation independently. Inspect PowerPoint
desktop/web as supported targets and document version/platform. If LibreOffice or
Google Slides is promised, test it explicitly; do not assume embedded audio,
fonts, animation and reading order survive conversion. Video does not guarantee
an editable or accessible PPTX. A PDF export is a future deliverable unless a
specific exporter and validation path are added.

## 6. Failure injection and operational rehearsal

In staging, terminate a specific render/worker process, drop a provider connection,
simulate 429/5xx, exhaust disk/memory, rotate a credential, deny storage writes,
and interrupt a migration/restore rehearsal. Test long queues, provider rate
limits and cancellation storms using synthetic traffic, not paid uncontrolled load.

Confirm cancellation leaves no published partial artifact, deduplication prevents
duplicate releases, checkpoints resume safely, and revoked consent cannot be
restored by rolling back an older application. Authorization/revocation state
must remain current even when content/model configuration rolls back.

Exercise backup restoration into an isolated environment and prove collection,
manifest and object consistency. Initial proposed objectives: metadata RPO <= 1 h
and service RTO <= 4 h, subject to chosen managed services and cost approval.
Retain immutable approved artifacts according to owner policy, not indefinitely.

Alerts should cover failed jobs, missing citations, consent violations, unexpected
cost, elevated handoffs, queue age, provider retirement, latency and error rates.
Assign an on-call/operator and a moderator escalation path. A synthetic health
check must not synthesize the owner's voice publicly or spend without a cap.

## 7. CI, release and delivery acceptance

Proposed CI stages, to wire only once the corresponding code exists:

1. PR: lint/type/schema checks, secret/dependency checks, deterministic unit tests,
   contract fixtures and a small frozen evaluation subset.
2. Protected staging: real persistence/workflow integration, full fixed corpus,
   opt-in provider smoke checks, visual/media tests and E2E scenarios.
3. Release candidate: representative load/soak, access/privacy/failure tests,
   backup/restore, full dress rehearsal and owner/moderator approval.
4. Canary: limited consenting users with explicit observation window and rollback
   thresholds; promote only after the agreed latency, cost and quality gates hold.

Deployment configuration must pin reviewed dependency versions and action SHAs,
use least-privilege permissions and protected environments, and keep production
secrets out of PR jobs. Do not add a workflow that references nonexistent packages
or tests and report it as a working quality gate.

Final delivery checklist:

- Accepted feature scope, supported languages/players, cost ceilings and SLOs.
- Passing per-case reports, known limitations, owner voice sign-off and rights/
  provider verification records stored privately.
- Complete signed sample bundle and evidence lineage; reproducible locked build.
- Production monitoring, budget alerts, moderator stop, tested revocation/deletion,
  restore and rollback procedures, and named support/incident ownership.
- User/admin/API documentation, moderator training, accessibility review and
  retained release approval.
- Production credentials provisioned securely and handover accepted by the owner.

Do not call the product delivered solely because documentation, a demo video or
an LLM evaluation score exists. Delivery requires a working deployment, validated
artifacts, operational controls and explicit acceptance.
