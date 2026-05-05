from __future__ import annotations

from pydantic import BaseModel, Field


class AvailableSourceOntology(BaseModel):
    source_name: str = Field(description="Stable source identifier used in the workspace folder name.")
    source_type: str | None = Field(default=None, description="Source type from ontology metadata if available.")
    status: str | None = Field(default=None, description="Ontology processing status from ontology metadata if available.")
    ontology_path: str = Field(description="Absolute path to the source-level ontology.md file.")


class SourceOntologyDocument(BaseModel):
    source: AvailableSourceOntology
    ontology_text: str = Field(description="Raw ontology markdown content.")
    numbered_ontology_text: str = Field(description="Ontology markdown content prefixed with line numbers.")
    total_lines: int = Field(description="Total line count of the ontology document.")


class SourceOntologyQueryInput(BaseModel):
    source_name: str = Field(description="Selected source identifier.")
    question: str = Field(description="User question about the selected source ontology.")


class OntologyCitation(BaseModel):
    line_start: int = Field(description="1-based inclusive start line in the ontology file.")
    line_end: int = Field(description="1-based inclusive end line in the ontology file.")
    snippet: str = Field(description="Snippet copied from the cited ontology lines.")


class SourceOntologyQueryOutput(BaseModel):
    source_name: str = Field(description="Selected source identifier used to answer the question.")
    ontology_path: str = Field(description="Absolute path to the ontology used to answer.")
    answer_markdown: str = Field(description="Final markdown answer grounded in the selected ontology.")
    citations: list[OntologyCitation] = Field(default_factory=list, description="Evidence citations from the ontology.")
    insufficient_context: bool = Field(
        default=False,
        description="Whether the ontology did not contain enough evidence to fully answer the question.",
    )
