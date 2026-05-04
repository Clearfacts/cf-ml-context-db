from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import streamlit as st

from context_db.agents.clearfacts_navigation_deepagent import ClearfactsNavigationDeepAgent
from context_db.agents.clearfacts_navigation_deepagent.schemas import ClearfactsNavigationDeepAgentRequest
from context_db.agents.clearfacts_navigation_agent.tools import (
    PersistentPlaywrightBrowserSession,
    SOURCES_DIR,
    ensure_navigation_run,
    load_manifest,
    load_navigation_run,
    load_navigation_source,
    prepare_playwright_run_config,
    read_recent_navigation_events,
)
from context_db.agents.source_ontology_query_agent import SourceOntologyQueryAgent
from context_db.agents.source_ontology_query_agent.schemas import SourceOntologyQueryInput
from context_db.agents.source_ontology_query_agent.tools import list_available_source_ontologies


DEFAULT_SOURCE_NAME = "navigation_agent_clearfacts"
DEFAULT_MAX_ITERATIONS = 6


@st.cache_resource
def get_navigation_deepagent() -> ClearfactsNavigationDeepAgent:
    return ClearfactsNavigationDeepAgent()


@st.cache_resource
def get_ontology_query_agent() -> SourceOntologyQueryAgent:
    return SourceOntologyQueryAgent()


def list_navigation_sources() -> list:
    sources = []
    for source_path in sorted(SOURCES_DIR.glob("navigation_agent*.yaml")):
        try:
            sources.append(load_navigation_source(source_path))
        except Exception:
            continue
    return sources


def _format_navigation_source_label(source) -> str:
    parts = [source.source_name, source.source_type]
    if source.default_role:
        parts.append(f"default role: {source.default_role}")
    return " | ".join(parts)


def _format_ontology_source_label(source) -> str:
    parts = [source.source_name]
    if source.source_type:
        parts.append(source.source_type)
    if source.status:
        parts.append(source.status)
    return " | ".join(parts)


def init_session_state() -> None:
    defaults = {
        "nav_selected_source": DEFAULT_SOURCE_NAME,
        "nav_previous_source": None,
        "nav_role_selection": "__default__",
        "nav_resume_run_timestamp_input": "",
        "nav_active_run_timestamp": None,
        "nav_history": [],
        "nav_last_result": None,
        "nav_last_error": None,
        "nav_max_iterations": DEFAULT_MAX_ITERATIONS,
        "nav_include_snapshot": True,
        "nav_browser_session": None,
        "nav_browser_session_key": None,
        "ontology_selected_source": None,
        "ontology_previous_source": None,
        "ontology_question_input": "",
        "ontology_last_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_navigation_session() -> None:
    close_navigation_browser_session()
    for key in [
        "nav_active_run_timestamp",
        "nav_history",
        "nav_last_result",
        "nav_last_error",
    ]:
        if key == "nav_history":
            st.session_state[key] = []
        else:
            st.session_state[key] = None


def close_navigation_browser_session() -> None:
    browser_session = st.session_state.get("nav_browser_session")
    if browser_session is not None:
        try:
            browser_session.stop()
        except Exception:
            pass
    st.session_state["nav_browser_session"] = None
    st.session_state["nav_browser_session_key"] = None


def ensure_active_navigation_run(selected_source) -> Any:
    requested_timestamp = (
        st.session_state.get("nav_active_run_timestamp")
        or st.session_state.get("nav_resume_run_timestamp_input", "").strip()
        or None
    )
    run = ensure_navigation_run(selected_source.source_name, timestamp=requested_timestamp)
    st.session_state["nav_active_run_timestamp"] = run.timestamp
    return run


def ensure_navigation_browser_session(selected_source, run) -> PersistentPlaywrightBrowserSession:
    desired_key = f"{selected_source.source_name}:{run.timestamp}"
    browser_session = st.session_state.get("nav_browser_session")
    session_key = st.session_state.get("nav_browser_session_key")

    if browser_session is not None and session_key != desired_key:
        close_navigation_browser_session()
        browser_session = None

    if browser_session is None or not browser_session.is_active():
        browser_session = PersistentPlaywrightBrowserSession(prepare_playwright_run_config(selected_source, run))
        browser_session.start()
        st.session_state["nav_browser_session"] = browser_session
        st.session_state["nav_browser_session_key"] = desired_key

    return browser_session


def sync_navigation_selection(selected_source) -> None:
    previous_source = st.session_state.get("nav_previous_source")
    current_source = st.session_state.get("nav_selected_source")
    if previous_source is not None and previous_source != current_source:
        reset_navigation_session()
        st.session_state["nav_role_selection"] = (
            selected_source.default_role if selected_source.default_role else "__default__"
        )
    elif (
        st.session_state.get("nav_role_selection") not in {"__default__", *selected_source.available_roles}
    ):
        st.session_state["nav_role_selection"] = (
            selected_source.default_role if selected_source.default_role else "__default__"
        )
    st.session_state["nav_previous_source"] = current_source


def sync_ontology_source_change() -> None:
    selected_source = st.session_state.get("ontology_selected_source")
    previous_source = st.session_state.get("ontology_previous_source")
    if previous_source is not None and previous_source != selected_source:
        st.session_state["ontology_last_result"] = None
        st.session_state["ontology_question_input"] = ""
    st.session_state["ontology_previous_source"] = selected_source


def get_latest_navigation_payload(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("latest_navigation_result") or {}


def get_result_current_page(result: dict[str, Any]) -> dict[str, Any]:
    current_page = result.get("current_page") or {}
    if current_page:
        return current_page
    latest_navigation = get_latest_navigation_payload(result)
    return latest_navigation.get("current_page") or {}


def summarize_result(result: dict[str, Any]) -> str:
    lines = [
        f"**Status:** `{result['status']}`",
        f"**Run:** `{result['run_timestamp']}`",
        f"**Role:** `{result.get('role') or '_default_'}`",
        f"**Message:** {result.get('message') or '_none_'}",
    ]
    if result.get("question_for_user"):
        lines.append(f"**Question:** {result['question_for_user']}")
    trace_references = result.get("trace_references") or []
    if trace_references:
        lines.append(f"**Trace artifacts:** {len(trace_references)}")
    current_page = get_result_current_page(result)
    if current_page.get("url"):
        lines.append(f"**Current URL:** {current_page['url']}")
    if current_page.get("title"):
        lines.append(f"**Current title:** {current_page['title']}")
    return "\n\n".join(lines)


def render_navigation_result(result: dict[str, Any]) -> None:
    st.markdown(summarize_result(result))

    current_page = get_result_current_page(result)
    text_excerpt = current_page.get("text_excerpt")
    page_summary = current_page.get("page_summary")
    snapshot = current_page.get("snapshot")
    latest_navigation = get_latest_navigation_payload(result)
    events = latest_navigation.get("events") or []
    trace_references = result.get("trace_references") or []

    if page_summary or text_excerpt or snapshot:
        with st.expander("Latest page evidence", expanded=False):
            if page_summary:
                st.markdown(page_summary)
            if text_excerpt:
                st.markdown("**Visible text excerpt**")
                st.code(text_excerpt[:8000], language="text")
            if snapshot:
                st.markdown("**Snapshot excerpt**")
                st.code(snapshot[:8000], language="markdown")

    if events:
        with st.expander("Recent events", expanded=False):
            for event in events[-8:]:
                headline = f"- `{event['phase']}` / `{event['status']}`"
                if event.get("tool_name"):
                    headline += f" via `{event['tool_name']}`"
                st.markdown(headline)
                if event.get("message"):
                    st.code(event["message"][:4000], language="text")

    if trace_references:
        with st.expander("DeepAgents traces", expanded=False):
            for reference in trace_references[-12:]:
                st.markdown(
                    f"- `{reference.get('agent_name', 'unknown')}` / "
                    f"`{reference.get('trace_kind', 'trace')}`"
                )
                if reference.get("path"):
                    st.code(reference["path"], language="text")


def render_navigation_sidebar(selected_source, effective_role: str | None) -> None:
    st.sidebar.subheader("Current run")
    active_run_timestamp = st.session_state.get("nav_active_run_timestamp")
    resume_timestamp = st.session_state.get("nav_resume_run_timestamp_input", "").strip()
    candidate_timestamp = active_run_timestamp or resume_timestamp

    st.sidebar.markdown(f"**Source:** `{selected_source.source_name}`")
    st.sidebar.markdown(f"**Role:** `{effective_role or selected_source.default_role or 'none'}`")
    st.sidebar.markdown("**Coordinator:** `DeepAgents`")
    st.sidebar.markdown("**Browser:** `chrome` via Playwright MCP")
    st.sidebar.markdown(
        f"**Headless:** `{'yes' if selected_source.playwright.headless else 'no'}`"
    )
    browser_session = st.session_state.get("nav_browser_session")
    browser_session_key = st.session_state.get("nav_browser_session_key")
    expected_key = (
        f"{selected_source.source_name}:{candidate_timestamp}" if candidate_timestamp else None
    )
    browser_status = "active" if (
        browser_session is not None
        and browser_session.is_active()
        and browser_session_key == expected_key
    ) else "closed"
    st.sidebar.markdown(f"**Live browser session:** `{browser_status}`")

    if not candidate_timestamp:
        st.sidebar.info("No active run yet. Send a message to create a run.")
        return

    try:
        run = load_navigation_run(selected_source.source_name, timestamp=candidate_timestamp)
        manifest = load_manifest(run.manifest_path)
        events = read_recent_navigation_events(run, limit=8)
    except Exception as exc:
        st.sidebar.warning(f"Could not load run `{candidate_timestamp}`: {exc}")
        return

    st.sidebar.markdown(f"**Run timestamp:** `{run.timestamp}`")
    st.sidebar.markdown(f"**Run folder:** `{run.run_dir}`")
    st.sidebar.markdown(f"**Status:** `{manifest.get('status', 'unknown')}`")

    last_result = st.session_state.get("nav_last_result") or {}
    if last_result.get("question_for_user"):
        st.sidebar.markdown(f"**Question for user:** {last_result['question_for_user']}")
    trace_references = last_result.get("trace_references") or []
    if trace_references:
        st.sidebar.markdown(f"**Trace artifacts:** `{len(trace_references)}`")

    last_url = manifest.get("last_observed_url")
    last_title = manifest.get("last_observed_title")
    if last_url:
        st.sidebar.markdown(f"**Latest URL:** `{last_url}`")
    if last_title:
        st.sidebar.markdown(f"**Latest title:** `{last_title}`")

    with st.sidebar.expander("Recent events", expanded=False):
        if not events:
            st.write("No events recorded yet.")
        else:
            for event in events:
                st.markdown(f"- `{event.phase}` / `{event.status}`")
                if event.message:
                    st.caption(event.message[:300])


def render_navigation_tab() -> None:
    st.title("Clearfacts exploration app")
    st.caption(
        "Guide the DeepAgents navigation coordinator in natural language. "
        "It will orchestrate the Clearfacts navigation runtime while Playwright MCP keeps a shared Chrome session open."
    )

    sources = list_navigation_sources()
    if not sources:
        st.warning("No navigation source YAML files were found under agents/sources/navigation_agent*.yaml.")
        return

    source_lookup = {source.source_name: source for source in sources}
    source_names = list(source_lookup)

    default_source = st.session_state.get("nav_selected_source", source_names[0])
    if default_source not in source_lookup:
        default_source = source_names[0]
        st.session_state["nav_selected_source"] = default_source

    st.sidebar.header("Exploration controls")
    st.sidebar.selectbox(
        "Navigation source",
        options=source_names,
        index=source_names.index(default_source),
        format_func=lambda source_name: _format_navigation_source_label(source_lookup[source_name]),
        key="nav_selected_source",
    )

    selected_source = source_lookup[st.session_state["nav_selected_source"]]
    sync_navigation_selection(selected_source)

    role_options = ["__default__"] + selected_source.available_roles
    current_role = st.session_state.get("nav_role_selection", "__default__")
    if current_role not in role_options:
        current_role = "__default__"
        st.session_state["nav_role_selection"] = current_role

    st.sidebar.selectbox(
        "Role",
        options=role_options,
        format_func=lambda value: (
            f"Use source default ({selected_source.default_role})" if value == "__default__" else value
        ),
        index=role_options.index(current_role),
        key="nav_role_selection",
    )
    effective_role = None if st.session_state["nav_role_selection"] == "__default__" else st.session_state["nav_role_selection"]

    st.sidebar.number_input(
        "Max execution iterations",
        min_value=1,
        max_value=20,
        step=1,
        key="nav_max_iterations",
    )
    st.sidebar.checkbox(
        "Capture snapshots",
        key="nav_include_snapshot",
        help="Persist page snapshots and text excerpts into the active run folder.",
    )
    st.sidebar.text_input(
        "Run timestamp to resume",
        key="nav_resume_run_timestamp_input",
        help="Optionally resume an existing run by timestamp.",
    )

    resume_col, new_run_col, close_col = st.sidebar.columns(3)
    with resume_col:
        if st.button("Resume run", use_container_width=True):
            resume_timestamp = st.session_state.get("nav_resume_run_timestamp_input", "").strip()
            if not resume_timestamp:
                st.sidebar.warning("Enter a run timestamp first.")
            else:
                try:
                    load_navigation_run(selected_source.source_name, timestamp=resume_timestamp)
                except Exception as exc:
                    st.sidebar.error(f"Could not resume run `{resume_timestamp}`: {exc}")
                else:
                    close_navigation_browser_session()
                    st.session_state["nav_active_run_timestamp"] = resume_timestamp
                    st.session_state["nav_history"] = []
                    st.session_state["nav_last_result"] = None
                    st.session_state["nav_last_error"] = None
                    st.rerun()
    with new_run_col:
        if st.button("Start new", use_container_width=True):
            reset_navigation_session()
            st.rerun()
    with close_col:
        if st.button("Close browser", use_container_width=True):
            close_navigation_browser_session()
            st.rerun()

    render_navigation_sidebar(selected_source, effective_role)

    if st.session_state.get("nav_last_error"):
        st.error(st.session_state["nav_last_error"])

    for entry in st.session_state.get("nav_history", []):
        with st.chat_message(entry["role"]):
            if entry["role"] == "user":
                st.markdown(entry["content"])
            else:
                render_navigation_result(entry["result"])

    prompt = st.chat_input("What would you like the agent to explore?")
    if not prompt:
        return

    st.session_state["nav_history"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        with st.chat_message("assistant"):
            with st.spinner("Exploring with the DeepAgents coordinator..."):
                run = ensure_active_navigation_run(selected_source)
                browser_session = ensure_navigation_browser_session(selected_source, run)
                request = ClearfactsNavigationDeepAgentRequest(
                    source_name=selected_source.source_name,
                    instruction=prompt,
                    role=effective_role,
                    run_timestamp=run.timestamp,
                    execution_max_iterations=int(st.session_state["nav_max_iterations"]),
                    include_snapshot=bool(st.session_state["nav_include_snapshot"]),
                )
                result = get_navigation_deepagent().invoke(request, browser=browser_session)
                result_payload = result.model_dump(mode="json")
                render_navigation_result(result_payload)
    except Exception as exc:
        st.session_state["nav_last_error"] = str(exc)
        with st.chat_message("assistant"):
            st.error(str(exc))
        return

    st.session_state["nav_last_error"] = None
    st.session_state["nav_last_result"] = result_payload
    st.session_state["nav_active_run_timestamp"] = result_payload["run_timestamp"]
    st.session_state["nav_history"].append({"role": "assistant", "result": result_payload})
    st.rerun()


def render_ontology_query_tab() -> None:
    st.title("Source ontology query")
    st.caption("Ask a question about one finalized source ontology at a time.")

    sources = list_available_source_ontologies()
    if not sources:
        st.warning("No finalized source ontologies were found under workspace/*/ontology.md.")
        return

    source_lookup = {source.source_name: source for source in sources}
    source_names = list(source_lookup)

    default_source = st.session_state.get("ontology_selected_source", source_names[0])
    if default_source not in source_lookup:
        default_source = source_names[0]
        st.session_state["ontology_selected_source"] = default_source

    st.selectbox(
        "Source",
        options=source_names,
        index=source_names.index(default_source),
        format_func=lambda source_name: _format_ontology_source_label(source_lookup[source_name]),
        key="ontology_selected_source",
    )
    sync_ontology_source_change()

    with st.form("source_ontology_query_form"):
        st.text_area(
            "Question",
            key="ontology_question_input",
            height=140,
            placeholder="What does this source ontology say about ...?",
        )
        submitted = st.form_submit_button("Ask")

    if submitted:
        question = st.session_state["ontology_question_input"].strip()
        if not question:
            st.warning("Enter a question before submitting.")
        else:
            with st.spinner("Querying selected source ontology..."):
                st.session_state["ontology_last_result"] = get_ontology_query_agent().invoke(
                    SourceOntologyQueryInput(
                        source_name=st.session_state["ontology_selected_source"],
                        question=question,
                    )
                )

    result = st.session_state.get("ontology_last_result")
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


def main() -> None:
    st.set_page_config(page_title="Clearfacts exploration", layout="wide")
    init_session_state()

    explore_tab, ontology_tab = st.tabs(["Explore app", "Ontology query"])
    with explore_tab:
        render_navigation_tab()
    with ontology_tab:
        render_ontology_query_tab()


if __name__ == "__main__":
    main()
