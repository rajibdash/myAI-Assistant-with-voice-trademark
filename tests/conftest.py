from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import Settings, create_app
from app.providers import ExtractiveGenerator
from app.service import Service
from app.store import Store

TOKEN = "local-testing-only-" + "x" * 32


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(token=TOKEN, database=tmp_path / "assistant.sqlite3")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client


@pytest.fixture
def service(tmp_path: Path) -> Service:
    return Service(Store(tmp_path / "state.sqlite3"), {"extractive": ExtractiveGenerator()})
