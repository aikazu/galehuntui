"""Pipeline orchestrator for automated web pentesting.

This module provides the PipelineOrchestrator class that coordinates
the execution of security tools through defined pipeline stages.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from galehuntui.storage.database import Database

from galehuntui.core.constants import (
    AuditEventType,
    ClassificationGroup,
    EngagementMode,
    PipelineStage,
    RATE_LIMITS,
    StepStatus,
)
from galehuntui.core.exceptions import (
    PipelineError,
    ScopeViolationError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from galehuntui.core.models import (
    Finding,
    RunConfig,
    ScanProfile,
    ScopeConfig,
    ToolConfig,
    ToolResult,
)
from galehuntui.classifier.classifier import URLClassifier
from galehuntui.orchestrator.state import RunStateManager, StageResult
from galehuntui.orchestrator.scheduler import TaskScheduler, TaskPriority
from galehuntui.tools.base import ToolAdapter


logger = logging.getLogger(__name__)


@runtime_checkable
class ToolAdapterProtocol(Protocol):
    """Protocol for tool adapters."""
    
    name: str
    required: bool
    mode_required: Optional[str]
    
    async def run(self, inputs: list[str], config: ToolConfig) -> ToolResult:
        ...
    
    def parse_output(self, raw: str) -> list[Finding]:
        ...
    
    async def check_available(self) -> bool:
        ...


# Stage to tool name mapping
STAGE_TOOL_MAP: dict[PipelineStage, list[str]] = {
    PipelineStage.SUBDOMAIN_ENUM: ["subfinder"],
    PipelineStage.DNS_RESOLUTION: ["dnsx"],
    PipelineStage.HTTP_PROBING: ["httpx"],
    PipelineStage.WEB_CRAWLING: ["katana", "gau"],
    PipelineStage.URL_CLASSIFICATION: [],  # Internal processing
    PipelineStage.VULN_SCANNING: ["nuclei"],
    PipelineStage.XSS_TESTING: ["dalfox"],
    PipelineStage.FUZZING: ["ffuf"],
    PipelineStage.SQLI_TESTING: ["sqlmap"],
}

# Stage dependencies (stage -> required previous stages)
STAGE_DEPENDENCIES: dict[PipelineStage, list[PipelineStage]] = {
    PipelineStage.SUBDOMAIN_ENUM: [],
    PipelineStage.DNS_RESOLUTION: [PipelineStage.SUBDOMAIN_ENUM],
    PipelineStage.HTTP_PROBING: [PipelineStage.DNS_RESOLUTION],
    PipelineStage.WEB_CRAWLING: [PipelineStage.HTTP_PROBING],
    PipelineStage.URL_CLASSIFICATION: [PipelineStage.WEB_CRAWLING],
    PipelineStage.VULN_SCANNING: [PipelineStage.URL_CLASSIFICATION],
    PipelineStage.XSS_TESTING: [PipelineStage.URL_CLASSIFICATION],
    PipelineStage.FUZZING: [PipelineStage.URL_CLASSIFICATION],
    PipelineStage.SQLI_TESTING: [PipelineStage.URL_CLASSIFICATION],
}


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution.
    
    Attributes:
        stages: List of stages to execute
        profile: Scan profile with execution parameters
        scope: Scope configuration for target validation
        engagement_mode: Engagement mode affecting rate limits and features
        concurrency: Maximum concurrent tool executions
        rate_limit_global: Global rate limit (requests/second)
        rate_limit_per_host: Per-host rate limit (requests/second)
        timeout: Default tool timeout in seconds
        stop_on_failure: Whether to stop pipeline on stage failure
    """
    stages: list[PipelineStage]
    profile: ScanProfile
    scope: ScopeConfig
    engagement_mode: EngagementMode
    concurrency: int = 10
    rate_limit_global: int = 30
    rate_limit_per_host: int = 5
    timeout: int = 300
    stop_on_failure: bool = False


class PipelineOrchestrator:
    """Orchestrates the execution of security tool pipelines.
    
    Coordinates tool execution through defined stages, manages data flow
    between stages, handles rate limiting, and tracks progress.
    
    Example:
        >>> config = PipelineConfig(...)
        >>> adapters = {"subfinder": SubfinderAdapter(...), ...}
        >>> orchestrator = PipelineOrchestrator(config, adapters)
        >>> await orchestrator.run("example.com")
    """
    
    def __init__(
        self,
        config: PipelineConfig,
        adapters: dict[str, ToolAdapter],
        *,
        run_config: Optional[RunConfig] = None,
        state_manager: Optional[RunStateManager] = None,
        db: Optional["Database"] = None,
    ) -> None:
        """Initialize pipeline orchestrator.
        
        Args:
            config: Pipeline configuration
            adapters: Dictionary of tool name -> adapter instances
            run_config: Optional run configuration
            state_manager: Optional state manager (created if not provided)
            db: Optional database for step persistence
        """
        self.config = config
        self.adapters = adapters
        self.db = db
        
        # Create run config if not provided
        if run_config is None:
            run_config = RunConfig(
                target="",
                profile=config.profile.name,
                scope_file=Path(),
                engagement_mode=config.engagement_mode,
                rate_limit_global=config.rate_limit_global,
                rate_limit_per_host=config.rate_limit_per_host,
                concurrency=config.concurrency,
                timeout=config.timeout,
            )
        self.run_config = run_config
        
        # State management
        if state_manager is None:
            state_manager = RunStateManager(run_config, db=db)
        self.state = state_manager
        
        # Task scheduler for concurrent execution
        self.scheduler = TaskScheduler(
            max_workers=config.concurrency,
            rate_limit=float(config.rate_limit_global),
            engagement_mode=config.engagement_mode,
        )
        
        # URL classifier for classification stage
        self.classifier = URLClassifier()
        
        # Execution control
        self._running = False
        self._cancelled = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
    
    async def run(self, target: str) -> RunStateManager:
        """Execute the full pipeline for a target.
        
        Args:
            target: Target domain to scan
            
        Returns:
            RunStateManager with final state and results
            
        Raises:
            PipelineError: If pipeline execution fails critically
        """
        if self._running:
            raise PipelineError("Pipeline is already running")
        
        self._running = True
        self._cancelled = False
        self.run_config.target = target
        
        try:
            # Initialize state and directories
            await self.state.initialize()
            
            # Register steps
            step_names = [stage.value for stage in self.config.stages]
            self.state.register_steps(step_names)
            
            # Start scheduler
            await self.scheduler.start()
            
            # Mark run as started
            await self.state.start_run()
            
            audit_logger = self.state.get_audit_logger()
            if audit_logger:
                audit_logger.log_event(
                    AuditEventType.MODE_CHANGE,
                    {
                        "mode": self.config.engagement_mode.value,
                        "rate_limit_global": self.config.rate_limit_global,
                        "rate_limit_per_host": self.config.rate_limit_per_host,
                    },
                )
            
            logger.info(f"Starting pipeline for target: {target}")
            
            # Execute stages in order
            for stage in self.config.stages:
                if self._cancelled:
                    logger.info("Pipeline cancelled")
                    await self.state.cancel_run()
                    break
                
                # Wait if paused
                await self._pause_event.wait()
                
                # Check dependencies
                if not self._check_dependencies(stage):
                    logger.warning(f"Skipping {stage.value}: dependencies not met")
                    await self.state.skip_step(
                        stage.value,
                        "Dependencies not met",
                    )
                    continue
                
                # Execute stage
                try:
                    await self._execute_stage(stage, target)
                except Exception as e:
                    logger.error(f"Stage {stage.value} failed: {e}")
                    await self.state.fail_step(stage.value, str(e))
                    
                    if self.config.stop_on_failure:
                        await self.state.fail_run(str(e))
                        break
            
            # Mark run as completed if not failed/cancelled
            if self.state.metadata.state.value == "running":
                await self.state.complete_run()
            
            logger.info(f"Pipeline completed: {self.state.metadata.total_findings} findings")
            
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            await self.state.fail_run(str(e))
            raise PipelineError(f"Pipeline execution failed: {e}") from e
        
        finally:
            self._running = False
            await self.scheduler.stop()
        
        return self.state
    
    async def cancel(self) -> None:
        """Cancel the running pipeline."""
        self._cancelled = True
        self._pause_event.set()  # Unpause if paused
    
    async def pause(self) -> None:
        """Pause the pipeline execution."""
        self._pause_event.clear()
        await self.state.pause_run()
    
    async def resume(self) -> None:
        """Resume paused pipeline execution."""
        self._pause_event.set()
        await self.state.resume_run()
    
    def _check_dependencies(self, stage: PipelineStage) -> bool:
        """Check if stage dependencies are satisfied.
        
        Args:
            stage: Stage to check
            
        Returns:
            True if all dependencies completed successfully
        """
        dependencies = STAGE_DEPENDENCIES.get(stage, [])
        
        for dep in dependencies:
            result = self.state.get_stage_result(dep)
            if result is None or not result.success:
                return False
        
        return True
    
    async def _execute_stage(
        self,
        stage: PipelineStage,
        target: str,
    ) -> StageResult:
        """Execute a single pipeline stage.
        
        Args:
            stage: Stage to execute
            target: Target domain
            
        Returns:
            StageResult with outputs and findings
        """
        logger.info(f"Executing stage: {stage.value}")
        await self.state.start_step(stage.value)
        
        # Get inputs from previous stages
        inputs = self._get_stage_inputs(stage, target)
        
        if not inputs:
            logger.warning(f"No inputs for stage {stage.value}")
            result = StageResult(
                stage=stage,
                status=StepStatus.SKIPPED,
                error="No inputs available",
            )
            await self.state.skip_step(stage.value, "No inputs")
            return result
        
        # Execute stage based on type
        if stage == PipelineStage.URL_CLASSIFICATION:
            result = await self._execute_classification_stage(stage, inputs)
        else:
            result = await self._execute_tool_stage(stage, inputs)
        
        # Store result and update state
        await self.state.store_stage_result(stage, result)
        
        if result.success:
            await self.state.complete_step(
                stage.value,
                output_path=result.output_path,
                findings_count=len(result.findings),
            )
        else:
            await self.state.fail_step(stage.value, result.error or "Unknown error")
        
        return result
    
    def _get_stage_inputs(
        self,
        stage: PipelineStage,
        target: str,
    ) -> list[str]:
        """Get inputs for a stage from previous stage outputs.
        
        Args:
            stage: Stage to get inputs for
            target: Original target domain
            
        Returns:
            List of input strings for the stage
        """
        if stage == PipelineStage.SUBDOMAIN_ENUM:
            return [target]
        
        if stage == PipelineStage.DNS_RESOLUTION:
            return self.state.get_stage_output(PipelineStage.SUBDOMAIN_ENUM)
        
        if stage == PipelineStage.HTTP_PROBING:
            return self.state.get_stage_output(PipelineStage.DNS_RESOLUTION)
        
        if stage == PipelineStage.WEB_CRAWLING:
            return self.state.get_stage_output(PipelineStage.HTTP_PROBING)
        
        if stage == PipelineStage.URL_CLASSIFICATION:
            return self.state.get_stage_output(PipelineStage.WEB_CRAWLING)
        
        if stage == PipelineStage.VULN_SCANNING:
            # All classified URLs
            return self.state.get_stage_output(PipelineStage.URL_CLASSIFICATION)
        
        if stage == PipelineStage.XSS_TESTING:
            # XSS candidates from classification
            result = self.state.get_stage_result(PipelineStage.URL_CLASSIFICATION)
            if result and hasattr(result, "output_data"):
                # Parse classified URLs to get XSS candidates
                return self._filter_classified_urls(
                    result.output_data,
                    ClassificationGroup.XSS.value,
                )
            return []
        
        if stage == PipelineStage.SQLI_TESTING:
            result = self.state.get_stage_result(PipelineStage.URL_CLASSIFICATION)
            if result and hasattr(result, "output_data"):
                return self._filter_classified_urls(
                    result.output_data,
                    ClassificationGroup.SQLI.value,
                )
            return []
        
        if stage == PipelineStage.FUZZING:
            return self.state.get_stage_output(PipelineStage.URL_CLASSIFICATION)
        
        return []
    
    def _filter_classified_urls(
        self,
        classified_data: list[str],
        group: str,
    ) -> list[str]:
        """Filter classified URLs by group.
        
        Classification data is stored as JSON lines with url and groups.
        
        Args:
            classified_data: Classification output data
            group: Classification group to filter for
            
        Returns:
            List of URLs matching the group
        """
        urls = []
        for line in classified_data:
            try:
                data = json.loads(line)
                if group in data.get("groups", []):
                    urls.append(data.get("url", ""))
            except (json.JSONDecodeError, KeyError):
                continue
        return [u for u in urls if u]
    
    async def _execute_tool_stage(
        self,
        stage: PipelineStage,
        inputs: list[str],
    ) -> StageResult:
        """Execute a tool-based pipeline stage.
        
        Args:
            stage: Stage to execute
            inputs: Input data for tools
            
        Returns:
            StageResult with tool outputs
        """
        tools = STAGE_TOOL_MAP.get(stage, [])
        
        if not tools:
            return StageResult(
                stage=stage,
                status=StepStatus.SKIPPED,
                error="No tools configured for stage",
            )
        
        all_outputs: list[str] = []
        all_findings: list[Finding] = []
        output_path: Optional[Path] = None
        start_time = datetime.now()
        errors: list[str] = []
        audit_logger = self.state.get_audit_logger()
        
        for tool_name in tools:
            adapter = self.adapters.get(tool_name)
            
            if adapter is None:
                error_msg = f"Adapter not found for tool: {tool_name}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
            
            if not await adapter.check_available():
                error_msg = f"Tool not available: {tool_name}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
            
            try:
                tool_config = ToolConfig(
                    name=tool_name,
                    timeout=self.config.timeout,
                    rate_limit=self.config.rate_limit_per_host,
                )
                
                if audit_logger:
                    audit_logger.log_event(
                        AuditEventType.TOOL_START,
                        {
                            "tool": tool_name,
                            "stage": stage.value,
                            "input_count": len(inputs),
                        },
                    )
                
                result = await adapter.run(inputs, tool_config)
                
                if result.success:
                    outputs = self._parse_tool_output(result.stdout, tool_name)
                    all_outputs.extend(outputs)
                    
                    findings = adapter.parse_output(result.stdout)
                    all_findings.extend(findings)
                    
                    if output_path is None:
                        output_path = result.output_path
                    
                    if audit_logger:
                        audit_logger.log_event(
                            AuditEventType.TOOL_FINISH,
                            {
                                "tool": tool_name,
                                "stage": stage.value,
                                "success": True,
                                "finding_count": len(findings),
                                "output_count": len(outputs),
                                "duration": result.duration,
                            },
                        )
                    
                    logger.info(
                        f"Tool {tool_name} completed: "
                        f"{len(outputs)} outputs, {len(findings)} findings"
                    )
                else:
                    error_msg = f"Tool {tool_name} failed: exit={result.exit_code}"
                    if result.stderr:
                        error_msg += f" stderr={result.stderr[:200]}"
                    
                    if audit_logger:
                        audit_logger.log_event(
                            AuditEventType.TOOL_FINISH,
                            {
                                "tool": tool_name,
                                "stage": stage.value,
                                "success": False,
                                "finding_count": 0,
                                "exit_code": result.exit_code,
                                "error": error_msg,
                            },
                        )
                    
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    
            except ToolTimeoutError:
                error_msg = f"Tool {tool_name} timed out"
                logger.warning(error_msg)
                errors.append(error_msg)
            except ToolExecutionError as e:
                error_msg = f"Tool {tool_name} execution error: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error running {tool_name}: {e}"
                logger.exception(error_msg)
                errors.append(error_msg)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if all_outputs or all_findings:
            status = StepStatus.COMPLETED
            error = None
        elif not tools:
            status = StepStatus.SKIPPED
            error = "No tools configured"
        else:
            status = StepStatus.FAILED
            error = "; ".join(errors) if errors else "All tools failed without output"
        
        if all_outputs and output_path:
            combined_path = self.state.get_artifact_path(stage, "combined_output.txt")
            combined_path.write_text("\n".join(all_outputs))
            output_path = combined_path
        
        return StageResult(
            stage=stage,
            status=status,
            output_data=all_outputs,
            output_path=output_path,
            findings=all_findings,
            duration=duration,
            error=error,
        )
    
    async def _execute_classification_stage(
        self,
        stage: PipelineStage,
        inputs: list[str],
    ) -> StageResult:
        """Execute URL classification stage.
        
        This is an internal processing stage that doesn't use external tools.
        
        Args:
            stage: Classification stage
            inputs: URLs to classify
            
        Returns:
            StageResult with classified URLs
        """
        start_time = datetime.now()
        
        try:
            # Classify and group URLs
            groups = self.classifier.classify_deduplicate_and_group(inputs)
            
            # Build output data as JSON lines
            output_data: list[str] = []
            
            for url in inputs:
                result = self.classifier.classify(url)
                if result.groups:
                    output_data.append(json.dumps({
                        "url": url,
                        "groups": result.groups,
                        "confidence": result.confidence,
                    }))
            
            # Get statistics
            stats = self.classifier.get_statistics(inputs)
            logger.info(
                f"Classification complete: {stats['classified_urls']} URLs classified, "
                f"XSS: {stats.get('xss_candidates_count', 0)}, "
                f"SQLi: {stats.get('sqli_candidates_count', 0)}"
            )
            
            # Save classification output
            output_path = self.state.get_artifact_path(
                stage,
                "classified_urls.jsonl",
            )
            output_path.write_text("\n".join(output_data))
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return StageResult(
                stage=stage,
                status=StepStatus.COMPLETED,
                output_data=output_data,
                output_path=output_path,
                findings=[],
                duration=duration,
            )
            
        except Exception as e:
            logger.exception(f"Classification failed: {e}")
            return StageResult(
                stage=stage,
                status=StepStatus.FAILED,
                error=str(e),
                duration=(datetime.now() - start_time).total_seconds(),
            )
    
    def _parse_tool_output(self, stdout: str, tool_name: str) -> list[str]:
        """Parse tool stdout to extract output items.
        
        Args:
            stdout: Raw tool output
            tool_name: Name of the tool
            
        Returns:
            List of output items (subdomains, URLs, etc.)
        """
        outputs = []
        
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            
            # Try to parse as JSON
            try:
                data = json.loads(line)
                
                # Extract relevant field based on tool
                if tool_name == "subfinder":
                    outputs.append(data.get("host", ""))
                elif tool_name == "dnsx":
                    outputs.append(data.get("host", ""))
                elif tool_name == "httpx":
                    outputs.append(data.get("url", ""))
                elif tool_name in ("katana", "gau"):
                    outputs.append(data.get("url", "") or data.get("endpoint", ""))
                else:
                    # Generic extraction
                    for key in ("url", "host", "target", "endpoint"):
                        if key in data:
                            outputs.append(data[key])
                            break
                            
            except json.JSONDecodeError:
                # Treat as plain text line
                outputs.append(line.strip())
        
        return [o for o in outputs if o]
    
    async def run_single_tool(
        self,
        tool_name: str,
        inputs: list[str],
        *,
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """Run a single tool outside of the pipeline.
        
        Useful for ad-hoc tool execution or testing.
        
        Args:
            tool_name: Name of the tool to run
            inputs: Input data for the tool
            timeout: Optional timeout override
            
        Returns:
            ToolResult from tool execution
            
        Raises:
            ToolNotFoundError: If tool adapter not found
            ToolExecutionError: If tool execution fails
        """
        adapter = self.adapters.get(tool_name)
        
        if adapter is None:
            raise ToolNotFoundError(f"No adapter for tool: {tool_name}")
        
        if not await adapter.check_available():
            raise ToolNotFoundError(f"Tool not available: {tool_name}")
        
        config = ToolConfig(
            name=tool_name,
            timeout=timeout or self.config.timeout,
            rate_limit=self.config.rate_limit_per_host,
        )
        
        return await adapter.run(inputs, config)
    
    def get_available_stages(self) -> list[PipelineStage]:
        """Get list of stages that can be executed.
        
        Checks tool availability for each stage.
        
        Returns:
            List of available pipeline stages
        """
        available = []
        
        for stage in PipelineStage:
            tools = STAGE_TOOL_MAP.get(stage, [])
            
            # Internal stages are always available
            if not tools:
                available.append(stage)
                continue
            
            # Check if at least one tool is available
            for tool_name in tools:
                adapter = self.adapters.get(tool_name)
                if adapter is not None:
                    available.append(stage)
                    break
        
        return available
    
    @classmethod
    def create_standard_pipeline(
        cls,
        adapters: dict[str, ToolAdapter],
        target: str,
        profile: ScanProfile,
        scope: ScopeConfig,
        engagement_mode: EngagementMode = EngagementMode.BUG_BOUNTY,
    ) -> "PipelineOrchestrator":
        """Create a standard pipeline with common configuration.
        
        Factory method for easy pipeline creation.
        
        Args:
            adapters: Dictionary of tool adapters
            target: Target domain
            profile: Scan profile
            scope: Scope configuration
            engagement_mode: Engagement mode
            
        Returns:
            Configured PipelineOrchestrator instance
        """
        # Get rate limits for mode
        mode_limits = RATE_LIMITS.get(engagement_mode, RATE_LIMITS[EngagementMode.BUG_BOUNTY])
        
        # Determine stages from profile steps
        stages = []
        step_to_stage = {
            "subfinder": PipelineStage.SUBDOMAIN_ENUM,
            "dnsx": PipelineStage.DNS_RESOLUTION,
            "httpx": PipelineStage.HTTP_PROBING,
            "katana": PipelineStage.WEB_CRAWLING,
            "gau": PipelineStage.WEB_CRAWLING,
            "nuclei": PipelineStage.VULN_SCANNING,
            "dalfox": PipelineStage.XSS_TESTING,
            "ffuf": PipelineStage.FUZZING,
            "sqlmap": PipelineStage.SQLI_TESTING,
        }
        
        seen_stages = set()
        for step in profile.steps:
            stage = step_to_stage.get(step)
            if stage and stage not in seen_stages:
                stages.append(stage)
                seen_stages.add(stage)
        
        # Always add classification after crawling if we have vuln stages
        vuln_stages = {
            PipelineStage.VULN_SCANNING,
            PipelineStage.XSS_TESTING,
            PipelineStage.FUZZING,
            PipelineStage.SQLI_TESTING,
        }
        if any(s in vuln_stages for s in stages):
            # Insert classification before first vuln stage
            for i, stage in enumerate(stages):
                if stage in vuln_stages:
                    stages.insert(i, PipelineStage.URL_CLASSIFICATION)
                    break
        
        config = PipelineConfig(
            stages=stages,
            profile=profile,
            scope=scope,
            engagement_mode=engagement_mode,
            concurrency=mode_limits.get("concurrency", 10),
            rate_limit_global=mode_limits.get("global", 30),
            rate_limit_per_host=mode_limits.get("per_host", 5),
            timeout=profile.timeout,
        )
        
        run_config = RunConfig(
            target=target,
            profile=profile.name,
            scope_file=Path(),
            engagement_mode=engagement_mode,
            rate_limit_global=config.rate_limit_global,
            rate_limit_per_host=config.rate_limit_per_host,
            concurrency=config.concurrency,
            timeout=config.timeout,
            enabled_steps=profile.steps,
        )
        
        return cls(config, adapters, run_config=run_config)
    
    async def run_with_resume(
        self,
        target: str,
        resume_id: Optional[str] = None,
    ) -> RunStateManager:
        if resume_id and self.db:
            completed_steps = self.db.get_completed_step_names(resume_id)
            self.state = await RunStateManager.resume(
                resume_id,
                self.db,
                self.run_config,
            )
            logger.info(f"Resuming run {resume_id}, {len(completed_steps)} steps complete")
        else:
            completed_steps = set()
        
        if self._running:
            raise PipelineError("Pipeline is already running")
        
        self._running = True
        self._cancelled = False
        self.run_config.target = target
        
        try:
            await self.state.initialize()
            
            step_names = [stage.value for stage in self.config.stages]
            if not resume_id:
                self.state.register_steps(step_names)
            
            await self.scheduler.start()
            await self.state.start_run()
            
            logger.info(f"Starting pipeline for target: {target}")
            
            for stage in self.config.stages:
                if self._cancelled:
                    logger.info("Pipeline cancelled")
                    await self.state.cancel_run()
                    break
                
                if stage.value in completed_steps:
                    logger.info(f"Skipping completed step: {stage.value}")
                    continue
                
                await self._pause_event.wait()
                
                if not self._check_dependencies(stage):
                    logger.warning(f"Skipping {stage.value}: dependencies not met")
                    await self.state.skip_step(stage.value, "Dependencies not met")
                    continue
                
                try:
                    await self._execute_stage(stage, target)
                except Exception as e:
                    logger.error(f"Stage {stage.value} failed: {e}")
                    await self.state.fail_step(stage.value, str(e))
                    
                    if self.config.stop_on_failure:
                        await self.state.fail_run(str(e))
                        break
            
            if self.state.metadata.state.value == "running":
                await self.state.complete_run()
            
            logger.info(f"Pipeline completed: {self.state.metadata.total_findings} findings")
            
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            await self.state.fail_run(str(e))
            raise PipelineError(f"Pipeline execution failed: {e}") from e
        
        finally:
            self._running = False
            await self.scheduler.stop()
        
        return self.state
