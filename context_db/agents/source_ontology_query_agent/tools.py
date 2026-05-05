from __future__ import annotations

from pathlib import Path

import yaml
from langchain_core.tools import tool

from .schemas import AvailableSourceOntology, SourceOntologyDocument


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_workspace_dir(workspace_dir: str | Path | None = None) -> Path:
    if workspace_dir is None:
        return get_repo_root() / "workspace"
    return Path(workspace_dir).resolve()


def _extract_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    in_metadata = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "## Metadata":
            in_metadata = True
            continue
        if in_metadata and line.startswith("## "):
            break
        if in_metadata and line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            metadata[key.strip()] = value.strip()

    return metadata


def _number_lines(text: str) -> str:
    return "\n".join(f"{index + 1}: {line}" for index, line in enumerate(text.splitlines()))


def list_available_source_ontologies(workspace_dir: str | Path | None = None) -> list[AvailableSourceOntology]:
    workspace_path = get_workspace_dir(workspace_dir)
    sources: list[AvailableSourceOntology] = []

    if not workspace_path.exists():
        return sources

    for ontology_path in sorted(workspace_path.glob("*/ontology.md")):
        source_dir = ontology_path.parent
        ontology_text = ontology_path.read_text(encoding="utf-8")
        metadata = _extract_metadata(ontology_text)
        sources.append(
            AvailableSourceOntology(
                source_name=metadata.get("source_name", source_dir.name),
                source_type=metadata.get("source_type"),
                status=metadata.get("status"),
                ontology_path=str(ontology_path.resolve()),
            )
        )

    return sources


def load_source_ontology(source_name: str, workspace_dir: str | Path | None = None) -> SourceOntologyDocument:
    for source in list_available_source_ontologies(workspace_dir):
        if source.source_name == source_name:
            ontology_text = Path(source.ontology_path).read_text(encoding="utf-8")
            return SourceOntologyDocument(
                source=source,
                ontology_text=ontology_text,
                numbered_ontology_text=_number_lines(ontology_text),
                total_lines=len(ontology_text.splitlines()),
            )

    raise ValueError(f"Unknown source-level ontology: {source_name}")


@tool("list_available_source_ontologies")
def list_available_source_ontologies_tool() -> str:
    """List source-level ontologies that can be queried."""
    payload = [source.model_dump() for source in list_available_source_ontologies()]
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


@tool("read_selected_source_ontology")
def read_selected_source_ontology_tool(source_name: str) -> str:
    """Read one source-level ontology by source name."""
    document = load_source_ontology(source_name)
    payload = {
        "source": document.source.model_dump(),
        "total_lines": document.total_lines,
        "numbered_ontology_text": document.numbered_ontology_text,
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
