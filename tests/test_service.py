from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.domain import (
    Brief,
    HashApproval,
    Problem,
    Selection,
    Selections,
    Source,
    SourceInput,
    canonical_hash,
)
from app.providers import ExtractiveGenerator
from app.service import Service, build_deck
from app.store import Store


def approved_source(service: Service, content: str = "The sample budget is 42 units.") -> Source:
    source = service.add_source(
        SourceInput(title="Synthetic source", content=content, rights_reference="Test author"),
        f"source-{content}",
    )
    return service.review_source(
        source.id, HashApproval(expected_hash=source.content_hash, reviewed=True)
    )


def test_pending_sources_cannot_generate(service: Service) -> None:
    source = service.add_source(
        SourceInput(title="Source", content="Pending evidence", rights_reference="Owner"),
        "pending-key",
    )
    with pytest.raises(Problem, match="source_not_approved"):
        service.generate(Brief(title="Title", source_ids=[source.id]), "draft-key")


def test_hash_approval_and_withdrawal(service: Service) -> None:
    source = approved_source(service)
    with pytest.raises(Problem, match="hash_mismatch"):
        service.review_source(source.id, HashApproval(expected_hash="0" * 64, reviewed=True))
    presentation = service.generate(Brief(title="Title", source_ids=[source.id]), "draft-key")
    assert presentation.deck is not None
    with pytest.raises(Problem, match="not_approved"):
        service.approved_deck(presentation.id)
    with pytest.raises(Problem, match="hash_mismatch"):
        service.approve(presentation.id, HashApproval(expected_hash="0" * 64, reviewed=True))
    approved = service.approve(
        presentation.id,
        HashApproval(expected_hash=canonical_hash(presentation.deck), reviewed=True),
    )
    assert approved.state == "approved"
    assert service.approved_deck(approved.id) == presentation.deck
    service.withdraw_source(source.id)
    with pytest.raises(Problem, match="stale_evidence"):
        service.approved_deck(approved.id)
    with pytest.raises(Problem, match="source_withdrawn"):
        service.review_source(
            source.id, HashApproval(expected_hash=source.content_hash, reviewed=True)
        )


def test_exact_quotes_round_robin_and_slide_limit(service: Service) -> None:
    first = approved_source(service, "First source has 42 units. " * 20)
    second = approved_source(service, "Second source has 100 units.")
    result = service.generate(
        Brief(title="Evidence", source_ids=[first.id, second.id], slide_count=4), "round-robin"
    )
    assert result.deck is not None
    assert len(result.deck.slides) <= 4
    assert result.deck.slides[1].citation.source_id == second.id
    for slide in result.deck.slides:
        source = service.source(slide.citation.source_id)
        assert source.content[slide.citation.start : slide.citation.end] == slide.citation.quote


@pytest.mark.parametrize("quote,source_id", [("Invented 999", None), ("Exact evidence", "0" * 32)])
def test_forged_evidence_rejected(service: Service, quote: str, source_id: str | None) -> None:
    source = approved_source(service, "Exact evidence")
    with pytest.raises(Problem, match="unsupported_quote"):
        build_deck(
            Brief(title="Title", source_ids=[source.id]),
            [source],
            Selections(selections=[Selection(source_id=source_id or source.id, quote=quote)]),
        )


@pytest.mark.parametrize("quote", ["The value is 4", "he value is 42.5", "The value is 42."])
def test_partial_word_and_number_quotes_rejected(service: Service, quote: str) -> None:
    source = approved_source(service, "The value is 42.5 units.")
    with pytest.raises(Problem, match="unsupported_quote"):
        build_deck(
            Brief(title="Title", source_ids=[source.id]),
            [source],
            Selections(selections=[Selection(source_id=source.id, quote=quote)]),
        )


def test_source_and_presentation_idempotency(service: Service) -> None:
    data = SourceInput(title="Source", content="Evidence", rights_reference="Owner")
    source = service.add_source(data, "source-key")
    assert service.add_source(data, "source-key").id == source.id
    with pytest.raises(Problem, match="idempotency_conflict"):
        service.add_source(data.model_copy(update={"content": "Different"}), "source-key")
    service.review_source(source.id, HashApproval(expected_hash=source.content_hash, reviewed=True))
    brief = Brief(title="Title", source_ids=[source.id])
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: service.generate(brief, "same-draft"), range(2)))
    assert results[0].id == results[1].id
    assert len([e for e in service.store.events() if e["action"] == "generation_started"]) == 1
    with pytest.raises(Problem, match="idempotency_conflict"):
        service.generate(brief.model_copy(update={"title": "Changed"}), "same-draft")


def test_provider_failure_persists_and_never_automatically_retries(service: Service) -> None:
    class FailedGenerator:
        version = "failed-test"
        calls = 0

        def select(self, brief: Brief, sources: list[Source]) -> Selections:
            self.calls += 1
            raise Problem(502, "provider_failure", "Synthetic failure")

    generator = FailedGenerator()
    service.generators["openai"] = generator
    source = approved_source(service)
    brief = Brief(title="Title", source_ids=[source.id], generator="openai")
    with pytest.raises(Problem, match="provider_failure"):
        service.generate(brief, "failed-key")
    replay = service.generate(brief, "failed-key")
    assert replay.state == "failed"
    assert replay.error_code == "provider_failure"
    assert generator.calls == 1


def test_source_withdrawn_during_generation_cannot_finish(service: Service) -> None:
    source = approved_source(service)

    class RevokingGenerator(ExtractiveGenerator):
        def select(self, brief: Brief, sources: list[Source]) -> Selections:
            service.withdraw_source(source.id)
            return super().select(brief, sources)

    service.generators["extractive"] = RevokingGenerator()
    brief = Brief(title="Title", source_ids=[source.id])
    with pytest.raises(Problem, match="stale_evidence"):
        service.generate(brief, "revoked-key")
    assert service.generate(brief, "revoked-key").state == "failed"


def test_persistence_restart_and_interrupted_job(tmp_path: Path) -> None:
    store = Store(tmp_path / "persistent.sqlite3")
    first = Service(store, {"extractive": ExtractiveGenerator()})
    source = approved_source(first)
    presentation = first.generate(Brief(title="Persist", source_ids=[source.id]), "persistent")
    second = Service(Store(store.path), {"extractive": ExtractiveGenerator()})
    assert second.presentation(presentation.id) == presentation
    presentation.state = "generating"
    with store.transaction() as connection:
        store.put(connection, "presentation", presentation.id, presentation)
    store.fail_interrupted_runs()
    assert second.presentation(presentation.id).error_code == "interrupted_generation"


def test_audit_has_no_raw_source_content(service: Service) -> None:
    private_text = "Private synthetic payload"
    source = approved_source(service, private_text)
    events = service.store.events()
    assert any(event["action"] == "source_approved" for event in events)
    assert private_text not in str(events)
    assert source.content_hash in str(events)


def test_unconfigured_generator_and_input_budget(service: Service) -> None:
    source = approved_source(service, "x" * 30_000)
    with pytest.raises(Problem, match="provider_not_configured"):
        service.generate(Brief(title="Title", source_ids=[source.id], generator="openai"), "no-key")
    second = approved_source(service, "y" * 30_000)
    with pytest.raises(Problem, match="source_budget_exceeded"):
        service.generate(Brief(title="Title", source_ids=[source.id, second.id]), "too-big")
