from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

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
    PlaywrightMcpBrowser,
    _run_async_blocking,
    build_human_readable_page_summary,
    build_playwright_mcp_args,
    extract_json_payload_from_tool_message,
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
    async def test_run_async_blocking_works_inside_running_event_loop(self) -> None:
        async def sample_coroutine() -> str:
            await asyncio.sleep(0)
            return "ok"

        self.assertEqual(_run_async_blocking(sample_coroutine()), "ok")


if __name__ == "__main__":
    unittest.main()
