from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import streamlit as st

from context_db.agents.source_ontology_query_agent import SourceOntologyQueryAgent
from context_db.agents.source_ontology_query_agent.schemas import SourceOntologyQueryInput
from context_db.agents.source_ontology_query_agent.tools import list_available_source_ontologies



@st.cache_resource
def get_agent() -> SourceOntologyQueryAgent:
    return SourceOntologyQueryAgent()


def _format_source_label(source) -> str:
    parts = [source.source_name]
    if source.source_type:
        parts.append(source.source_type)
    if source.status:
        parts.append(source.status)
    return " | ".join(parts)


def _reset_result_on_source_change() -> None:
    selected_source = st.session_state.get("selected_source")
    previous_source = st.session_state.get("previous_source")
    if previous_source is not None and previous_source != selected_source:
        st.session_state["last_result"] = None
        st.session_state["question_input"] = ""
    st.session_state["previous_source"] = selected_source


def main() -> None:
    st.set_page_config(page_title="Source Ontology Query", layout="wide")
    st.title("Source ontology query")
    st.caption("Ask a question about one finalized source ontology at a time.")

    sources = list_available_source_ontologies()

    if not sources:
        st.warning("No finalized source ontologies were found under workspace/*/ontology.md.")
        return

    source_lookup = {source.source_name: source for source in sources}
    source_names = list(source_lookup)

    default_source = st.session_state.get("selected_source", source_names[0])
    if default_source not in source_lookup:
        default_source = source_names[0]

    st.selectbox(
        "Source",
        options=source_names,
        index=source_names.index(default_source),
        format_func=lambda source_name: _format_source_label(source_lookup[source_name]),
        key="selected_source",
    )
    _reset_result_on_source_change()

    with st.form("source_ontology_query_form"):
        st.text_area(
            "Question",
            key="question_input",
            height=140,
            placeholder="What does this source ontology say about ...?",
        )
        submitted = st.form_submit_button("Ask")

    if submitted:
        question = st.session_state["question_input"].strip()
        if not question:
            st.warning("Enter a question before submitting.")
        else:
            with st.spinner("Querying selected source ontology..."):
                agent = get_agent()
                st.session_state["last_result"] = agent.invoke(
                    SourceOntologyQueryInput(
                        source_name=st.session_state["selected_source"],
                        question=question,
                    )
                )

    result = st.session_state.get("last_result")
    if result is None:
        return

    st.subheader("Answer")
    st.markdown(result.answer_markdown)
    st.caption(f"Source: {result.source_name}")

    if result.insufficient_context:
        st.info("The selected ontology did not contain enough evidence to answer fully.")

    st.subheader("Citations")
    if not result.citations:
        st.write("No citations returned.")
    else:
        for index, citation in enumerate(result.citations, start=1):
            with st.expander(f"Citation {index}: lines {citation.line_start}-{citation.line_end}", expanded=False):
                st.code(citation.snippet, language="markdown")


if __name__ == "__main__":
    main()
