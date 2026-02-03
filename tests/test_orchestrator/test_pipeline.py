"""Unit tests for PipelineOrchestrator.

Tests the orchestrator's ability to coordinate tool execution, manage
pipeline stages, enforce rate limits, and handle stage dependencies.
"""

import asyncio
import json
import unittest
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from galehuntui.core.constants import (
    EngagementMode,
    PipelineStage,
    RATE_LIMITS,
    StepStatus,
)
from galehuntui.core.exceptions import (
    PipelineError,
    ToolNotFoundError,
)
from galehuntui.core.models import (
    Finding,
    RunConfig,
    ScanProfile,
    ScopeConfig,
    Severity,
    Confidence,
    ToolConfig,
    ToolResult,
)
from galehuntui.orchestrator.pipeline import (
    PipelineConfig,
    PipelineOrchestrator,
    STAGE_TOOL_MAP,
    STAGE_DEPENDENCIES,
)
from galehuntui.orchestrator.state import RunStateManager, StageResult
from galehuntui.orchestrator.scheduler import TaskScheduler


class TestPipelineConfig(unittest.TestCase):
    """Test PipelineConfig initialization and validation."""
    
    def test_pipeline_config_initialization(self):
        """Test PipelineConfig can be created with required fields."""
        profile = ScanProfile(
            name="test_profile",
            description="Test profile",
            steps=["subfinder", "httpx"],
        )
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[PipelineStage.SUBDOMAIN_ENUM, PipelineStage.HTTP_PROBING],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        self.assertEqual(len(config.stages), 2)
        self.assertEqual(config.profile, profile)
        self.assertEqual(config.scope, scope)
        self.assertEqual(config.engagement_mode, EngagementMode.BUG_BOUNTY)
        self.assertEqual(config.concurrency, 10)
        self.assertEqual(config.rate_limit_global, 30)
        self.assertEqual(config.rate_limit_per_host, 5)
        self.assertEqual(config.timeout, 300)
        self.assertFalse(config.stop_on_failure)
    
    def test_pipeline_config_custom_parameters(self):
        """Test PipelineConfig with custom execution parameters."""
        profile = ScanProfile(
            name="aggressive",
            description="Aggressive scan",
            steps=["subfinder"],
        )
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[PipelineStage.SUBDOMAIN_ENUM],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.AGGRESSIVE,
            concurrency=50,
            rate_limit_global=500,
            rate_limit_per_host=100,
            timeout=600,
            stop_on_failure=True,
        )
        
        self.assertEqual(config.concurrency, 50)
        self.assertEqual(config.rate_limit_global, 500)
        self.assertEqual(config.rate_limit_per_host, 100)
        self.assertEqual(config.timeout, 600)
        self.assertTrue(config.stop_on_failure)


class TestPipelineOrchestrator(unittest.IsolatedAsyncioTestCase):
    """Test PipelineOrchestrator initialization and configuration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(
            name="standard",
            description="Standard scan",
            steps=["subfinder", "httpx", "nuclei"],
            timeout=300,
        )
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[
                PipelineStage.SUBDOMAIN_ENUM,
                PipelineStage.HTTP_PROBING,
                PipelineStage.VULN_SCANNING,
            ],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        # Create mock adapters
        self.mock_adapters = {}
        for tool in ["subfinder", "httpx", "nuclei"]:
            mock_adapter = AsyncMock()
            mock_adapter.name = tool
            mock_adapter.required = True
            mock_adapter.mode_required = None
            mock_adapter.check_available.return_value = True
            self.mock_adapters[tool] = mock_adapter
    
    def test_orchestrator_initialization(self):
        """Test PipelineOrchestrator initializes correctly."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        self.assertEqual(orchestrator.config, self.config)
        self.assertEqual(orchestrator.adapters, self.mock_adapters)
        self.assertIsNotNone(orchestrator.state)
        self.assertIsNotNone(orchestrator.scheduler)
        self.assertIsNotNone(orchestrator.classifier)
        self.assertFalse(orchestrator._running)
        self.assertFalse(orchestrator._cancelled)
    
    def test_orchestrator_creates_run_config(self):
        """Test orchestrator creates RunConfig if not provided."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        self.assertIsNotNone(orchestrator.run_config)
        self.assertEqual(orchestrator.run_config.profile, "standard")
        self.assertEqual(orchestrator.run_config.engagement_mode, EngagementMode.BUG_BOUNTY)
        self.assertEqual(orchestrator.run_config.concurrency, 10)
    
    def test_orchestrator_uses_provided_state_manager(self):
        """Test orchestrator uses provided state manager."""
        run_config = RunConfig(
            target="test.com",
            profile="standard",
            scope_file=Path(),
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        state_manager = RunStateManager(run_config)
        
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
            state_manager=state_manager,
        )
        
        self.assertEqual(orchestrator.state, state_manager)
    
    def test_scheduler_initialized_with_correct_parameters(self):
        """Test scheduler is initialized with correct rate limits and concurrency."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        self.assertEqual(orchestrator.scheduler.max_workers, self.config.concurrency)
        self.assertIsNotNone(orchestrator.scheduler.rate_limiter)


class TestPipelineExecution(unittest.IsolatedAsyncioTestCase):
    """Test pipeline execution flow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(
            name="quick",
            description="Quick scan",
            steps=["subfinder", "httpx"],
            timeout=300,
        )
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[
                PipelineStage.SUBDOMAIN_ENUM,
                PipelineStage.DNS_RESOLUTION,
                PipelineStage.HTTP_PROBING,
            ],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        # Create mock adapters
        self.mock_adapters = {}
        for tool in ["subfinder", "dnsx", "httpx"]:
            mock_adapter = AsyncMock()
            mock_adapter.name = tool
            mock_adapter.check_available.return_value = True
            
            # Mock successful run
            mock_adapter.run.return_value = ToolResult(
                stdout=json.dumps({"host": "sub.example.com"}),
                stderr="",
                exit_code=0,
                duration=1.5,
                output_path=Path("/tmp/output.json"),
            )
            mock_adapter.parse_output.return_value = []
            
            self.mock_adapters[tool] = mock_adapter
    
    async def test_run_prevents_concurrent_execution(self):
        """Test run() raises error if pipeline already running."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        # Mock state manager to avoid actual execution
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock):
                # Start first run
                orchestrator._running = True
                
                # Attempt second run
                with self.assertRaises(PipelineError) as ctx:
                    await orchestrator.run("example.com")
                
                self.assertIn("already running", str(ctx.exception))
    
    async def test_run_initializes_state(self):
        """Test run() initializes state and directories."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock) as mock_init:
            with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'complete_run', new_callable=AsyncMock):
                    with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock):
                        with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                            with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                                await orchestrator.run("example.com")
                                
                                mock_init.assert_called_once()
    
    async def test_run_registers_steps(self):
        """Test run() registers all pipeline steps."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'register_steps') as mock_register:
                with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock):
                    with patch.object(orchestrator.state, 'complete_run', new_callable=AsyncMock):
                        with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock):
                            with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                                with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                                    await orchestrator.run("example.com")
                                    
                                    mock_register.assert_called_once()
                                    registered_steps = mock_register.call_args[0][0]
                                    self.assertEqual(len(registered_steps), 3)
                                    self.assertIn("subdomain_enumeration", registered_steps)
    
    async def test_run_starts_and_stops_scheduler(self):
        """Test run() starts scheduler at beginning and stops at end."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'complete_run', new_callable=AsyncMock):
                    with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock):
                        with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock) as mock_start:
                            with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock) as mock_stop:
                                await orchestrator.run("example.com")
                                
                                mock_start.assert_called_once()
                                mock_stop.assert_called_once()
    
    async def test_run_executes_all_stages_in_order(self):
        """Test run() executes all configured stages in order."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'complete_run', new_callable=AsyncMock):
                    with patch.object(orchestrator, '_check_dependencies', return_value=True):
                        with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock) as mock_execute:
                            with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                                with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                                    await orchestrator.run("example.com")
                                    
                                    self.assertEqual(mock_execute.call_count, 3)
                                    # Check stages executed in order
                                    calls = mock_execute.call_args_list
                                    self.assertEqual(calls[0][0][0], PipelineStage.SUBDOMAIN_ENUM)
                                    self.assertEqual(calls[1][0][0], PipelineStage.DNS_RESOLUTION)
                                    self.assertEqual(calls[2][0][0], PipelineStage.HTTP_PROBING)
    
    async def test_run_marks_completion(self):
        """Test run() marks run as completed when successful."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'complete_run', new_callable=AsyncMock) as mock_complete:
                    with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock):
                        with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                            with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                                # Mock metadata state to simulate running state
                                orchestrator.state.metadata.state = MagicMock()
                                orchestrator.state.metadata.state.value = "running"
                                
                                await orchestrator.run("example.com")
                                
                                mock_complete.assert_called_once()
    
    async def test_run_handles_cancellation(self):
        """Test run() handles cancellation correctly."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        # Create a side effect that sets cancelled flag after start_run
        async def set_cancelled():
            orchestrator._cancelled = True
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'start_run', new_callable=AsyncMock, side_effect=set_cancelled):
                with patch.object(orchestrator.state, 'cancel_run', new_callable=AsyncMock) as mock_cancel:
                    with patch.object(orchestrator, '_execute_stage', new_callable=AsyncMock) as mock_execute:
                        with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                            with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                                await orchestrator.run("example.com")
                                
                                mock_cancel.assert_called_once()
                                # Should not execute any stages
                                mock_execute.assert_not_called()
    
    async def test_run_handles_failure(self):
        """Test run() marks run as failed on exception."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'initialize', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'start_run', side_effect=Exception("Test error")):
                with patch.object(orchestrator.state, 'fail_run', new_callable=AsyncMock) as mock_fail:
                    with patch.object(orchestrator.scheduler, 'start', new_callable=AsyncMock):
                        with patch.object(orchestrator.scheduler, 'stop', new_callable=AsyncMock):
                            with self.assertRaises(PipelineError):
                                await orchestrator.run("example.com")
                            
                            mock_fail.assert_called_once()


class TestStageExecution(unittest.IsolatedAsyncioTestCase):
    """Test individual stage execution."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(
            name="test",
            description="Test",
            steps=["subfinder"],
            timeout=300,
        )
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[PipelineStage.SUBDOMAIN_ENUM],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        self.mock_adapter = AsyncMock()
        self.mock_adapter.name = "subfinder"
        self.mock_adapter.check_available.return_value = True
        self.mock_adapter.run.return_value = ToolResult(
            stdout='{"host": "sub.example.com"}',
            stderr="",
            exit_code=0,
            duration=1.5,
            output_path=Path("/tmp/output.json"),
        )
        # Use Mock instead of AsyncMock for non-async method
        self.mock_adapter.parse_output = Mock(return_value=[])
        
        self.mock_adapters = {"subfinder": self.mock_adapter}
    
    async def test_execute_stage_starts_step(self):
        """Test _execute_stage() marks step as started."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'start_step', new_callable=AsyncMock) as mock_start:
            with patch.object(orchestrator.state, 'complete_step', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'store_stage_result', new_callable=AsyncMock):
                    with patch.object(orchestrator.state, 'get_artifact_path') as mock_path:
                        mock_path.return_value = Path("/tmp/test.txt")
                        await orchestrator._execute_stage(PipelineStage.SUBDOMAIN_ENUM, "example.com")
                        
                        mock_start.assert_called_once_with("subdomain_enumeration")
    
    async def test_execute_stage_completes_step_on_success(self):
        """Test _execute_stage() marks step as completed on success."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator.state, 'start_step', new_callable=AsyncMock):
            with patch.object(orchestrator.state, 'complete_step', new_callable=AsyncMock) as mock_complete:
                with patch.object(orchestrator.state, 'store_stage_result', new_callable=AsyncMock):
                    with patch.object(orchestrator.state, 'get_artifact_path') as mock_path:
                        mock_path.return_value = Path("/tmp/test.txt")
                        await orchestrator._execute_stage(PipelineStage.SUBDOMAIN_ENUM, "example.com")
                        
                        mock_complete.assert_called_once()
    
    async def test_execute_stage_skips_when_no_inputs(self):
        """Test _execute_stage() skips stage when no inputs available."""
        orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters=self.mock_adapters,
        )
        
        with patch.object(orchestrator, '_get_stage_inputs', return_value=[]):
            with patch.object(orchestrator.state, 'start_step', new_callable=AsyncMock):
                with patch.object(orchestrator.state, 'skip_step', new_callable=AsyncMock) as mock_skip:
                    result = await orchestrator._execute_stage(PipelineStage.DNS_RESOLUTION, "example.com")
                    
                    mock_skip.assert_called_once_with("dns_resolution", "No inputs")
                    self.assertEqual(result.status, StepStatus.SKIPPED)


class TestDependencyChecking(unittest.IsolatedAsyncioTestCase):
    """Test stage dependency validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(
            name="test",
            description="Test",
            steps=["subfinder"],
            timeout=300,
        )
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[PipelineStage.SUBDOMAIN_ENUM, PipelineStage.DNS_RESOLUTION],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        self.orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters={},
        )
    
    def test_check_dependencies_no_dependencies(self):
        """Test _check_dependencies() returns True for stages with no dependencies."""
        result = self.orchestrator._check_dependencies(PipelineStage.SUBDOMAIN_ENUM)
        self.assertTrue(result)
    
    def test_check_dependencies_satisfied(self):
        """Test _check_dependencies() returns True when dependencies satisfied."""
        # Mock successful dependency result
        dep_result = StageResult(
            stage=PipelineStage.SUBDOMAIN_ENUM,
            status=StepStatus.COMPLETED,
        )
        self.orchestrator.state._stage_results[PipelineStage.SUBDOMAIN_ENUM] = dep_result
        
        result = self.orchestrator._check_dependencies(PipelineStage.DNS_RESOLUTION)
        self.assertTrue(result)
    
    def test_check_dependencies_not_satisfied(self):
        """Test _check_dependencies() returns False when dependencies not met."""
        # No result for dependency
        result = self.orchestrator._check_dependencies(PipelineStage.DNS_RESOLUTION)
        self.assertFalse(result)
    
    def test_check_dependencies_failed_dependency(self):
        """Test _check_dependencies() returns False when dependency failed."""
        # Mock failed dependency result
        dep_result = StageResult(
            stage=PipelineStage.SUBDOMAIN_ENUM,
            status=StepStatus.FAILED,
        )
        self.orchestrator.state._stage_results[PipelineStage.SUBDOMAIN_ENUM] = dep_result
        
        result = self.orchestrator._check_dependencies(PipelineStage.DNS_RESOLUTION)
        self.assertFalse(result)


class TestRateLimiting(unittest.IsolatedAsyncioTestCase):
    """Test rate limiting based on engagement mode."""
    
    def test_bugbounty_mode_rate_limits(self):
        """Test BUG_BOUNTY mode applies correct rate limits."""
        profile = ScanProfile(name="test", description="Test", steps=[])
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        orchestrator = PipelineOrchestrator(config=config, adapters={})
        
        # Check rate limits from RATE_LIMITS constant
        expected = RATE_LIMITS[EngagementMode.BUG_BOUNTY]
        self.assertEqual(orchestrator.run_config.rate_limit_global, expected["global"])
        self.assertEqual(orchestrator.run_config.rate_limit_per_host, expected["per_host"])
        self.assertEqual(orchestrator.run_config.concurrency, expected["concurrency"])
    
    def test_authorized_mode_rate_limits(self):
        """Test AUTHORIZED mode applies correct rate limits."""
        profile = ScanProfile(name="test", description="Test", steps=[])
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.AUTHORIZED,
            rate_limit_global=100,
            rate_limit_per_host=20,
            concurrency=50,
        )
        
        orchestrator = PipelineOrchestrator(config=config, adapters={})
        
        self.assertEqual(orchestrator.run_config.rate_limit_global, 100)
        self.assertEqual(orchestrator.run_config.rate_limit_per_host, 20)
        self.assertEqual(orchestrator.run_config.concurrency, 50)
    
    def test_aggressive_mode_rate_limits(self):
        """Test AGGRESSIVE mode applies correct rate limits."""
        profile = ScanProfile(name="test", description="Test", steps=[])
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.AGGRESSIVE,
            rate_limit_global=500,
            rate_limit_per_host=100,
            concurrency=100,
        )
        
        orchestrator = PipelineOrchestrator(config=config, adapters={})
        
        self.assertEqual(orchestrator.run_config.rate_limit_global, 500)
        self.assertEqual(orchestrator.run_config.rate_limit_per_host, 100)
        self.assertEqual(orchestrator.run_config.concurrency, 100)


class TestControlFunctions(unittest.IsolatedAsyncioTestCase):
    """Test pause, resume, and cancel functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(name="test", description="Test", steps=[])
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        self.orchestrator = PipelineOrchestrator(config=self.config, adapters={})
    
    async def test_cancel_sets_flag(self):
        """Test cancel() sets the cancelled flag."""
        self.assertFalse(self.orchestrator._cancelled)
        await self.orchestrator.cancel()
        self.assertTrue(self.orchestrator._cancelled)
    
    async def test_pause_clears_event(self):
        """Test pause() clears the pause event."""
        with patch.object(self.orchestrator.state, 'pause_run', new_callable=AsyncMock):
            self.assertTrue(self.orchestrator._pause_event.is_set())
            await self.orchestrator.pause()
            self.assertFalse(self.orchestrator._pause_event.is_set())
    
    async def test_resume_sets_event(self):
        """Test resume() sets the pause event."""
        with patch.object(self.orchestrator.state, 'resume_run', new_callable=AsyncMock):
            self.orchestrator._pause_event.clear()
            await self.orchestrator.resume()
            self.assertTrue(self.orchestrator._pause_event.is_set())


class TestSingleToolExecution(unittest.IsolatedAsyncioTestCase):
    """Test single tool execution outside pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.profile = ScanProfile(name="test", description="Test", steps=[])
        self.scope = ScopeConfig(target_domain="example.com")
        
        self.config = PipelineConfig(
            stages=[],
            profile=self.profile,
            scope=self.scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        self.mock_adapter = AsyncMock()
        self.mock_adapter.name = "httpx"
        self.mock_adapter.check_available.return_value = True
        self.mock_adapter.run.return_value = ToolResult(
            stdout="test output",
            stderr="",
            exit_code=0,
            duration=1.0,
            output_path=Path("/tmp/output.json"),
        )
        
        self.orchestrator = PipelineOrchestrator(
            config=self.config,
            adapters={"httpx": self.mock_adapter},
        )
    
    async def test_run_single_tool_success(self):
        """Test run_single_tool() executes tool successfully."""
        result = await self.orchestrator.run_single_tool(
            "httpx",
            ["https://example.com"],
        )
        
        self.assertTrue(result.success)
        self.mock_adapter.run.assert_called_once()
    
    async def test_run_single_tool_not_found(self):
        """Test run_single_tool() raises error for unknown tool."""
        with self.assertRaises(ToolNotFoundError):
            await self.orchestrator.run_single_tool(
                "nonexistent",
                ["input"],
            )
    
    async def test_run_single_tool_not_available(self):
        """Test run_single_tool() raises error when tool not available."""
        self.mock_adapter.check_available.return_value = False
        
        with self.assertRaises(ToolNotFoundError):
            await self.orchestrator.run_single_tool(
                "httpx",
                ["input"],
            )
    
    async def test_run_single_tool_custom_timeout(self):
        """Test run_single_tool() uses custom timeout when provided."""
        await self.orchestrator.run_single_tool(
            "httpx",
            ["https://example.com"],
            timeout=600,
        )
        
        # Check that config was created with custom timeout
        call_args = self.mock_adapter.run.call_args
        config = call_args[0][1]
        self.assertEqual(config.timeout, 600)


class TestStandardPipelineFactory(unittest.IsolatedAsyncioTestCase):
    """Test create_standard_pipeline factory method."""
    
    async def test_create_standard_pipeline(self):
        """Test create_standard_pipeline() creates correct configuration."""
        profile = ScanProfile(
            name="standard",
            description="Standard scan",
            steps=["subfinder", "dnsx", "httpx", "nuclei"],
            timeout=1800,
        )
        scope = ScopeConfig(target_domain="example.com")
        
        mock_adapters = {
            "subfinder": Mock(),
            "dnsx": Mock(),
            "httpx": Mock(),
            "nuclei": Mock(),
        }
        
        orchestrator = PipelineOrchestrator.create_standard_pipeline(
            adapters=mock_adapters,
            target="example.com",
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.AUTHORIZED,
        )
        
        self.assertEqual(orchestrator.run_config.target, "example.com")
        self.assertEqual(orchestrator.run_config.engagement_mode, EngagementMode.AUTHORIZED)
        
        # Check rate limits match AUTHORIZED mode
        expected_limits = RATE_LIMITS[EngagementMode.AUTHORIZED]
        self.assertEqual(orchestrator.config.rate_limit_global, expected_limits["global"])
        self.assertEqual(orchestrator.config.rate_limit_per_host, expected_limits["per_host"])
        self.assertEqual(orchestrator.config.concurrency, expected_limits["concurrency"])
    
    async def test_create_standard_pipeline_includes_classification(self):
        """Test create_standard_pipeline() adds URL_CLASSIFICATION before vuln stages."""
        profile = ScanProfile(
            name="deep",
            description="Deep scan",
            steps=["subfinder", "dnsx", "httpx", "katana", "nuclei", "dalfox"],
            timeout=3600,
        )
        scope = ScopeConfig(target_domain="example.com")
        
        mock_adapters = {}
        
        orchestrator = PipelineOrchestrator.create_standard_pipeline(
            adapters=mock_adapters,
            target="example.com",
            profile=profile,
            scope=scope,
        )
        
        # Check that URL_CLASSIFICATION is added before VULN_SCANNING
        stages = orchestrator.config.stages
        self.assertIn(PipelineStage.URL_CLASSIFICATION, stages)
        
        # Find indices
        if PipelineStage.URL_CLASSIFICATION in stages and PipelineStage.VULN_SCANNING in stages:
            class_idx = stages.index(PipelineStage.URL_CLASSIFICATION)
            vuln_idx = stages.index(PipelineStage.VULN_SCANNING)
            self.assertLess(class_idx, vuln_idx)


class TestAvailableStages(unittest.TestCase):
    """Test get_available_stages method."""
    
    def test_get_available_stages_all_tools_present(self):
        """Test get_available_stages() returns all stages when tools available."""
        profile = ScanProfile(name="test", description="Test", steps=[])
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=list(PipelineStage),
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        # Create mock adapters for all tools
        mock_adapters = {}
        for stage, tools in STAGE_TOOL_MAP.items():
            for tool in tools:
                mock_adapters[tool] = Mock()
        
        orchestrator = PipelineOrchestrator(config=config, adapters=mock_adapters)
        available = orchestrator.get_available_stages()
        
        # All stages should be available
        self.assertEqual(len(available), len(PipelineStage))
    
    def test_get_available_stages_internal_stages_always_available(self):
        """Test get_available_stages() includes internal stages without tools."""
        profile = ScanProfile(name="test", description="Test", steps=[])
        scope = ScopeConfig(target_domain="example.com")
        
        config = PipelineConfig(
            stages=[PipelineStage.URL_CLASSIFICATION],
            profile=profile,
            scope=scope,
            engagement_mode=EngagementMode.BUG_BOUNTY,
        )
        
        orchestrator = PipelineOrchestrator(config=config, adapters={})
        available = orchestrator.get_available_stages()
        
        # URL_CLASSIFICATION is internal, should be available
        self.assertIn(PipelineStage.URL_CLASSIFICATION, available)


if __name__ == "__main__":
    unittest.main()
