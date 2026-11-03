import pytest
from pydantic import ValidationError

from app.domain import Brief, Citation, SourceInput, canonical_hash, digest


@pytest.mark.parametrize("value", ["", "  ", "secret\x00data", "bad\x1bdata", "bad\ud800data"])
def test_source_rejects_empty_or_unsafe_text(value: str) -> None:
    with pytest.raises(ValidationError):
        SourceInput(title="Source", content=value, rights_reference="Owner-approved")


def test_contract_normalizes_outer_whitespace_and_rejects_extra_fields() -> None:
    source = SourceInput(title=" Title ", content=" Text\nhere ", rights_reference=" Owner ")
    assert source.content == "Text\nhere"
    assert source.title == "Title"
    assert digest(source.content) != digest(" Text\nhere ")
    with pytest.raises(ValidationError):
        SourceInput.model_validate(
            {"title": "Title", "content": "Text", "rights_reference": "Owner", "approved": True}
        )


def test_source_size_limit() -> None:
    SourceInput(title="Source", content="a" * 50_000, rights_reference="Owner")
    with pytest.raises(ValidationError):
        SourceInput(title="Source", content="a" * 50_001, rights_reference="Owner")


@pytest.mark.parametrize("title", ["Two\nlines", "Two\rlines", "Two\tparts"])
def test_titles_are_single_line(title: str) -> None:
    with pytest.raises(ValidationError):
        SourceInput(title=title, content="Evidence", rights_reference="Owner")


@pytest.mark.parametrize("count", [0, 13, True, 1.5, "5"])
def test_slide_count_strict_and_bounded(count: object) -> None:
    with pytest.raises(ValidationError):
        Brief.model_validate({"title": "Title", "source_ids": ["a" * 32], "slide_count": count})


def test_source_ids_unique_and_bounded() -> None:
    with pytest.raises(ValidationError):
        Brief(title="Title", source_ids=["a" * 32, "a" * 32])
    with pytest.raises(ValidationError):
        Brief(title="Title", source_ids=[])


def test_citation_span_must_match_text() -> None:
    with pytest.raises(ValidationError):
        Citation(
            source_id="a" * 32,
            source_hash="a" * 64,
            source_title="Source",
            quote="Exact quote",
            start=4,
            end=5,
        )


def test_hash_is_stable_across_model_roundtrip() -> None:
    brief = Brief(title="Title", source_ids=["a" * 32])
    assert canonical_hash(brief) == canonical_hash(
        Brief.model_validate_json(brief.model_dump_json())
    )
