from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_db.agents.clearfacts_navigation_agent.agents import ClearfactsNavigationAgent
from context_db.agents.clearfacts_navigation_agent.schemas import CredentialField, ExplorationAction, ExplorationActionType
from context_db.agents.clearfacts_navigation_agent.schemas import (
    NavigationActionObservation,
    NavigationPageAffordance,
    NavigationLabelObservation,
    NavigationOntologyDelta,
    NavigationPageEvidence,
    NavigationPathObservation,
    NavigationScreenObservation,
    NavigationValidationNote,
    PlaywrightMcpServerConfig,
)
from context_db.agents.clearfacts_navigation_agent.tools import (
    ExecutedToolCall,
    PlaywrightMcpBrowser,
    PlaywrightToolExecutionError,
    _run_async_blocking,
    build_human_readable_page_summary,
    build_playwright_mcp_args,
    extract_json_payload_from_tool_message,
    finalize_navigation_run,
    load_navigation_ontology,
    load_navigation_source,
    merge_navigation_ontology,
    remap_snapshot_ref_target,
    save_snapshot,
    setup_navigation_run,
)


class ClearfactsNavigationToolsTest(unittest.TestCase):
    def test_build_playwright_mcp_args_preserves_quoted_segments(self) -> None:
        self.assertEqual(
            build_playwright_mcp_args('node server.js --label "hello world"', headless=False),
            ["node", "server.js", "--label", "hello world"],
        )
        self.assertEqual(
            build_playwright_mcp_args("-y @playwright/mcp@latest", headless=True),
            ["-y", "@playwright/mcp@latest", "--headless"],
        )

    def test_load_navigation_source_reads_yaml_contract(self) -> None:
        source = load_navigation_source("navigation_agent_clearfacts")
        self.assertEqual(source.source_name, "navigation_agent_clearfacts")
        self.assertEqual(source.base_url, "https://staging.acc.clearfacts.be")
        self.assertEqual(source.default_role, "sme_admin")
        self.assertIn("accountant", source.available_roles)
        self.assertTrue(source.entry_points)
        self.assertIn("sme_admin", source.credentials)
        self.assertFalse(source.playwright.headless)

    def test_setup_navigation_run_creates_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_210000",
            )

            self.assertTrue(run.source_workspace_dir.exists())
            self.assertTrue(run.run_dir.exists())
            self.assertTrue(run.run_ontology.exists())
            self.assertTrue(run.manifest_path.exists())
            self.assertTrue(run.events_path.exists())
            self.assertTrue(run.browser_profile_dir.exists())
            self.assertTrue((run.source_workspace_dir / "ontology.md").exists())

            ontology_text = run.run_ontology.read_text(encoding="utf-8")
            self.assertIn("## Exploration Targets", ontology_text)
            self.assertIn("## Screens", ontology_text)

    def test_merge_navigation_ontology_appends_structured_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_220000",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    screens=[
                        NavigationScreenObservation(
                            name="Login page",
                            url="https://staging.acc.clearfacts.be/login",
                            title="Clearfacts voor Accountants",
                            description="Authentication page for Clearfacts users.",
                            labels=["Gebruikersnaam", "Wachtwoord"],
                        )
                    ],
                    actions=[
                        NavigationActionObservation(
                            name="Submit login form",
                            description="Submit the login form to authenticate.",
                            page_name="Login page",
                            target_hint="#_submit",
                        )
                    ],
                    labels=[
                        NavigationLabelObservation(
                            text="Aanmelden op Clearfacts",
                            page_name="Login page",
                            label_type="heading",
                        )
                    ],
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Anonymous user can open the login page from the base URL.",
                            from_screen="Base URL",
                            to_screen="Login page",
                            action_summary="Navigate to /login.",
                        )
                    ],
                    validation_notes=[
                        NavigationValidationNote(
                            note="Login flow still needs live browser validation for role-specific landing pages.",
                            severity="warning",
                        )
                    ],
                    open_questions=["Which page does sme_admin land on after login?"],
                ),
            )

            ontology = load_navigation_ontology(run.run_ontology)
            self.assertEqual(len(ontology.screens), 1)
            self.assertEqual(ontology.screens[0].name, "Login page")
            self.assertEqual(len(ontology.actions), 1)
            self.assertEqual(len(ontology.labels), 1)
            self.assertEqual(len(ontology.navigation_paths), 1)
            self.assertEqual(len(ontology.validation_notes), 1)
            self.assertEqual(ontology.open_questions, ["Which page does sme_admin land on after login?"])

    def test_merge_navigation_ontology_backfills_typed_route_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_220500",
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    navigation_paths=[
                        NavigationPathObservation(
                            description="Authenticate from the Login page to reach the role-specific Dashboard.",
                            from_screen="Login page",
                            to_screen="Dashboard",
                            action_summary="Fill credentials and submit.",
                            route_steps=[
                                "Go to /login",
                                "Type valid Gebruikersnaam into #username",
                                "Type valid Wachtwoord into #password",
                                "Click Aanmelden (#_submit)",
                            ],
                            success_criteria=["Dashboard heading visible (e.g., Bedrijfsresultaat per boekperiode)"],
                        )
                    ]
                ),
                source_base_url="https://staging.acc.clearfacts.be",
            )

            ontology = load_navigation_ontology(run.run_ontology)
            typed_steps = ontology.navigation_paths[0].typed_route_steps

        self.assertEqual(
            [step.operation for step in typed_steps],
            [
                ExplorationActionType.NAVIGATE_URL,
                ExplorationActionType.TYPE_ROLE_CREDENTIAL,
                ExplorationActionType.TYPE_ROLE_CREDENTIAL,
                ExplorationActionType.CLICK,
                ExplorationActionType.WAIT_FOR_TEXT,
            ],
        )
        self.assertEqual(typed_steps[0].url, "https://staging.acc.clearfacts.be/login")
        self.assertEqual(typed_steps[1].credential_field, CredentialField.USERNAME)
        self.assertEqual(typed_steps[2].credential_field, CredentialField.PASSWORD)
        self.assertEqual(typed_steps[3].target, "#_submit")
        self.assertEqual(typed_steps[4].text, "Bedrijfsresultaat per boekperiode")

    def test_finalize_navigation_run_merges_run_ontology_into_source_ontology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_221000",
            )
            merge_navigation_ontology(
                run.baseline_ontology,
                NavigationOntologyDelta(
                    screens=[
                        NavigationScreenObservation(
                            name="Existing source screen",
                            url="https://example.test/existing",
                            title="Existing",
                            description="Existing source-level observation.",
                        )
                    ]
                ),
            )
            merge_navigation_ontology(
                run.run_ontology,
                NavigationOntologyDelta(
                    screens=[
                        NavigationScreenObservation(
                            name="Run-discovered screen",
                            url="https://example.test/run",
                            title="Run",
                            description="Observation discovered in one navigation run.",
                        )
                    ]
                ),
            )

            finalize_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_221000",
            )

            source_ontology = load_navigation_ontology(run.baseline_ontology)
            screen_names = {screen.name for screen in source_ontology.screens}
            self.assertIn("Existing source screen", screen_names)
            self.assertIn("Run-discovered screen", screen_names)

    def test_prepare_arguments_prefers_target_for_current_playwright_tools(self) -> None:
        browser = PlaywrightMcpBrowser(PlaywrightMcpServerConfig(command="npx"))
        browser._tools = {
            "browser_type": type(
                "Tool",
                (),
                {
                    "inputSchema": {
                        "properties": {
                            "element": {"type": "string"},
                            "target": {"type": "string"},
                            "text": {"type": "string"},
                        }
                    }
                },
            )(),
            "browser_evaluate": type(
                "Tool",
                (),
                {
                    "inputSchema": {
                        "properties": {
                            "function": {"type": "string"},
                        }
                    }
                },
            )(),
        }

        type_arguments = browser._prepare_arguments(
            "browser_type",
            [
                (("target", "selector", "element", "ref"), "#username"),
                (("text", "value"), "hello"),
            ],
        )
        evaluate_arguments = browser._prepare_arguments(
            "browser_evaluate",
            [
                (("function", "expression", "script"), "() => document.title"),
            ],
        )

        self.assertEqual(type_arguments, {"target": "#username", "text": "hello"})
        self.assertEqual(evaluate_arguments, {"function": "() => document.title"})

    def test_human_readable_summary_and_snapshot_include_page_summary(self) -> None:
        summary = build_human_readable_page_summary(
            {
                "title": "Login",
                "url": "https://staging.acc.clearfacts.be/login",
                "headings": ["Aanmelden op Clearfacts"],
                "buttons": ["Aanmelden"],
                "inputs": ["Gebruikersnaam | text", "Wachtwoord | password"],
                "text_excerpt": "Welkom terug",
            }
        )
        self.assertIn("**Headings**", summary)
        self.assertIn("Aanmelden", summary)

        with tempfile.TemporaryDirectory() as tmp_dir:
            run = setup_navigation_run(
                "navigation_agent_clearfacts",
                workspace_dir=tmp_dir,
                timestamp="20260430_230000",
            )
            snapshot_path = save_snapshot(
                run,
                step_index=1,
                phase="after",
                page=NavigationPageEvidence(
                    url="https://staging.acc.clearfacts.be/login",
                    title="Login",
                    page_summary=summary,
                    text_excerpt="Welkom terug",
                ),
            )

            self.assertIsNotNone(snapshot_path)
            snapshot_text = Path(snapshot_path).read_text(encoding="utf-8")
            self.assertIn("## Human summary", snapshot_text)
            self.assertIn("Aanmelden op Clearfacts", snapshot_text)

    def test_remap_snapshot_ref_target_matches_same_control_in_fresh_snapshot(self) -> None:
        previous_snapshot = """
        - textbox "Gebruikersnaam" [active] [ref=e14]
        - button "Aanmelden" [ref=e19] [cursor=pointer]
        """
        fresh_snapshot = """
        - textbox "Gebruikersnaam" [active] [ref=e114]
        - button "Aanmelden" [ref=e119] [cursor=pointer]
        """

        self.assertEqual(
            remap_snapshot_ref_target(
                "ref=e14",
                previous_snapshot=previous_snapshot,
                fresh_snapshot=fresh_snapshot,
            ),
            "ref=e114",
        )
        self.assertEqual(
            remap_snapshot_ref_target(
                "ref=e19",
                previous_snapshot=previous_snapshot,
                fresh_snapshot=fresh_snapshot,
            ),
            "ref=e119",
        )

    def test_prepare_action_target_normalizes_bracket_ref(self) -> None:
        agent = ClearfactsNavigationAgent.__new__(ClearfactsNavigationAgent)
        action = ExplorationAction(
            action_type=ExplorationActionType.TYPE_TEXT,
            summary="Type into field",
            target="[ref=e14]",
            text="hello",
        )

        prepared = agent._prepare_action_target(action=action, current_page=None)
        self.assertEqual(prepared.target, "ref=e14")

    def test_prepare_action_target_prefers_stable_login_selectors(self) -> None:
        agent = ClearfactsNavigationAgent.__new__(ClearfactsNavigationAgent)
        username_action = ExplorationAction(
            action_type=ExplorationActionType.TYPE_ROLE_CREDENTIAL,
            summary="Type username",
            target="[ref=e14]",
            role="sme_admin",
            credential_field=CredentialField.USERNAME,
        )
        submit_action = ExplorationAction(
            action_type=ExplorationActionType.CLICK,
            summary="Click Aanmelden",
            target="[ref=e19]",
        )
        login_page = NavigationPageEvidence(
            url="https://staging.acc.clearfacts.be/login",
            snapshot='- button "Aanmelden" [ref=e19]\n- textbox "Gebruikersnaam" [ref=e14]',
        )

        prepared_username = agent._prepare_action_target(action=username_action, current_page=login_page)
        prepared_submit = agent._prepare_action_target(action=submit_action, current_page=login_page)

        self.assertEqual(prepared_username.target, "#username")
        self.assertEqual(prepared_submit.target, "#_submit")

    def test_prepare_action_target_resolves_affordance_key_to_selector(self) -> None:
        agent = ClearfactsNavigationAgent.__new__(ClearfactsNavigationAgent)
        action = ExplorationAction(
            action_type=ExplorationActionType.CLICK,
            summary="Open purchase inbox",
            target="link:href:/test-dossier-vdl/inbox/purchase",
        )
        page = NavigationPageEvidence(
            url="https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard",
            affordances=[
                NavigationPageAffordance(
                    key="link:href:/test-dossier-vdl/inbox/purchase",
                    kind="a",
                    label="5 Aankoop",
                    selector='a[href="/test-dossier-vdl/inbox/purchase"]',
                    href="/test-dossier-vdl/inbox/purchase",
                )
            ],
        )

        prepared = agent._prepare_action_target(action=action, current_page=page)
        self.assertEqual(prepared.target, 'a[href="/test-dossier-vdl/inbox/purchase"]')

    def test_prepare_action_target_resolves_affordance_by_label(self) -> None:
        agent = ClearfactsNavigationAgent.__new__(ClearfactsNavigationAgent)
        action = ExplorationAction(
            action_type=ExplorationActionType.CLICK,
            summary="Open purchase inbox",
            target="Aankoop",
        )
        page = NavigationPageEvidence(
            url="https://staging.acc.clearfacts.be/test-dossier-vdl/dashboard",
            affordances=[
                NavigationPageAffordance(
                    key="link:href:/test-dossier-vdl/inbox/purchase",
                    kind="a",
                    label="5 Aankoop",
                    selector='a[href="/test-dossier-vdl/inbox/purchase"]',
                    href="/test-dossier-vdl/inbox/purchase",
                )
            ],
        )

        prepared = agent._prepare_action_target(action=action, current_page=page)
        self.assertEqual(prepared.target, 'a[href="/test-dossier-vdl/inbox/purchase"]')

    def test_extract_json_payload_from_tool_message_parses_playwright_result_wrapper(self) -> None:
        message = """### Result
"{\\"url\\": \\"https://example.test/dashboard\\", \\"title\\": \\"Dashboard\\", \\"affordances\\": [{\\"key\\": \\"link:href:/inbox/purchase\\", \\"kind\\": \\"a\\", \\"label\\": \\"Aankoop\\", \\"selector\\": \\"a[href=\\\\\\"/inbox/purchase\\\\\\"]\\"}]}"
### Ran Playwright code
```js
await page.evaluate('...');
```"""
        parsed = extract_json_payload_from_tool_message(message)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["url"], "https://example.test/dashboard")
        self.assertEqual(parsed["affordances"][0]["key"], "link:href:/inbox/purchase")


class ClearfactsNavigationAsyncBridgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_inspect_page_does_not_sleep_for_configured_step_delay(self) -> None:
        browser = PlaywrightMcpBrowser(PlaywrightMcpServerConfig(command="npx", step_delay_ms=500))

        async def fail_sleep(_seconds):
            raise AssertionError("inspect_page should not sleep without a transient navigation error.")

        async def fake_evaluate(function_text, target=None):
            return ExecutedToolCall(
                tool_name="browser_evaluate",
                arguments={},
                message=(
                    '### Result\n'
                    '"{\\"url\\": \\"https://example.test/dashboard\\", '
                    '\\"title\\": \\"Dashboard\\", '
                    '\\"affordances\\": []}"'
                ),
            )

        browser.evaluate = fake_evaluate

        with patch("context_db.agents.clearfacts_navigation_agent.tools.asyncio.sleep", new=fail_sleep):
            page = await browser.inspect_page(include_snapshot=False)

        self.assertEqual(page.url, "https://example.test/dashboard")
        self.assertEqual(page.title, "Dashboard")

    async def test_wait_for_text_uses_evaluate_based_condition_wait(self) -> None:
        browser = PlaywrightMcpBrowser(PlaywrightMcpServerConfig(command="npx"))
        calls = []

        async def fake_evaluate(function_text, target=None):
            calls.append(function_text)
            return ExecutedToolCall(
                tool_name="browser_evaluate",
                arguments={"function": function_text},
                message=(
                    '### Result\n'
                    '"{\\"visible\\": true, '
                    '\\"text\\": \\"Bedrijfsresultaat per boekperiode\\", '
                    '\\"url\\": \\"https://example.test/dashboard\\", '
                    '\\"title\\": \\"Dashboard\\"}"'
                ),
            )

        browser.evaluate = fake_evaluate

        execution = await browser.wait_for_text("Bedrijfsresultaat per boekperiode")

        self.assertEqual(execution.tool_name, "browser_evaluate")
        self.assertEqual(execution.message, "Observed text 'Bedrijfsresultaat per boekperiode' in page evidence.")
        self.assertEqual(len(calls), 1)

    async def test_inspect_page_retries_transient_navigation_errors(self) -> None:
        browser = PlaywrightMcpBrowser(PlaywrightMcpServerConfig(command="npx", step_delay_ms=0))
        calls = {"evaluate": 0}

        async def fake_snapshot(target=None):
            return ExecutedToolCall(
                tool_name="browser_snapshot",
                arguments={},
                message='- heading "Purchase inbox" [ref=e1]',
            )

        async def fake_evaluate(function_text, target=None):
            calls["evaluate"] += 1
            if calls["evaluate"] == 1:
                raise PlaywrightToolExecutionError(
                    tool_name="browser_evaluate",
                    arguments={},
                    message="Error: browserBackend.callTool: Execution context was destroyed, most likely because of a navigation",
                )
            return ExecutedToolCall(
                tool_name="browser_evaluate",
                arguments={},
                message=(
                    '### Result\n'
                    '"{\\"url\\": \\"https://example.test/inbox\\", '
                    '\\"title\\": \\"Purchase inbox\\", '
                    '\\"affordances\\": []}"'
                ),
            )

        browser.capture_snapshot = fake_snapshot
        browser.evaluate = fake_evaluate

        page = await browser.inspect_page(include_snapshot=True)

        self.assertEqual(calls["evaluate"], 2)
        self.assertEqual(page.url, "https://example.test/inbox")
        self.assertEqual(page.title, "Purchase inbox")

    async def test_run_async_blocking_works_inside_running_event_loop(self) -> None:
        async def sample_coroutine() -> str:
            await asyncio.sleep(0)
            return "ok"

        self.assertEqual(_run_async_blocking(sample_coroutine()), "ok")


if __name__ == "__main__":
    unittest.main()
