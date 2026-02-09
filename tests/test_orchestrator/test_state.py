"""Unit tests for run state persistence and resume behavior."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from galehuntui.core.constants import EngagementMode, PipelineStage, StepStatus
from galehuntui.core.models import RunConfig
from galehuntui.orchestrator.state import RunStateManager
from galehuntui.storage.database import Database


class TestRunStateResume(unittest.IsolatedAsyncioTestCase):
    """Test resume hydration and state persistence semantics."""

    async def test_resume_hydrates_outputs_and_requeues_missing_artifacts(self) -> None:
        """Completed steps with missing artifacts should be marked pending on resume."""
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db = Database(tmp_path / "galehuntui.db")
            db.init_db()

            config = RunConfig(
                target="example.com",
                profile="standard",
                scope_file=tmp_path / "scope.yaml",
                engagement_mode=EngagementMode.BUG_BOUNTY,
            )

            manager = RunStateManager(
                config,
                run_id="run-resume-1",
                base_dir=tmp_path / "runs",
                db=db,
            )
            await manager.initialize()
            manager.register_steps(
                [
                    PipelineStage.SUBDOMAIN_ENUM.value,
                    PipelineStage.DNS_RESOLUTION.value,
                ]
            )
            await manager.start_run()

            subdomain_output = manager.get_artifact_path(
                PipelineStage.SUBDOMAIN_ENUM,
                "output.txt",
            )
            subdomain_output.write_text("a.example.com\nb.example.com\n")

            await manager.start_step(PipelineStage.SUBDOMAIN_ENUM.value)
            await manager.complete_step(
                PipelineStage.SUBDOMAIN_ENUM.value,
                output_path=subdomain_output,
            )

            missing_output = manager.get_artifact_path(
                PipelineStage.DNS_RESOLUTION,
                "missing.txt",
            )
            await manager.start_step(PipelineStage.DNS_RESOLUTION.value)
            await manager.complete_step(
                PipelineStage.DNS_RESOLUTION.value,
                output_path=missing_output,
            )

            resumed = await RunStateManager.resume(
                "run-resume-1",
                db,
                config,
                base_dir=tmp_path / "runs",
            )

            self.assertEqual(
                resumed.get_stage_output(PipelineStage.SUBDOMAIN_ENUM),
                ["a.example.com", "b.example.com"],
            )

            dns_step = resumed.get_step(PipelineStage.DNS_RESOLUTION.value)
            self.assertIsNotNone(dns_step)
            self.assertEqual(dns_step.status, StepStatus.PENDING)

            completed_steps = resumed.get_completed_step_names()
            self.assertIn(PipelineStage.SUBDOMAIN_ENUM.value, completed_steps)
            self.assertNotIn(PipelineStage.DNS_RESOLUTION.value, completed_steps)

            db.close()

    async def test_pause_and_resume_state_are_persisted(self) -> None:
        """pause_run and resume_run should persist metadata state changes."""
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db = Database(tmp_path / "galehuntui.db")
            db.init_db()

            config = RunConfig(
                target="example.com",
                profile="quick",
                scope_file=tmp_path / "scope.yaml",
                engagement_mode=EngagementMode.BUG_BOUNTY,
            )

            manager = RunStateManager(
                config,
                run_id="run-resume-2",
                base_dir=tmp_path / "runs",
                db=db,
            )
            await manager.initialize()
            await manager.start_run()

            await manager.pause_run()
            paused_meta = db.get_run("run-resume-2")
            self.assertIsNotNone(paused_meta)
            self.assertEqual(paused_meta.state.value, "paused")

            await manager.resume_run()
            resumed_meta = db.get_run("run-resume-2")
            self.assertIsNotNone(resumed_meta)
            self.assertEqual(resumed_meta.state.value, "running")

            db.close()

    async def test_resume_keeps_completed_step_with_empty_existing_output(self) -> None:
        """Existing empty artifacts should remain resumable and completed."""
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db = Database(tmp_path / "galehuntui.db")
            db.init_db()

            config = RunConfig(
                target="example.com",
                profile="quick",
                scope_file=tmp_path / "scope.yaml",
                engagement_mode=EngagementMode.BUG_BOUNTY,
            )

            manager = RunStateManager(
                config,
                run_id="run-resume-3",
                base_dir=tmp_path / "runs",
                db=db,
            )
            await manager.initialize()
            manager.register_steps([PipelineStage.URL_CLASSIFICATION.value])
            await manager.start_run()

            empty_output = manager.get_artifact_path(
                PipelineStage.URL_CLASSIFICATION,
                "classified_urls.jsonl",
            )
            empty_output.write_text("")

            await manager.start_step(PipelineStage.URL_CLASSIFICATION.value)
            await manager.complete_step(
                PipelineStage.URL_CLASSIFICATION.value,
                output_path=empty_output,
            )

            resumed = await RunStateManager.resume(
                "run-resume-3",
                db,
                config,
                base_dir=tmp_path / "runs",
            )

            resumed_step = resumed.get_step(PipelineStage.URL_CLASSIFICATION.value)
            self.assertIsNotNone(resumed_step)
            self.assertEqual(resumed_step.status, StepStatus.COMPLETED)
            self.assertEqual(resumed.get_stage_output(PipelineStage.URL_CLASSIFICATION), [])

            completed_steps = resumed.get_completed_step_names()
            self.assertIn(PipelineStage.URL_CLASSIFICATION.value, completed_steps)

            db.close()
