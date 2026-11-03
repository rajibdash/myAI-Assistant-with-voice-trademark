"""Exercise the local API using synthetic data, with an explicit human review pause."""

import argparse
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path(".local-data/demo.pptx"))
    args = parser.parse_args()
    token = os.environ.get("PRESENTATION_API_TOKEN")
    if not token:
        raise SystemExit("Set PRESENTATION_API_TOKEN to the same token used by the local server")
    if args.output.exists():
        raise SystemExit("Output already exists; choose a different --output path")
    with httpx.Client(
        base_url=args.url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
        follow_redirects=False,
    ) as client:
        source_response = client.post(
            "/v1/sources",
            headers={"Idempotency-Key": uuid4().hex},
            json={
                "title": "Synthetic project facts",
                "content": (
                    "This fictional project has a demonstration budget of 42 units. "
                    "The demonstration team has three fictional members. "
                    "These are synthetic facts, not claims about a real organization."
                ),
                "rights_reference": "Original synthetic demonstration text in examples/demo.py",
            },
        )
        source_response.raise_for_status()
        source = source_response.json()
        print(f"Review this source and its rights before approval:\n{source['content']}")
        if input("Type approve-source to continue: ").strip() != "approve-source":
            raise SystemExit("Source remains pending; no draft generated")
        response = client.post(
            f"/v1/sources/{source['id']}/approve",
            json={"expected_hash": source["content_hash"], "reviewed": True},
        )
        response.raise_for_status()
        response = client.post(
            "/v1/presentations",
            headers={"Idempotency-Key": uuid4().hex},
            json={
                "title": "Reviewed source demonstration",
                "source_ids": [source["id"]],
                "slide_count": 1,
                "generator": "extractive",
            },
        )
        response.raise_for_status()
        draft = response.json()
        for slide in draft["deck"]["slides"]:
            citation = slide["citation"]
            print(f"\n{slide['title']}\n{citation['quote']}")
            print(f"Source {citation['source_id']}, chars {citation['start']}-{citation['end']}")
        print(f"\nExact deck hash: {draft['deck_hash']}")
        if input("After review, type approve-deck to export: ").strip() != "approve-deck":
            raise SystemExit("Draft remains unapproved; no PowerPoint exported")
        response = client.post(
            f"/v1/presentations/{draft['id']}/approve",
            json={"expected_hash": draft["deck_hash"], "reviewed": True},
        )
        response.raise_for_status()
        response = client.get(f"/v1/presentations/{draft['id']}/pptx")
        response.raise_for_status()
        artifact_hash = hashlib.sha256(response.content).hexdigest()
        if artifact_hash != response.headers.get("X-Artifact-SHA256"):
            raise SystemExit("Artifact hash mismatch; refusing to save")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as destination:
            destination.write(response.content)
        print(f"Saved {args.output} (SHA256 {artifact_hash})")


if __name__ == "__main__":
    main()
