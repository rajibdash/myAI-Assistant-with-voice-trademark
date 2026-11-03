import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app.domain import DeckSpec
from app.main import ROOT, Settings, create_app
from app.render import PowerPointRenderer


def create_draft(client: TestClient) -> tuple[dict, dict]:
    source_response = client.post(
        "/v1/sources",
        headers={"Idempotency-Key": "example-source"},
        json={
            "title": "Synthetic evidence",
            "content": "The example budget is 42 units.",
            "rights_reference": "Synthetic data authored for this test",
        },
    )
    assert source_response.status_code == 200
    source = source_response.json()
    response = client.post(
        f"/v1/sources/{source['id']}/approve",
        json={"expected_hash": source["content_hash"], "reviewed": True},
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/presentations",
        headers={"Idempotency-Key": "example-presentation"},
        json={"title": "Sample presentation", "source_ids": [source["id"]], "slide_count": 1},
    )
    assert response.status_code == 200
    return source, response.json()


def approve(client: TestClient, presentation: dict) -> None:
    response = client.post(
        f"/v1/presentations/{presentation['id']}/approve",
        json={"expected_hash": presentation["deck_hash"], "reviewed": True},
    )
    assert response.status_code == 200


def test_authentication_and_health(client: TestClient) -> None:
    assert client.get("/health", headers={"Authorization": ""}).status_code == 200
    for authorization in ["", "Bearer invalid", "Basic invalid", "Bearer \u00e9"]:
        response = client.get("/v1/audit", headers={"Authorization": authorization.encode("utf-8")})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["code"] == "unauthorized"
    assert client.get("/v1/audit").status_code == 200


def test_invalid_requests_do_not_echo_sensitive_inputs(client: TestClient) -> None:
    response = client.post(
        "/v1/sources",
        headers={"Idempotency-Key": "example-source"},
        json={"title": "Private secret string", "content": "confidential", "unexpected": True},
    )
    assert response.status_code == 422
    assert "confidential" not in response.text
    assert "Private secret string" not in response.text
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/v1/sources/missing").status_code == 404


def test_idempotency_header_required(client: TestClient) -> None:
    response = client.post(
        "/v1/sources",
        json={"title": "Source", "content": "Evidence", "rights_reference": "Owner"},
    )
    assert response.status_code == 422


def test_real_pptx_export_contains_exact_evidence_notes_and_provenance(client: TestClient) -> None:
    source, draft = create_draft(client)
    path = f"/v1/presentations/{draft['id']}/pptx"
    assert client.get(path).status_code == 409
    approve(client, draft)
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["x-artifact-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-deck-sha256"] == draft["deck_hash"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        assert package.testzip() is None
        slide = ElementTree.fromstring(package.read("ppt/slides/slide1.xml"))
        text = " ".join(slide.itertext())
        assert source["content"] in text
        assert source["content_hash"] in text
        assert source["id"] in text
        notes = ElementTree.fromstring(package.read("ppt/notesSlides/notesSlide1.xml"))
        assert source["content"] in " ".join(notes.itertext())
    assert client.get(f"/v1/presentations/{draft['id']}").json()["state"] == "approved"
    assert client.get("/v1/audit").json()[-1]["action"] == "pptx_exported"
    client.post(f"/v1/sources/{source['id']}/withdraw")
    assert client.get(path).status_code == 409


def test_withdrawal_during_render_blocks_download(client: TestClient, monkeypatch) -> None:
    source, draft = create_draft(client)
    approve(client, draft)
    original = PowerPointRenderer.render

    def withdraw_then_render(renderer: PowerPointRenderer, deck: DeckSpec) -> bytes:
        client.post(f"/v1/sources/{source['id']}/withdraw")
        return original(renderer, deck)

    monkeypatch.setattr(PowerPointRenderer, "render", withdraw_then_render)
    response = client.get(f"/v1/presentations/{draft['id']}/pptx")
    assert response.status_code == 409
    assert response.json()["code"] == "stale_evidence"


def test_missing_renderer_is_explicit(settings: Settings) -> None:
    missing = Settings(
        token=settings.token, database=settings.database, renderer=Path("/not-built.js")
    )
    with TestClient(
        create_app(missing), headers={"Authorization": f"Bearer {settings.token}"}
    ) as client:
        _, draft = create_draft(client)
        approve(client, draft)
        response = client.get(f"/v1/presentations/{draft['id']}/pptx")
        assert response.status_code == 503
        assert response.json()["code"] == "renderer_not_built"


def test_openai_not_silently_substituted(client: TestClient) -> None:
    source, _ = create_draft(client)
    response = client.post(
        "/v1/presentations",
        headers={"Idempotency-Key": "paid-model-key"},
        json={"title": "Title", "source_ids": [source["id"]], "generator": "openai"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "provider_not_configured"


def test_configuration_refuses_weak_tokens(tmp_path: Path) -> None:
    for token in ["", "short", " " * 40, "\u00e9" * 40, "\x00" * 40, "\x7f" * 40]:
        with pytest.raises(ValueError, match="PRESENTATION_API_TOKEN"):
            Settings(token=token, database=tmp_path / "unused.sqlite3")


def test_schema_and_generated_types_are_current() -> None:
    expected = json.dumps(DeckSpec.model_json_schema(), indent=2, sort_keys=True) + "\n"
    assert (ROOT / "contracts/deck.schema.json").read_text() == expected


def test_multiline_source_xml_escaping_and_notes(client: TestClient) -> None:
    source = client.post(
        "/v1/sources",
        headers={"Idempotency-Key": "multiline-source"},
        json={
            "title": "Literal <XML> & text",
            "content": 'First line <tag> & "quote".\n\nSecond line.\n' * 3,
            "rights_reference": "Synthetic author",
        },
    ).json()
    client.post(
        f"/v1/sources/{source['id']}/approve",
        json={"expected_hash": source["content_hash"], "reviewed": True},
    ).raise_for_status()
    draft = client.post(
        "/v1/presentations",
        headers={"Idempotency-Key": "multiline-presentation"},
        json={"title": "Safe text", "source_ids": [source["id"]], "slide_count": 1},
    ).json()
    approve(client, draft)
    response = client.get(f"/v1/presentations/{draft['id']}/pptx")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        for name in package.namelist():
            if name.endswith(".xml"):
                ElementTree.fromstring(package.read(name))
        notes = ElementTree.fromstring(package.read("ppt/notesSlides/notesSlide1.xml"))
        assert "<tag>" in " ".join(notes.itertext())
        assert "Second line." in " ".join(notes.itertext())


def test_renderer_rejects_malformed_input() -> None:
    result = subprocess.run(
        ["node", str(ROOT / "workers/render/dist/render.js")],
        input=b'{"title": "Bad", "slides": []}',
        capture_output=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert result.stdout == b""


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (subprocess.CompletedProcess([], 1, b"", b"private details"), "render_failed"),
        (subprocess.CompletedProcess([], 0, b"not a zip", b""), "invalid_artifact"),
    ],
)
def test_renderer_failures_do_not_return_success(
    client: TestClient, monkeypatch, outcome, expected
) -> None:
    _, draft = create_draft(client)
    approve(client, draft)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: outcome)
    response = client.get(f"/v1/presentations/{draft['id']}/pptx")
    assert response.status_code == 502
    assert response.json()["code"] == expected
    assert "private details" not in response.text


def test_unexpected_error_is_redacted(client: TestClient, monkeypatch) -> None:
    def fail() -> list:
        raise RuntimeError("private source content")

    monkeypatch.setattr(client.app.state.service.store, "events", fail)
    with TestClient(client.app, raise_server_exceptions=False, headers=client.headers) as alternate:
        response = alternate.get("/v1/audit")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "private source content" not in response.text
