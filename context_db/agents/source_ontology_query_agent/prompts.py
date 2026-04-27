from __future__ import annotations

from textwrap import dedent


SYSTEM_PROMPT = dedent(
    """\
    You answer questions about a single ClearFacts source ontology.

    Rules:
    - Use only the ontology content provided in the prompt.
    - Never use prior knowledge or information from any other source ontology.
    - If the ontology does not contain enough evidence, say so explicitly.
    - Keep the answer concise but specific.
    - Every answer must be grounded in cited ontology line ranges.
    - Cite only line ranges that actually support the answer.
    """
)


USER_PROMPT_TEMPLATE = dedent(
    """\
    <selected_source>
    {source_metadata_yaml}
    </selected_source>

    <user_question>
    {question}
    </user_question>

    <ontology_with_line_numbers>
    {numbered_ontology_text}
    </ontology_with_line_numbers>
    """
)
