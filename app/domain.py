import hashlib
import json
import unicodedata
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\r\n\t]+$")
]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value: BaseModel) -> str:
    return digest(json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    @field_validator("*")
    @classmethod
    def safe_text(cls, value: object) -> object:
        if isinstance(value, str) and any(
            (unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\r\t")
            or char in "\ufffe\uffff"
            for char in value
        ):
            raise ValueError("Text contains unsupported control characters")
        return value


class SourceInput(Contract):
    title: Label = Field(max_length=64)
    content: Text = Field(max_length=50_000)
    rights_reference: Text = Field(max_length=200)


class Source(SourceInput):
    id: Identifier
    content_hash: Digest
    state: Literal["pending", "approved", "withdrawn"]
    created_at: datetime


class HashApproval(Contract):
    expected_hash: Digest
    reviewed: Literal[True]


class Brief(Contract):
    title: Label = Field(max_length=64)
    source_ids: list[Identifier] = Field(min_length=1, max_length=10)
    slide_count: int = Field(default=5, ge=1, le=12, strict=True)
    generator: Literal["extractive", "openai"] = "extractive"

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Source IDs must be unique")
        return value


class Selection(Contract):
    source_id: Identifier
    quote: Text = Field(max_length=280)


class Selections(Contract):
    selections: list[Selection] = Field(min_length=1, max_length=12)


class Citation(Contract):
    source_id: Identifier
    source_title: Label = Field(max_length=64)
    source_hash: Digest
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    quote: Text = Field(max_length=280)

    @model_validator(mode="after")
    def consistent_span(self) -> Self:
        if self.end - self.start != len(self.quote):
            raise ValueError("Citation span must match quote length")
        return self


class Slide(Contract):
    id: Identifier
    title: Label = Field(max_length=64)
    citation: Citation


class DeckSpec(Contract):
    schema_version: Literal["1"] = "1"
    title: Label = Field(max_length=64)
    slides: list[Slide] = Field(min_length=1, max_length=12)

    @field_validator("slides")
    @classmethod
    def unique_slides(cls, value: list[Slide]) -> list[Slide]:
        if len({slide.id for slide in value}) != len(value):
            raise ValueError("Slide IDs must be unique")
        return value


class Presentation(Contract):
    id: Identifier
    brief: Brief
    state: Literal["generating", "awaiting_approval", "approved", "failed"]
    created_at: datetime
    generator_version: str
    deck: DeckSpec | None = None
    deck_hash: Digest | None = None
    approved_hash: Digest | None = None
    error_code: str | None = None


class Problem(Exception):
    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False):
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(code)
