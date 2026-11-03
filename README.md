# myAI-Assistant-with-voice-trademark

A project for an AI assistant that presents approved material in the author's authorized voice and handles interactive audience questions. Authorization is not the same as trademark registration; see [Voice protection and unauthorized cloning](#voice-protection-and-unauthorized-cloning). The first runnable increment implements reviewed text sources, citation-linked draft slides, explicit approval, and editable PowerPoint export. Voice, video, and audience interaction remain planned; the older code examples later in this README are illustrative, not the running application.

## Run the first implementation

See the [local setup, demo, API, and delivery status](docs/local-development.md).
Python 3.12 and Node.js 22+ are required. The default extractive generator needs
no paid API or voice enrollment.

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

In another terminal with the **same token** and activated environment, run
`python examples/demo.py`. It pauses for source/deck approval and produces
`.local-data/demo.pptx`. Interactive API documentation is at
`http://127.0.0.1:8000/docs`; authorize with the token. Run `pytest` after building
the renderer to exercise real PPTX generation alongside API and provider tests.

**Local development only:** one owner, one process, SQLite, no public exposure.
This is not yet the complete voice presentation product or a production service.

## Goals and boundaries

- Deliver presentations from a reviewed knowledge base and answer audience questions in real time.
- Keep the assistant's spoken content grounded in approved sources and make it clear that the voice/avatar is AI-generated.
- Use only a voice and likeness for which the project owner has explicit rights and consent. Do not impersonate another person.
- Keep provider credentials on the server, minimize stored audience data, and provide a human moderator and a stop/disable control.

## Automated presentation product blueprint

The proposed product takes an authorized brief and reviewed sources, produces a cited
slide deck and narration in the owner's verified voice, renders a captioned video,
and optionally runs moderated audience Q&A. Routine generation can be automated;
voice enrollment, rights confirmation, disputed facts, and production approval
remain explicit human responsibilities.

| Design document | Contents |
|---|---|
| [Architecture and model selection](docs/presentation-architecture.md) | Specific LLM, speech, image, and embedding choices; tool integration; activity, data-flow, sequence, state, deployment, and delivery diagrams |
| [Software implementation guide](docs/implementation-guide.md) | Service boundaries, typed contracts, API/data design, reliability, voice authorization, implementation milestones, and delivery artifacts |
| [Validation and product delivery](docs/validation-and-delivery.md) | Source verification, measurable quality gates, voice and media testing, failure injection, release gates, and operational acceptance |

**Status:** The architecture documents describe the full target; the
[delivery status](docs/local-development.md#delivery-status-and-open-decisions)
identifies the smaller implemented increment and remaining decisions. There is a
local API, source/deck approval, an optional OpenAI evidence-selection adapter,
PPTX renderer, tests, and CI. There is no voice enrollment, speech/video, live
audience mode, or production deployment yet. Model identifiers were checked against
official SDK source on 2026-11-03; provider access, pricing, and compatibility still
require account-level preflight before live use.

## Voice protection and unauthorized cloning

**You cannot make a voice impossible to clone by registering a trademark.** A sound trademark protects a distinctive sound that identifies the commercial source of specified goods or services, subject to applicable law. It does not grant worldwide ownership of your vocal timbre or prohibit every imitation. Legal rights, contracts, secure deployment, provenance, and incident response should work together.

This section is general information, not legal advice or evidence that the author's voice is a registered trademark. India and the United States are examples, not an assumption about the owner's location. A qualified lawyer should confirm the relevant countries, current law, exceptions, and filing requirements before registration or enforcement.

### How to seek protection

1. **Define the brand sound.** Consider a distinctive spoken signature, audio logo, or other fixed sound used consistently to identify your assistant's services. A normal speaking voice alone is not automatically a registrable mark. Search for conflicting marks and ask a trademark professional whether the proposed sound is distinctive and non-functional.
2. **Apply in relevant territories and classes.** Trademark rights are territorial and tied to goods/services. Prepare the sound description, audio, and evidence of source-identifying use required by the relevant office. India's Trade Marks Rules, 2017, Rule 26(5), require an MP3 no longer than 30 seconds and a graphical representation of its notations; meeting that format does not guarantee registration. The USPTO also recognizes source-identifying sound marks. Use official filing guidance, not an assumed universal "voice trademark" process.
3. **Protect identity separately.** Depending on jurisdiction and facts, personality/publicity rights, privacy, passing off or false endorsement, and fraud laws may address unauthorized impersonation or commercial exploitation. These are distinct from trademark rights and can have exceptions, including protected expression. Do not assume celebrity court orders automatically apply to everyone.
4. **Protect recordings and contractual rights.** Copyright may protect particular recordings or performances, not your voice identity as such; ownership and exceptions must be checked. Written provider and licensee agreements should limit training, synthesis, sharing, sublicensing, retention, and reuse, and require deletion and incident cooperation where enforceable.
5. **Maintain a private rights record.** Keep consent agreements, registration details if granted, authorized provider/model IDs, license scope and expiry, and original recordings with dated provenance. Do not publish enrollment recordings, biometric voiceprints, or confidential agreements in this repository. Never claim registration or use a registered-mark symbol before applicable registration permits it.

Suggested public notice, to adapt with counsel:

> This project's authorized AI voice may be used only with the voice owner's express permission and within the agreed scope. We do not authorize third-party voice-model training, cloning, impersonation, or misleading endorsement. Suspected misuse should be reported through our designated abuse channel. This notice does not create trademark registration, override legal exceptions, or determine criminal liability.

Publish a monitored abuse contact before deployment. A notice communicates your position but cannot technically stop an outsider or bind everyone by itself.

### Prevent and control misuse in this assistant

These are **implementation requirements**, not controls already implemented by the illustrative code:

- Keep enrollment audio and voice models private and encrypted; use least-privilege access, strong administrator authentication, server-side provider credentials, and audit trails.
- Require verified owner consent before enrollment. Bind each synthesis request to an authenticated account, approved text, and an active voice license; reject expired or revoked authorization.
- Restrict model export, bulk synthesis, and third-party access. Apply rate limits and abuse alerts, and choose providers with documented consent verification, reuse restrictions, deletion procedures, and responsive abuse reporting.
- Provide clear AI disclosure and, where supported, audio watermarking plus cryptographically signed provenance linking an output hash to its issuer, time, and model/version. Keep signing keys protected and publish how to verify authorized output through an official channel.
- Add an owner/moderator kill switch to stop new synthesis, terminate active sessions, and revoke affected credentials and provider access. Seek deletion of compromised models and stored data under applicable agreements. Revocation cannot erase audio already downloaded or force an unrelated external model to stop.
- Do not approve payments, account recovery, or sensitive actions from voice similarity alone. Use independent authentication and confirm suspicious requests through a previously known contact channel.

Public speech can still be recorded and used by outsiders. No watermark, access control, or voice registration guarantees that cloning will never occur.

### Identify suspected clones without claiming certainty

Use several independent signals rather than a single "deepfake score":

1. **Check provenance and authorization.** Verify any signed output manifest against trusted issuer keys, the audio hash, and the authorization record. A valid signature establishes the signed file's origin and integrity, not that its words are true or that the speaker personally said them. Missing provenance is not proof of a fake; genuine recordings may lack it.
2. **Corroborate the context.** Confirm the claimed event or instruction with the owner through a trusted channel; compare official publications and permitted provider audit records. Speaker similarity may indicate whose voice is being imitated, but does not establish authenticity, consent, or the offender's identity.
3. **Use detectors as screening tools.** Synthetic-audio classifiers, watermark checks, and speaker comparisons can produce false positives and false negatives, especially after compression, re-recording, or exposure to unfamiliar models. Validate on representative recordings and require human review; do not automatically accuse or punish someone based on a score.
4. **Preserve evidence before requesting removal.** Keep the original file without alteration, its cryptographic hash, URLs, account identifiers, UTC capture times, relevant messages, and a record of who handled the evidence. Keep screenshots and working copies separate from originals. Store evidence securely with limited access; do not republish harmful audio or submit sensitive voice samples to unapproved services.
5. **Escalate disputed or high-impact cases.** Use a qualified audio-forensics professional and counsel for attribution, chain of custody, and evidentiary requirements. NIST's synthetic-content report explains why detection and provenance need a layered approach rather than a guaranteed authenticity test.

### Incident severity and lawful consequences

**Unauthorized cloning may be harmful or offensive, but it is not automatically a criminal offense everywhere.** Liability depends on consent, use, intent, harm, jurisdiction, and applicable legal exceptions. The following levels are operational priorities, not statutory sentencing categories. Courts determine damages and sentences; authorities investigate and prosecute offenses. This project cannot impose fines or imprisonment.

| Severity | Example | Control and escalation | Potential lawful consequence, if established |
|---|---|---|---|
| Low | Unverified similarity report with no demonstrated deception or harm | Preserve the report, check authorization, and review before taking action | No assumed violation or penalty; close unsupported reports or seek clarification |
| Medium | Confirmed unauthorized distribution or commercial reuse | Preserve evidence, revoke project access where justified, report under relevant platform/provider rules, and consult counsel | Contract remedies, removal, or civil relief where a valid claim exists |
| High | Misleading endorsement, reputational harm, repeated impersonation, or attempted fraud | Urgent platform/provider reports, containment, owner notification, and legal review; report suspected crime | Injunctions and damages where available; criminal investigation if offense requirements are met |
| Critical | Active financial fraud, extortion, credible threats, or immediate safety risk | Contact the bank/payment provider and relevant police or emergency service immediately; preserve evidence and contain access | Prosecution and statutory penalties for proven offenses; outcomes depend on the facts and law |

**India example:** Information Technology Act, 2000, Section 66D addresses cheating by personation using a communication device or computer resource. It provides imprisonment up to **three years** and liability to a fine up to **one lakh rupees**. Voice cloning alone does not establish this offense; the elements of cheating by personation must be met. Other offenses may apply to threats, extortion, or fraud, but there is no universal "voice cloning sentence." For cybercrime, use the [National Cyber Crime Reporting Portal](https://cybercrime.gov.in/); for financial cyberfraud, promptly contact **1930** and your bank. These channels do not guarantee recovery.

For any jurisdiction, counsel can assess a preservation request, a cease-and-desist letter, platform removal, an injunction, and damages. Use the correct complaint basis: impersonation/privacy complaints differ from trademark or copyright complaints. Request only relief supported by your rights and the evidence. Do not retaliate, dox suspects, hack accounts, or publicly identify an alleged offender solely from detector output. Internal suspensions should include documented reasons, human review, and an appeal path unless urgent containment is needed.

### Official references

- [USPTO sound trademark examples](https://www.uspto.gov/trademarks/soundmarks/trademark-sound-mark-examples): source-identifying sounds, not blanket ownership of a voice.
- [IP India: Trade Marks Rules, 2017](https://ipindia.gov.in/writereaddata/Portal/Images/pdf/Trade_Marks_Rules_2017.pdf): Rule 26(5), sound-mark submission requirements.
- [U.S. Copyright Office: AI initiative and digital-replica report](https://www.copyright.gov/ai/): distinctions between existing protections and recommended legal reforms; recommendations are not themselves enacted law.
- [India Code: Information Technology Act, 2000](https://indiacode.nic.in/handle/123456789/1999): see Section 66D for the offense and statutory maximum penalties.
- [Government of India: Cyber Frauds Helpline](https://pib.gov.in/Pressreleaseshare.aspx?PRID=1814120): financial cyberfraud reporting through 1930.
- [NIST AI 100-4: Reducing Risks Posed by Synthetic Content](https://doi.org/10.6028/NIST.AI.100-4): provenance, watermarking, detection, and their limitations.

Recheck official sources before filing or enforcement. This README does not assert that pending digital-replica proposals have become law.

## System design

```text
┌────────────────────────────── Audience experience ───────────────────────────┐
│ Browser: microphone/text input, captions, transcript, avatar, moderator UI   │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ WebRTC or WebSocket; authenticated session
                                ▼
┌────────────────────────────── Application API ──────────────────────────────┐
│ Session/auth │ rate limits │ consent notice │ orchestration │ audit events  │
└───────────────┬───────────────────────────┬──────────────────┬──────────────┘
                │                           │                  │
                ▼                           ▼                  ▼
       Speech-to-text             Agent workflow       Text-to-speech / avatar
       (optional)                  ├─ safety gate      (provider adapters)
                                   ├─ knowledge search
                                   └─ answer composer
                                         │
                                         ▼
                              Approved knowledge base
                         documents → chunks → embeddings/index

       Observability and MLOps: evaluation, traces, versioned prompts/indexes,
       privacy-aware metrics, staged releases, rollback and incident response
```

### Request flow

1. The audience sends a text question or audio. Audio transcription is optional; text input remains available.
2. The API validates the session, applies rate limits, and sends the question through input safety checks.
3. The knowledge agent retrieves relevant passages only from the published knowledge collection.
4. The answer agent drafts a concise answer with source references. The safety gate rejects unsupported or disallowed answers and can request clarification or moderator help.
5. The response is shown as text/captions. If approved, the speech adapter generates audio; an optional avatar adapter receives the audio/text and returns a visual stream.
6. The system records operational metadata and evaluation signals, not raw audio or full transcripts by default. Retention and opt-in settings should be explicit.

## AI agents

Use a bounded, observable workflow rather than giving agents unrestricted tools. Each agent has one responsibility and passes typed data to the next stage.

| Agent | Input | Responsibility | Output / fallback |
|---|---|---|---|
| Input safety | Text or transcript | Detect abuse, secrets, and out-of-scope requests | Allow, refuse, or escalate |
| Knowledge retrieval | Approved question | Search the published index and rank evidence | Top passages with document IDs |
| Answer composer | Question and passages | Draft a brief, source-grounded answer | Text and citations; ask for clarification when evidence is weak |
| Response safety | Draft and citations | Verify grounding, policy, and presentation suitability | Approved text or refusal/escalation |
| Presentation controller | Approved text and session state | Manage turns, timing, captions, and moderator handoff | UI events; never invent facts |
| Speech/avatar adapters | Approved text/audio | Call configured providers and normalize streaming output | Audio/video stream or an explicit provider error |

A retrieval-augmented generation (RAG) index should contain only reviewed material. Keep each answer's citations and the knowledge-index version so quality problems can be traced to a source or release.

## Reference orchestration code

This Python example illustrates the service boundary and controlled agent flow. Provider adapters, authentication, persistence, streaming transport, and concrete model calls must be implemented for the deployment environment; the placeholders deliberately fail rather than returning success-shaped mock output.

```python
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Passage:
    document_id: str
    text: str
    score: float


@dataclass(frozen=True)
class Answer:
    text: str
    citations: tuple[str, ...]
    approved: bool


class KnowledgeIndex(Protocol):
    async def search(self, question: str, *, limit: int = 5) -> Sequence[Passage]: ...


class AnswerModel(Protocol):
    async def draft(self, question: str, evidence: Sequence[Passage]) -> str: ...


class ResponseGuard(Protocol):
    async def approve(self, text: str, evidence: Sequence[Passage]) -> bool: ...


async def answer_question(
    question: str,
    *,
    index: KnowledgeIndex,
    model: AnswerModel,
    guard: ResponseGuard,
    min_evidence_score: float = 0.35,
) -> Answer:
    normalized = question.strip()
    if not normalized:
        raise ValueError("Question must not be empty")

    evidence = await index.search(normalized, limit=5)
    grounded = [p for p in evidence if p.score >= min_evidence_score]
    if not grounded:
        return Answer(
            text="I could not find a reliable answer in the approved presentation material. "
                 "Please ask the moderator.",
            citations=(),
            approved=True,
        )

    draft = (await model.draft(normalized, grounded)).strip()
    if not draft:
        raise RuntimeError("Answer model returned an empty response")

    if not await guard.approve(draft, grounded):
        return Answer(
            text="I cannot confidently answer that from the approved material. "
                 "Please ask the moderator.",
            citations=tuple(dict.fromkeys(p.document_id for p in grounded)),
            approved=False,
        )

    return Answer(
        text=draft,
        citations=tuple(dict.fromkeys(p.document_id for p in grounded)),
        approved=True,
    )
```

The API layer should validate identity/session authorization, input size, and rate limits before calling this workflow. The speech/avatar layer should accept only approved answer text and return explicit timeouts/provider failures to the client; it must not silently substitute unrelated output.

## Voice and avatar integration

Keep vendor SDKs behind small adapters so the application can switch providers without changing agent logic. The original proposal names ElevenLabs or Hume AI for voice and HeyGen or Tavus for an avatar; compare their current APIs, latency, streaming support, data handling, and consent requirements before selecting one. Credentials belong in a managed secret store, never in the browser or repository.

```python
from typing import Protocol


class SpeechProvider(Protocol):
    async def stream_speech(self, text: str, *, voice_id: str): ...


class AvatarProvider(Protocol):
    async def start_session(self, *, session_id: str, voice_id: str): ...
    async def send_audio(self, session_id: str, audio_chunk: bytes) -> None: ...
```

Stream text and captions as early as safely possible. Apply bounded timeouts, retry only idempotent operations, and expose degraded modes (text-only answer or moderator handoff) when a provider is unavailable.

## Knowledge and data preparation

1. Collect presentation material that the owner is authorized to use.
2. Remove secrets and unnecessary personal data; record document title, revision, owner, and publication status.
3. Parse and chunk documents while preserving headings and source locations.
4. Build embeddings and an index from approved content only. Record the embedding model and index build/version.
5. Evaluate retrieval and answer quality against a reviewed question set before publishing an index.
6. Retire old indexes predictably and keep the previous known-good version available for rollback.

Do not use audience recordings or transcripts for model training by default. If any collection or training is introduced, obtain informed consent, define retention/deletion rules, and document the intended use.

## MLOps and release lifecycle

Treat prompts, evaluation datasets, model/provider settings, and knowledge indexes as versioned release inputs. Track quality and reliability without making raw audience content the default telemetry.

- **Data/index:** validate source manifests; scan for secrets; build an immutable, versioned index; record source revisions and embedding configuration.
- **Evaluation:** run regression questions for retrieval recall, citation correctness, groundedness, refusal behavior, latency, and cost. Require human review for voice quality and presentation behavior.
- **Release:** test and evaluate on every change; deploy to staging; use a small canary; promote only after gates pass. Keep the prior prompt/index/config for rollback.
- **Monitoring:** measure errors, latency, provider availability, escalation rate, retrieval misses, and user feedback. Alert on thresholds and have a moderator stop switch.
- **Governance:** document voice consent, model/provider versions, data retention, access controls, release approvals, and incident/rollback procedures. Apply the [voice protection requirements](#voice-protection-and-unauthorized-cloning), including authorization revocation, provenance checks, and severity-based incident escalation.

Example evaluation gate (the evaluator should use a curated, non-sensitive dataset):

```python
# eval_gate.py — illustrative CI gate; wire run_suite to the chosen evaluation stack.
from dataclasses import dataclass


@dataclass(frozen=True)
class Metrics:
    citation_accuracy: float
    groundedness: float
    refusal_recall: float
    p95_latency_ms: int


def assert_release_ready(metrics: Metrics) -> None:
    if metrics.citation_accuracy < 0.95:
        raise SystemExit("Release blocked: citation accuracy below 0.95")
    if metrics.groundedness < 0.90:
        raise SystemExit("Release blocked: groundedness below 0.90")
    if metrics.refusal_recall < 0.95:
        raise SystemExit("Release blocked: refusal recall below 0.95")
    if metrics.p95_latency_ms > 3000:
        raise SystemExit("Release blocked: p95 latency above 3000 ms")


if __name__ == "__main__":
    raise SystemExit("Connect this gate to the project's evaluation runner")
```

The thresholds above are starting examples, not universal targets. Calibrate them with the owner and moderator using representative test cases before using the gate to approve production releases.

The executable foundation CI is [`.github/workflows/foundation.yml`](.github/workflows/foundation.yml);
it builds the actual renderer and runs the current tests without paid API keys.
The following is an illustrative future full-product gate, not an installed
workflow: its `requirements.txt` and `eval_gate.py` references are not implemented.
Add deployment only after configuring repository secrets, environment approvals,
and a rollback target:

```yaml
# .github/workflows/assistant-quality.yml
name: Assistant quality
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  test-and-evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -r requirements.txt
      - run: python -m pytest
      - run: python eval_gate.py
```

Pin dependencies and GitHub Actions to reviewed versions or commit SHAs in production, and avoid putting provider keys or real audience data in CI logs/artifacts.

## Suggested repository structure

```text
app/
  api.py                 # Session API and transport boundary
  agents/                # Safety, retrieval, answer, and presentation workflow
  providers/             # Speech, avatar, LLM, and embedding adapters
  knowledge/             # Ingestion and index-building pipeline
  observability/         # Redacted metrics, traces, and audit events
evals/
  cases.jsonl            # Curated, non-sensitive evaluation cases
tests/
  test_agents.py
  test_knowledge.py
eval_gate.py
.github/workflows/
  assistant-quality.yml
```

## Implementation milestones

1. Build a text-only prototype using an approved knowledge collection, citations, and a moderator handoff.
2. Add evaluation cases and establish quality, latency, and cost baselines.
3. Add optional speech input and authorized voice output with clear AI disclosure and text captions. Implement consent/license checks, protected enrollment storage, abuse reporting, and a tested voice-revocation control before enabling synthesis.
4. Add an avatar only after the voice/text flow, consent, and provider fallback behavior are validated.
5. Add staged deployment, monitoring, retention controls, and a tested rollback process before public use.
