from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from context_db.agents.clearfacts_exploration_agent import ClearfactsExplorationAgent
from context_db.agents.clearfacts_exploration_agent.schemas import (
    ClearfactsExplorationRequest,
    ExplorationTaskStatus,
)
from context_db.agents.clearfacts_exploration_agent.tools import (
    find_active_exploration_run,
    load_exploration_index,
    load_scenario_tasks,
    parse_scenario_tasks,
    setup_exploration_run,
    update_exploration_index,
    update_scenario_task,
)
from context_db.agents.clearfacts_navigation_agent.schemas import NavigationOntologyDelta
from context_db.agents.clearfacts_navigation_deepagent.schemas import (
    ClearfactsNavigationDeepAgentRequest,
    ClearfactsNavigationDeepAgentResult,
    ClearfactsNavigationOntologyUpdateRequest,
    ClearfactsNavigationOntologyUpdateResult,
    DeepAgentExecutionStatus,
    DeepAgentTraceReference,
)


class ClearfactsExplorationAgentTest(unittest.TestCase):
    @staticmethod
    def _write_seed(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """---
scenario_id: test-scenario
source_name: navigation_agent_clearfacts
title: Test scenario
default_role: sme_admin
---

# Goal

Test scenario.

# Tasks

### T001 - Dashboard
status: pending
priority: high
instruction: Go to the dashboard.
max_minutes: 3

### T002 - Archive
status: pending
priority: medium
instruction: Go to the archive.
max_minutes: 4
""",
            encoding="utf-8",
        )

    def test_parse_scenario_tasks_reads_markdown_task_blocks(self) -> None:
        tasks = parse_scenario_tasks(
            """# Tasks

### T001 - Payments overview
status: pending
priority: high
instruction: Go to Payments and identify visible controls.
max_minutes: 3

### T002 - Archive overview
status: blocked
instruction: Go to Archive.
"""
        )

        self.assertEqual([task.task_id for task in tasks], ["T001", "T002"])
        self.assertEqual(tasks[0].title, "Payments overview")
        self.assertEqual(tasks[0].status, ExplorationTaskStatus.PENDING)
        self.assertEqual(tasks[0].priority, "high")
        self.assertEqual(tasks[0].max_minutes, 3)
        self.assertEqual(tasks[1].status, ExplorationTaskStatus.BLOCKED)

    def test_parse_scenario_tasks_reads_block_scalar_instruction(self) -> None:
        tasks = parse_scenario_tasks(
            """# Tasks

### T001 - Inboxes overview
status: pending
priority: high
instruction: |
  Go to the different inbox pages and identify visible tabs.
  inboxes: Sale, Purchase, Diverse docs.
max_minutes: 5
"""
        )

        self.assertEqual(
            tasks[0].instruction,
            "Go to the different inbox pages and identify visible tabs.\ninboxes: Sale, Purchase, Diverse docs.",
        )
        self.assertEqual(tasks[0].max_minutes, 5)

    def test_setup_exploration_run_copies_seed_and_creates_run_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110000",
            )

            manifest = yaml.safe_load(run.manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(run.scenario_path.exists())
            self.assertTrue(run.discoveries_path.exists())
            self.assertTrue(run.events_path.exists())
            self.assertTrue(run.child_navigation_runs_path.exists())
            self.assertTrue(run.index_path.exists())
            self.assertIn("Go to the dashboard", run.scenario_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_name"], "navigation_agent_clearfacts")
            self.assertEqual(manifest["status"], "initialized")
            self.assertEqual(manifest["scenario_seed_path"], str(seed))
            index = load_exploration_index("navigation_agent_clearfacts", workspace_dir=tmp_dir)
            self.assertEqual(index["scenarios"][0]["active_run_timestamp"], "20260505_110000")

    def test_update_scenario_task_marks_progress_in_run_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110001",
            )

            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.COMPLETED,
                outcome="Reached the dashboard.",
                navigation_run_timestamp="20260505_110101",
                evidence=["/tmp/trace.json"],
            )
            tasks = load_scenario_tasks(run.scenario_path)
            scenario_text = run.scenario_path.read_text(encoding="utf-8")

        self.assertEqual(tasks[0].status, ExplorationTaskStatus.COMPLETED)
        self.assertEqual(tasks[0].navigation_run_timestamp, "20260505_110101")
        self.assertIn("#### Progress Notes", scenario_text)
        self.assertIn("/tmp/trace.json", scenario_text)

    def test_exploration_agent_creates_missing_child_navigation_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run = ClearfactsExplorationAgent._ensure_child_navigation_run(
                "navigation_agent_clearfacts",
                timestamp="20260505_110010",
                workspace_dir=tmp_dir,
                force=False,
            )
            resumed = ClearfactsExplorationAgent._ensure_child_navigation_run(
                "navigation_agent_clearfacts",
                timestamp="20260505_110010",
                workspace_dir=tmp_dir,
                force=False,
            )

            self.assertEqual(run.timestamp, "20260505_110010")
            self.assertTrue(run.run_dir.exists())
            self.assertEqual(resumed.run_dir, run.run_dir)

    def test_exploration_agent_resumes_in_progress_task(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.BLOCKED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Stopped for test.",
                    run_timestamp=request.run_timestamp or "20260505_120010",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110011",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.IN_PROGRESS,
                outcome="Interrupted during previous run.",
            )
            fake_navigation = FakeNavigationAgent()
            result = ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    run_timestamp="20260505_110011",
                    max_tasks=1,
                    use_persistent_browser=False,
                )
            )
            scenario_text = Path(result.scenario_path).read_text(encoding="utf-8")

        self.assertEqual(fake_navigation.navigation_requests[0].instruction.splitlines()[0], "Go to the dashboard.")
        self.assertIn("Resumed scenario task that was left in progress.", scenario_text)

    def test_exploration_agent_resumes_latest_active_run_for_seed(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []
                self.update_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.COMPLETED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Reached archive.",
                    run_timestamp=request.run_timestamp or "20260505_120011",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                )

            def update_ontology(self, request: ClearfactsNavigationOntologyUpdateRequest):
                self.update_requests.append(request)
                return ClearfactsNavigationOntologyUpdateResult(
                    status="updated",
                    summary="Updated ontology.",
                    source_name=request.source_name,
                    run_timestamp=request.run_timestamp,
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                    source_ontology_path="/tmp/source-ontology.md",
                    analyzed_event_count=1,
                    ontology_delta=NavigationOntologyDelta(),
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110012",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.COMPLETED,
                outcome="Already reached dashboard.",
            )
            self.assertEqual(
                find_active_exploration_run("navigation_agent_clearfacts", scenario_seed_path=seed, workspace_dir=tmp_dir),
                "20260505_110012",
            )
            fake_navigation = FakeNavigationAgent()
            result = ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    max_tasks=1,
                    use_persistent_browser=False,
                )
            )
            index = load_exploration_index("navigation_agent_clearfacts", workspace_dir=tmp_dir)

        self.assertEqual(result.run_timestamp, "20260505_110012")
        self.assertIn("Go to the archive.", fake_navigation.navigation_requests[0].instruction)
        self.assertEqual(index["scenarios"][0]["latest_run_timestamp"], "20260505_110012")

    def test_exploration_agent_does_not_retry_blocked_tasks_by_default(self) -> None:
        class FailingNavigationAgent:
            def invoke(self, _request, *, browser=None):
                raise AssertionError("Blocked tasks should not be retried by default.")

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110013",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.BLOCKED,
                outcome="Blocked during previous attempt.",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T002",
                status=ExplorationTaskStatus.COMPLETED,
                outcome="Already completed.",
            )
            result = ClearfactsExplorationAgent(navigation_agent=FailingNavigationAgent()).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    run_timestamp="20260505_110013",
                    use_persistent_browser=False,
                )
            )

        self.assertEqual(result.status, ExplorationTaskStatus.BLOCKED)
        self.assertEqual(result.task_results, [])
        self.assertIn("No pending or in-progress scenario tasks", result.message)

    def test_exploration_agent_retries_blocked_tasks_when_flag_enabled(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []
                self.update_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.COMPLETED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Reached dashboard after retry.",
                    run_timestamp="20260505_120013",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                )

            def update_ontology(self, request: ClearfactsNavigationOntologyUpdateRequest):
                self.update_requests.append(request)
                return ClearfactsNavigationOntologyUpdateResult(
                    status="updated",
                    summary="Updated ontology.",
                    source_name=request.source_name,
                    run_timestamp=request.run_timestamp,
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                    source_ontology_path="/tmp/source-ontology.md",
                    analyzed_event_count=1,
                    ontology_delta=NavigationOntologyDelta(),
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110014",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.BLOCKED,
                outcome="Blocked during previous attempt.",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T002",
                status=ExplorationTaskStatus.COMPLETED,
                outcome="Already completed.",
            )
            fake_navigation = FakeNavigationAgent()
            result = ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    run_timestamp="20260505_110014",
                    retry_blocked=True,
                    max_tasks=1,
                    use_persistent_browser=False,
                )
            )
            scenario_text = Path(result.scenario_path).read_text(encoding="utf-8")

        self.assertEqual(result.status, ExplorationTaskStatus.COMPLETED)
        self.assertEqual(len(fake_navigation.navigation_requests), 1)
        self.assertIn("Go to the dashboard.", fake_navigation.navigation_requests[0].instruction)
        self.assertIn("Retrying scenario task that was previously blocked.", scenario_text)

    def test_exploration_agent_retries_latest_blocked_run_when_no_active_run_exists(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []
                self.update_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.COMPLETED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Reached dashboard after retry.",
                    run_timestamp="20260505_120014",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                )

            def update_ontology(self, request: ClearfactsNavigationOntologyUpdateRequest):
                self.update_requests.append(request)
                return ClearfactsNavigationOntologyUpdateResult(
                    status="updated",
                    summary="Updated ontology.",
                    source_name=request.source_name,
                    run_timestamp=request.run_timestamp,
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                    source_ontology_path="/tmp/source-ontology.md",
                    analyzed_event_count=1,
                    ontology_delta=NavigationOntologyDelta(),
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            run = setup_exploration_run(
                "navigation_agent_clearfacts",
                scenario_seed_path=seed,
                workspace_dir=tmp_dir,
                timestamp="20260505_110015",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T001",
                status=ExplorationTaskStatus.BLOCKED,
                outcome="Blocked during previous attempt.",
            )
            update_scenario_task(
                run.scenario_path,
                task_id="T002",
                status=ExplorationTaskStatus.COMPLETED,
                outcome="Already completed.",
            )
            update_exploration_index(run)
            self.assertIsNone(
                find_active_exploration_run(
                    "navigation_agent_clearfacts",
                    scenario_seed_path=seed,
                    workspace_dir=tmp_dir,
                )
            )

            fake_navigation = FakeNavigationAgent()
            result = ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    retry_blocked=True,
                    max_tasks=1,
                    use_persistent_browser=False,
                )
            )

        self.assertEqual(result.run_timestamp, "20260505_110015")
        self.assertEqual(result.status, ExplorationTaskStatus.COMPLETED)
        self.assertEqual(len(fake_navigation.navigation_requests), 1)

    def test_exploration_agent_delegates_task_to_navigation_agent_and_updates_ontology(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []
                self.update_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.COMPLETED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Reached dashboard.",
                    run_timestamp="20260505_120000",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                    trace_references=[
                        DeepAgentTraceReference(
                            agent_name="navigation",
                            trace_kind="coordinator",
                            path="/tmp/navigation-trace.json",
                        )
                    ],
                )

            def update_ontology(self, request: ClearfactsNavigationOntologyUpdateRequest):
                self.update_requests.append(request)
                return ClearfactsNavigationOntologyUpdateResult(
                    status="updated",
                    summary="Updated ontology.",
                    source_name=request.source_name,
                    run_timestamp=request.run_timestamp,
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                    source_ontology_path="/tmp/source-ontology.md",
                    analyzed_event_count=1,
                    ontology_delta=NavigationOntologyDelta(),
                    trace_references=[
                        DeepAgentTraceReference(
                            agent_name="ontology",
                            trace_kind="subagent",
                            path="/tmp/ontology-trace.json",
                        )
                    ],
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            fake_navigation = FakeNavigationAgent()
            result = ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    run_timestamp="20260505_110002",
                    max_tasks=1,
                    use_persistent_browser=False,
                )
            )
            run_folder = Path(result.run_folder)
            scenario_text = Path(result.scenario_path).read_text(encoding="utf-8")
            child_runs = yaml.safe_load((run_folder / "child_navigation_runs.yaml").read_text(encoding="utf-8"))
            events = [
                json.loads(line)
                for line in Path(result.events_path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(result.status, ExplorationTaskStatus.COMPLETED)
        self.assertEqual(result.completed_task_count, 1)
        self.assertEqual(len(fake_navigation.navigation_requests), 1)
        self.assertEqual(fake_navigation.navigation_requests[0].role, "sme_admin")
        self.assertIn("Scenario task id: T001", fake_navigation.navigation_requests[0].instruction)
        self.assertIn("Time budget: about 3 minute", fake_navigation.navigation_requests[0].instruction)
        self.assertEqual(len(fake_navigation.update_requests), 1)
        self.assertEqual(result.task_results[0].task.status, ExplorationTaskStatus.COMPLETED)
        self.assertIn("status: completed", scenario_text)
        self.assertEqual(child_runs["navigation_runs"][0]["task_id"], "T001")
        self.assertEqual(events[-1]["status"], "completed")

    def test_exploration_agent_passes_navigation_timestamp_for_external_browser(self) -> None:
        class FakeNavigationAgent:
            def __init__(self):
                self.navigation_requests = []

            def invoke(self, request: ClearfactsNavigationDeepAgentRequest, *, browser=None):
                self.navigation_requests.append(request)
                return ClearfactsNavigationDeepAgentResult(
                    status=DeepAgentExecutionStatus.BLOCKED,
                    source_name=request.source_name,
                    instruction=request.instruction,
                    role=request.role,
                    message="Stopped for test.",
                    run_timestamp=request.run_timestamp or "20260505_120100",
                    run_folder="/tmp/navigation-run",
                    ontology_path="/tmp/navigation-run/ontology.md",
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            seed = Path(tmp_dir) / "seed.md"
            self._write_seed(seed)
            fake_navigation = FakeNavigationAgent()
            ClearfactsExplorationAgent(navigation_agent=fake_navigation).invoke(
                ClearfactsExplorationRequest(
                    scenario_seed_path=str(seed),
                    workspace_dir=tmp_dir,
                    run_timestamp="20260505_110003",
                    max_tasks=1,
                    navigation_run_timestamp="20260505_120100",
                ),
                browser=object(),
            )

        self.assertEqual(fake_navigation.navigation_requests[0].run_timestamp, "20260505_120100")


if __name__ == "__main__":
    unittest.main()
