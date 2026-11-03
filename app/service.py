import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from app.domain import (
    Brief,
    Citation,
    DeckSpec,
    HashApproval,
    Presentation,
    Problem,
    Selections,
    Slide,
    Source,
    SourceInput,
    canonical_hash,
    digest,
)
from app.providers import Generator
from app.store import Store


def quote_offset(content: str, quote: str) -> int | None:
    start = content.find(quote)
    while start >= 0:
        end = start + len(quote)
        if (start == 0 or content[start - 1].isspace()) and (
            end == len(content) or content[end].isspace()
        ):
            return start
        start = content.find(quote, start + 1)
    return None


def build_deck(brief: Brief, sources: list[Source], selections: Selections) -> DeckSpec:
    if len(selections.selections) > brief.slide_count:
        raise Problem(422, "too_many_slides", "Generator exceeded requested slide count")
    by_id = {source.id: source for source in sources}
    slides: list[Slide] = []
    seen: set[tuple[str, str]] = set()
    for selection in selections.selections:
        source = by_id.get(selection.source_id)
        start = quote_offset(source.content, selection.quote) if source else None
        if source is None or start is None:
            raise Problem(422, "unsupported_quote", "Quote does not occur in the approved sources")
        key = (source.id, selection.quote)
        if key in seen:
            raise Problem(422, "duplicate_quote", "Duplicate evidence selection")
        seen.add(key)
        slides.append(
            Slide(
                id=uuid4().hex,
                title=source.title,
                citation=Citation(
                    source_id=source.id,
                    source_title=source.title,
                    source_hash=source.content_hash,
                    start=start,
                    end=start + len(selection.quote),
                    quote=selection.quote,
                ),
            )
        )
    return DeckSpec(title=brief.title, slides=slides)


def validate_deck(deck: DeckSpec, brief: Brief, sources: list[Source]) -> None:
    by_id = {source.id: source for source in sources}
    if any(source.state != "approved" for source in sources):
        raise Problem(409, "stale_evidence", "A pinned source is no longer approved")
    if deck.title != brief.title or len(deck.slides) > brief.slide_count:
        raise Problem(422, "invalid_deck", "Deck does not match the brief")
    for slide in deck.slides:
        citation = slide.citation
        source = by_id.get(citation.source_id)
        if (
            source is None
            or source.state != "approved"
            or source.content_hash != citation.source_hash
            or source.title != citation.source_title
            or slide.title != source.title
            or source.content[citation.start : citation.end] != citation.quote
            or quote_offset(source.content, citation.quote) != citation.start
        ):
            raise Problem(409, "stale_evidence", "Deck evidence is invalid or no longer approved")


class Service:
    def __init__(self, store: Store, generators: dict[str, Generator]):
        self.store = store
        self.generators = generators

    def add_source(self, data: SourceInput, key: str) -> Source:
        with self.store.transaction() as connection:
            previous = self.store.replay(connection, "sources", key, data)
            if previous:
                return Source.model_validate_json(self.store.get(connection, "source", previous))
            source = Source(
                **data.model_dump(),
                id=uuid4().hex,
                content_hash=digest(data.content),
                state="pending",
                created_at=datetime.now(UTC),
            )
            self.store.put(connection, "source", source.id, source)
            self.store.reserve(connection, "sources", key, data, source.id)
            self.store.audit(connection, "source_created", source.id, source.content_hash)
            return source

    def source(self, source_id: str) -> Source:
        with self.store.transaction() as connection:
            return Source.model_validate_json(self.store.get(connection, "source", source_id))

    def review_source(self, source_id: str, approval: HashApproval) -> Source:
        with self.store.transaction() as connection:
            source = Source.model_validate_json(self.store.get(connection, "source", source_id))
            if source.content_hash != approval.expected_hash:
                raise Problem(409, "hash_mismatch", "Review must match the current source hash")
            if source.state == "withdrawn":
                raise Problem(409, "source_withdrawn", "A withdrawn source cannot be reactivated")
            if source.state != "approved":
                source.state = "approved"
                self.store.put(connection, "source", source_id, source)
                self.store.audit(connection, "source_approved", source_id, source.content_hash)
            return source

    def withdraw_source(self, source_id: str) -> Source:
        with self.store.transaction() as connection:
            source = Source.model_validate_json(self.store.get(connection, "source", source_id))
            if source.state != "withdrawn":
                source.state = "withdrawn"
                self.store.put(connection, "source", source_id, source)
                self.store.audit(connection, "source_withdrawn", source_id, source.content_hash)
            return source

    def presentation(self, presentation_id: str) -> Presentation:
        with self.store.transaction() as connection:
            return Presentation.model_validate_json(
                self.store.get(connection, "presentation", presentation_id)
            )

    def generate(self, brief: Brief, key: str) -> Presentation:
        with self.store.transaction() as connection:
            previous = self.store.replay(connection, "presentations", key, brief)
            if previous:
                return Presentation.model_validate_json(
                    self.store.get(connection, "presentation", previous)
                )
            sources = [
                Source.model_validate_json(self.store.get(connection, "source", source_id))
                for source_id in brief.source_ids
            ]
            if any(source.state != "approved" for source in sources):
                raise Problem(409, "source_not_approved", "All sources must be explicitly approved")
            if sum(len(source.content) for source in sources) > 50_000:
                raise Problem(
                    422, "source_budget_exceeded", "Combined source limit is 50,000 characters"
                )
            generator = self.generators.get(brief.generator)
            if generator is None:
                raise Problem(
                    503, "provider_not_configured", "Requested generator is not configured"
                )
            presentation = Presentation(
                id=uuid4().hex,
                brief=brief,
                state="generating",
                created_at=datetime.now(UTC),
                generator_version=generator.version,
            )
            self.store.put(connection, "presentation", presentation.id, presentation)
            self.store.reserve(connection, "presentations", key, brief, presentation.id)
            self.store.audit(connection, "generation_started", presentation.id)
        try:
            deck = build_deck(brief, sources, generator.select(brief, sources))
            with self.store.transaction() as connection:
                current_sources = [
                    Source.model_validate_json(self.store.get(connection, "source", source_id))
                    for source_id in brief.source_ids
                ]
                validate_deck(deck, brief, current_sources)
                presentation.deck = deck
                presentation.deck_hash = canonical_hash(deck)
                presentation.state = "awaiting_approval"
                self.store.put(connection, "presentation", presentation.id, presentation)
                self.store.audit(
                    connection, "draft_created", presentation.id, presentation.deck_hash
                )
        except Problem as error:
            with self.store.transaction() as connection:
                presentation.state = "failed"
                presentation.error_code = error.code
                self.store.put(connection, "presentation", presentation.id, presentation)
                self.store.audit(connection, "generation_failed", presentation.id)
            raise
        return presentation

    def approve(self, presentation_id: str, approval: HashApproval) -> Presentation:
        with self.store.transaction() as connection:
            presentation = Presentation.model_validate_json(
                self.store.get(connection, "presentation", presentation_id)
            )
            if presentation.deck is None or presentation.state not in {
                "awaiting_approval",
                "approved",
            }:
                raise Problem(409, "not_reviewable", "Presentation has no reviewable draft")
            if canonical_hash(presentation.deck) != approval.expected_hash:
                raise Problem(409, "hash_mismatch", "Approval must match the exact deck hash")
            sources = [
                Source.model_validate_json(self.store.get(connection, "source", source_id))
                for source_id in presentation.brief.source_ids
            ]
            validate_deck(presentation.deck, presentation.brief, sources)
            if presentation.state != "approved":
                presentation.state = "approved"
                presentation.approved_hash = approval.expected_hash
                self.store.put(connection, "presentation", presentation_id, presentation)
                self.store.audit(
                    connection, "presentation_approved", presentation_id, approval.expected_hash
                )
            return presentation

    def approved_deck(self, presentation_id: str) -> DeckSpec:
        with self.store.transaction() as connection:
            return self._approved_deck(connection, presentation_id)

    def _approved_deck(self, connection: sqlite3.Connection, presentation_id: str) -> DeckSpec:
        presentation = Presentation.model_validate_json(
            self.store.get(connection, "presentation", presentation_id)
        )
        if (
            presentation.state != "approved"
            or presentation.deck is None
            or presentation.approved_hash != canonical_hash(presentation.deck)
        ):
            raise Problem(409, "not_approved", "Exact deck approval is required before export")
        sources = [
            Source.model_validate_json(self.store.get(connection, "source", source_id))
            for source_id in presentation.brief.source_ids
        ]
        validate_deck(presentation.deck, presentation.brief, sources)
        return presentation.deck

    def record_export(self, presentation_id: str, expected_hash: str, artifact_hash: str) -> None:
        with self.store.transaction() as connection:
            deck = self._approved_deck(connection, presentation_id)
            if canonical_hash(deck) != expected_hash:
                raise Problem(409, "hash_mismatch", "Deck changed during rendering")
            self.store.audit(connection, "pptx_exported", presentation_id, artifact_hash)
