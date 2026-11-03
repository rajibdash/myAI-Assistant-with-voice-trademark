import json
from pathlib import Path

from app.domain import DeckSpec


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "contracts/deck.schema.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(DeckSpec.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
