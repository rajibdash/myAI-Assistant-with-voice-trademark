import json
from datetime import UTC, datetime

import httpx
import pytest

from app.domain import Brief, Problem, Source, digest
from app.providers import ExtractiveGenerator, OpenAISelector


def source() -> Source:
    return Source(
        title="Synthetic",
        content="Exact evidence is 42 units.",
        rights_reference="Test author",
        id="a" * 32,
        content_hash=digest("Exact evidence is 42 units."),
        state="approved",
        created_at=datetime.now(UTC),
    )


def completed(text: str) -> dict[str, object]:
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
    }


def test_openai_request_uses_strict_schema_no_storage_and_no_tools() -> None:
    evidence = source()
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 4000
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["schema"]["additionalProperties"] is False
        assert "tools" not in payload
        assert request.headers["authorization"] == "Bearer synthetic-test-key"
        return httpx.Response(
            200,
            json=completed(
                json.dumps(
                    {
                        "selections": [{"source_id": evidence.id, "quote": evidence.content}],
                    }
                )
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = OpenAISelector("synthetic-test-key", "test-model", client).select(
            Brief(title="Title", source_ids=[evidence.id]), [evidence]
        )
    assert result.selections[0].quote == evidence.content
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"status": "incomplete", "output": []},
        {"status": "completed", "output": []},
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "refusal", "refusal": "Cannot comply"},
                    ],
                }
            ],
        },
        completed("not-json"),
        completed('{"selections": []}'),
        completed('{"selections": [{"source_id": "bad-id", "quote": "Invented"}]}'),
        [],
        None,
    ],
)
def test_invalid_or_refused_responses_fail_explicitly(body: object) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=json.dumps(body).encode())
        )
    ) as client:
        with pytest.raises(Problem, match="provider_invalid_output"):
            OpenAISelector("test-key", "test-model", client).select(
                Brief(title="Title", source_ids=[source().id]), [source()]
            )


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_provider_errors_are_redacted_and_not_retried(status: int) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": "private provider content"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(Problem, match="provider_rejected") as caught:
            OpenAISelector("test-key", "test-model", client).select(
                Brief(title="Title", source_ids=[source().id]), [source()]
            )
    assert "private" not in caught.value.message
    assert len(calls) == 1


def test_timeout_is_not_automatically_retried() -> None:
    calls = []

    def timeout(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("private request body", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(Problem, match="provider_connection_failed"):
            OpenAISelector("test-key", "test-model", client).select(
                Brief(title="Title", source_ids=[source().id]), [source()]
            )
    assert len(calls) == 1


def test_extractive_long_unbroken_unicode_and_duplicate_text() -> None:
    for text in ["Budget is 42.\n" * 1000, "Café example: 42 units."]:
        evidence = source().model_copy(update={"content": text})
        result = ExtractiveGenerator().select(
            Brief(title="Title", source_ids=[evidence.id], slide_count=12), [evidence]
        )
        assert 1 <= len(result.selections) <= 12
        assert len({selection.quote for selection in result.selections}) == len(result.selections)
        assert all(selection.quote in text for selection in result.selections)
        assert all(len(selection.quote) <= 280 for selection in result.selections)


def test_extractive_does_not_cut_a_long_token_in_half() -> None:
    evidence = source().model_copy(update={"content": "1" * 281})
    with pytest.raises(Problem, match="excerpt_too_long"):
        ExtractiveGenerator().select(Brief(title="Title", source_ids=[evidence.id]), [evidence])
