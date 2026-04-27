from __future__ import annotations

import logging

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from cf_ml_common.llm.token_tracker import tracking_context
from context_db.llm.config import get_azure_llm, init_token_tracking

from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .schemas import OntologyCitation, SourceOntologyQueryInput, SourceOntologyQueryOutput
from .tools import list_available_source_ontologies, load_source_ontology

logger = logging.getLogger(__name__)


class _StructuredOntologyCitation(BaseModel):
    line_start: int = Field(description="1-based inclusive start line in the ontology.")
    line_end: int = Field(description="1-based inclusive end line in the ontology.")


class _StructuredOntologyAnswer(BaseModel):
    answer_markdown: str = Field(description="Markdown answer grounded only in the selected ontology.")
    insufficient_context: bool = Field(
        default=False,
        description="Whether the ontology lacks enough evidence to fully answer the question.",
    )
    citations: list[_StructuredOntologyCitation] = Field(
        default_factory=list,
        description="Evidence citations using ontology line ranges only.",
    )


class SourceOntologyQueryAgent:
    AGENT_NAME = "source-ontology-query-agent"
    AGENT_OPERATION = "answer-source-ontology-question"

    def __init__(
        self,
        model_name: str = "gpt-5-2025-08-07",
        max_tokens: int = 4000,
    ) -> None:
        init_token_tracking()
        llm = get_azure_llm(model_name=model_name, max_tokens=max_tokens)
        self._llm = llm.with_structured_output(_StructuredOntologyAnswer)

    def list_available_sources(self):
        return list_available_source_ontologies()

    def invoke(self, query: SourceOntologyQueryInput) -> SourceOntologyQueryOutput:
        question = query.question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        document = load_source_ontology(query.source_name)
        source_metadata_yaml = yaml.safe_dump(
            document.source.model_dump(),
            sort_keys=False,
            allow_unicode=False,
        )
        prompt = USER_PROMPT_TEMPLATE.format(
            source_metadata_yaml=source_metadata_yaml,
            question=question,
            numbered_ontology_text=document.numbered_ontology_text,
        )

        logger.info(
            "Answering ontology question for source '%s' using %s",
            document.source.source_name,
            document.source.ontology_path,
        )
        logger.debug("Ontology query system prompt:\n%s", SYSTEM_PROMPT)
        logger.debug("Ontology query user prompt:\n%s", prompt)

        with tracking_context(agent_name=self.AGENT_NAME, operation=self.AGENT_OPERATION):
            response = self._llm.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ]
            )

        logger.debug("Ontology query structured response: %s", response.model_dump())
        citations = self._build_citations(document.ontology_text, response.citations)
        return SourceOntologyQueryOutput(
            source_name=document.source.source_name,
            ontology_path=document.source.ontology_path,
            answer_markdown=response.answer_markdown,
            citations=citations,
            insufficient_context=response.insufficient_context,
        )

    @staticmethod
    def _build_citations(
        ontology_text: str,
        citations: list[_StructuredOntologyCitation],
    ) -> list[OntologyCitation]:
        lines = ontology_text.splitlines()
        normalized: list[OntologyCitation] = []

        for citation in citations:
            start = max(1, citation.line_start)
            end = min(len(lines), citation.line_end)
            if end < start:
                continue

            snippet = "\n".join(lines[start - 1 : end]).strip()
            if not snippet:
                continue

            normalized.append(
                OntologyCitation(
                    line_start=start,
                    line_end=end,
                    snippet=snippet,
                )
            )

        return normalized
