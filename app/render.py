import io
import subprocess
import zipfile
from pathlib import Path

from app.domain import DeckSpec, Problem


class PowerPointRenderer:
    def __init__(self, worker: Path):
        self.worker = worker.resolve()

    def render(self, deck: DeckSpec) -> bytes:
        if not self.worker.is_file():
            raise Problem(
                503, "renderer_not_built", "Run npm ci and npm run build in workers/render first"
            )
        try:
            result = subprocess.run(
                ["node", str(self.worker)],
                input=deck.model_dump_json().encode(),
                capture_output=True,
                timeout=30,
                check=False,
                cwd=self.worker.parent,
            )
        except FileNotFoundError as error:
            raise Problem(503, "node_unavailable", "Node.js is required for PPTX export") from error
        except subprocess.TimeoutExpired as error:
            raise Problem(
                504, "render_timeout", "PowerPoint rendering exceeded 30 seconds"
            ) from error
        if result.returncode:
            raise Problem(
                502, "render_failed", "PowerPoint renderer failed; no artifact was delivered"
            )
        try:
            with zipfile.ZipFile(io.BytesIO(result.stdout)) as package:
                if package.testzip() is not None or "[Content_Types].xml" not in package.namelist():
                    raise ValueError("Invalid package")
                slides = [
                    name
                    for name in package.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ]
                if len(slides) != len(deck.slides):
                    raise ValueError("Slide count mismatch")
        except (zipfile.BadZipFile, ValueError) as error:
            raise Problem(
                502, "invalid_artifact", "Renderer produced an invalid PowerPoint"
            ) from error
        return result.stdout
