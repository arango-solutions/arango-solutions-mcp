"""
Main reasoner agent for job processing
"""
import time
import json
import re
from typing import Optional, Dict, Any
from datetime import datetime

from reasoner_pod.core.models import Job, JobStatus, JobStep
from reasoner_pod.clients.opencode import OpenCodeClient
from reasoner_pod.config import settings
from reasoner_pod.utils.logging import get_logger, job_id_var
from reasoner_pod.utils.metrics import metrics

logger = get_logger(__name__)


class ReasonerAgent:
    """
    Main reasoning agent that orchestrates job execution
    
    Phases:
    1. Planning - Create step-by-step execution plan
    2. Execution - Execute plan steps with tool calling
    3. Synthesis - Generate final user-friendly result
    """
    
    def __init__(self, opencode_client: OpenCodeClient):
        """
        Initialize reasoner agent
        
        Args:
            opencode_client: OpenCode client for LLM interactions
        """
        self.opencode = opencode_client
        logger.info("ReasonerAgent initialized")
    
    async def process_job(self, job: Job) -> Job:
        """
        Process job with global MCP (verify availability before starting)
        
        Args:
            job: Job to process
            
        Returns:
            Processed job with results
        """
        # Set job ID in context for logging
        job_id_var.set(job.job_id)
        
        logger.info(f"🚀 Starting job processing: {job.job_id}")
        
        try:
            # Step 1: Create OpenCode session for this job
            session_id = await self.opencode.create_session(
                title=f"Job: {job.job_id[:8]}"
            )
            job.opencode_session_id = session_id
            logger.info(f"✅ Session created: {session_id}")
            
            # Step 2: Planning with plan agent
            await self._planning_phase(job)
            
            # Step 3: Execution with build agent
            await self._execution_phase(job)
            
            # Step 4: Synthesis (mandatory)
            await self._synthesis_phase(job)
            
            # Mark as completed
            job.update_status(JobStatus.COMPLETED)
            logger.info(f"✅ Job completed: {job.job_id}")
            
            # Record metrics
            if job.duration_seconds:
                metrics.record_job_completed(JobStatus.COMPLETED, job.duration_seconds)
        
        except Exception as e:
            # Fail job immediately with clear error
            job.update_status(JobStatus.FAILED)
            job.error = str(e)
            logger.error(
                f"❌ Job failed: {job.job_id}",
                extra={
                    "error": str(e),
                    "job_id": job.job_id
                },
                exc_info=True
            )
            
            # Record metrics
            if job.duration_seconds:
                metrics.record_job_completed(JobStatus.FAILED, job.duration_seconds)
        
        finally:
            # Cleanup: Delete session
            try:
                if job.opencode_session_id:
                    await self.opencode.delete_session(job.opencode_session_id)
                    logger.info(f"🧹 Session deleted: {job.opencode_session_id}")
            except Exception as e:
                logger.warning(f"⚠️ Session cleanup failed: {e}")
        
        return job
    
    async def _planning_phase(self, job: Job) -> None:
        """
        Planning phase using OpenCode's plan agent
        
        Args:
            job: Job to plan
        """
        job.update_status(JobStatus.PLANNING)
        logger.info(f"📋 Planning phase started for job {job.job_id}")
        
        try:
            from reasoner_pod.config import settings
            model_config = {
                "providerID": settings.opencode_provider,
                "modelID": settings.opencode_model
            }
            
            # Use OpenCode's plan agent with user's raw query
            logger.info(f"🤖 Calling plan agent with user request")
            response = await self.opencode.send_message(
                content=job.user_request,  # Just the user's question
                model=model_config,
                agent="plan"  # OpenCode's plan agent
            )
            
            # Extract plan text from response
            plan_text = self._extract_text_from_parts(response.get("parts", []))
            
            if not plan_text:
                raise ValueError("Plan agent returned empty response")
            
            logger.info(
                f"📝 Plan received from agent",
                extra={
                    "plan_length": len(plan_text),
                    "plan_preview": plan_text[:500] if len(plan_text) > 500 else plan_text
                }
            )
            
            # Parse plan into steps for API display
            job.plan = self._parse_plan(plan_text)
            
            logger.info(
                f"📋 Plan parsed into {len(job.plan)} steps",
                extra={"parsed_steps": job.plan}
            )
            
            # Store raw plan text for build agent (pass raw text, not parsed)
            job.context = job.context or {}
            job.context["plan_text"] = plan_text
            
            logger.info(
                f"✅ Planning complete",
                extra={
                    "parsed_steps": len(job.plan),
                    "plan_preview": plan_text[:200] + "..." if len(plan_text) > 200 else plan_text
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Planning phase failed: {e}", exc_info=True)
            raise
    
    async def _execution_phase(self, job: Job) -> None:
        """
        Execution phase using OpenCode's build agent
        
        Args:
            job: Job to execute
        """
        job.update_status(JobStatus.EXECUTING)
        logger.info(f"🔨 Execution phase started for job {job.job_id}")
        
        if not job.plan:
            raise ValueError("No plan available for execution")
        
        # Get raw plan text from context (pass to build agent as-is)
        plan_text = job.context.get("plan_text", "") if job.context else ""
        
        if not plan_text:
            raise ValueError("Plan text not found in job context")
        
        try:
            start_time = time.time()
            
            from reasoner_pod.config import settings
            model_config = {
                "providerID": settings.opencode_provider,
                "modelID": settings.opencode_model
            }
            
            # Use OpenCode's build agent with raw plan text
            logger.info(f"🤖 Calling build agent with plan")
            response = await self.opencode.send_message(
                content=plan_text,  # Raw plan text from plan agent
                model=model_config,
                agent="build"  # OpenCode's build agent
            )
            
            # Extract execution result
            execution_text = self._extract_text_from_parts(response.get("parts", []))
            
            if not execution_text:
                raise ValueError("Build agent returned empty response")
            
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            logger.info(
                f"✅ Build agent execution complete",
                extra={
                    "result_length": len(execution_text),
                    "duration_ms": duration_ms
                }
            )
            
            # Create execution step
            step = JobStep(
                step_num=1,
                description="Executed plan using OpenCode build agent with MCP tools",
                tool_used="opencode_build_agent",
                result=execution_text,
                duration_ms=duration_ms
            )
            job.add_step(step)
            metrics.record_job_step()
            
            # Store execution result in context for synthesis
            job.context = job.context or {}
            job.context["execution_result"] = execution_text
            
        except Exception as e:
            logger.error(f"❌ Execution phase failed: {e}", exc_info=True)
            raise
    
    async def _synthesis_phase(self, job: Job) -> None:
        """
        Synthesis phase - generate user-friendly summary (mandatory)
        
        Args:
            job: Job to synthesize
        """
        logger.info(f"✨ Synthesis phase started for job {job.job_id}")
        
        # Get execution result from context
        execution_result = job.context.get("execution_result", "") if job.context else ""
        
        if not execution_result:
            execution_result = job.steps[0].result if job.steps else "No execution results"
        
        synthesis_prompt = f"""Provide a clear, user-friendly summary of the results.

Original Request: {job.user_request}

Execution Result:
{execution_result}

Generate a concise, well-formatted summary that directly answers the user's question."""
        
        try:
            from reasoner_pod.config import settings
            model_config = {
                "providerID": settings.opencode_provider,
                "modelID": settings.opencode_model
            }
            
            # Regular message (no agent parameter for synthesis)
            response = await self.opencode.send_message(
                content=synthesis_prompt,
                model=model_config
                # No agent parameter - regular assistant response
            )
            
            result_text = self._extract_text_from_parts(response.get("parts", []))
            
            if not result_text:
                # Fallback to execution result if synthesis fails
                logger.warning("Synthesis returned empty, using execution result")
                result_text = execution_result
            
            job.final_result = result_text
            
            logger.info(
                f"✅ Synthesis complete",
                extra={"result_length": len(result_text)}
            )
            
        except Exception as e:
            logger.error(f"❌ Synthesis failed: {e}", exc_info=True)
            # Don't fail the job, use execution result as fallback
            job.final_result = execution_result
            logger.warning("Using execution result as final result due to synthesis failure")
    
    def _extract_text_from_parts(self, parts: list[dict]) -> str:
        """Extract text content from message parts"""
        text_parts = [
            part.get("text", "")
            for part in parts
            if part.get("type") == "text"
        ]
        return "\n".join(text_parts)
    
    def _parse_plan(self, plan_text: str) -> list[str]:
        """
        Parse numbered plan from text
        
        Handles formats like:
        1. Step one
        2. Step two
        
        Or:
        1. **Step one**:
           - Details
        2. **Step two**:
           - Details
        """
        lines = plan_text.split('\n')
        plan = []
        
        for line in lines:
            line = line.strip()
            # Look for numbered lines (1., 2., 3., etc.)
            if line and any(line.startswith(f"{i}.") for i in range(1, 100)):
                # Remove number prefix and extract main step (before colon or newline)
                step_text = line.split('.', 1)[1].strip()
                
                # If step has bold formatting like **Step**: remove it
                if step_text.startswith('**'):
                    # Extract text between ** and optional :
                    if '**:' in step_text:
                        step_text = step_text.split('**:')[0].replace('**', '').strip()
                    elif '**' in step_text[2:]:
                        step_text = step_text.split('**')[1].strip()
                
                # Remove trailing colon if present
                if step_text.endswith(':'):
                    step_text = step_text[:-1].strip()
                
                if step_text:
                    plan.append(step_text)
        
        # Fallback: if no numbered items found, try to extract meaningful lines
        if not plan and plan_text.strip():
            # Look for lines starting with - or * (bullet points)
            for line in lines:
                line = line.strip()
                if line.startswith('-') or line.startswith('*'):
                    step = line.lstrip('-*').strip()
                    if step and len(step) > 10:  # Avoid very short lines
                        plan.append(step)
            
            # If still no plan, use first few meaningful lines
            if not plan:
                meaningful_lines = [l.strip() for l in lines if len(l.strip()) > 20]
                plan = meaningful_lines[:5] if meaningful_lines else [plan_text.strip()[:200]]
        
        return plan
    
    def _extract_steps_from_messages(self, messages: list[dict]) -> list[JobStep]:
        """Extract execution steps from message history"""
        steps = []
        step_num = 1
        
        for msg in messages:
            parts = msg.get("parts", [])
            
            for part in parts:
                part_type = part.get("type")
                
                if part_type == "tool_call":
                    # Tool was called
                    tool_data = part.get("tool", {})
                    tool_name = tool_data.get("name", "unknown")
                    tool_input = tool_data.get("input", {})
                    
                    steps.append(JobStep(
                        step_num=step_num,
                        description=f"Execute {tool_name}",
                        tool_used=tool_name,
                        tool_input=tool_input,
                        result="(pending)",
                        duration_ms=0
                    ))
                    step_num += 1
                
                elif part_type == "tool_result":
                    # Update last step with result
                    if steps and steps[-1].result == "(pending)":
                        steps[-1].result = str(part.get("result", ""))
        
        return steps
    
    def _format_steps(self, steps: list[JobStep]) -> str:
        """Format steps for display"""
        if not steps:
            return "No steps executed"
        
        formatted = []
        for step in steps:
            formatted.append(
                f"Step {step.step_num}: {step.description}"
                f"{f' (tool: {step.tool_used})' if step.tool_used else ''}"
                f" -> {step.result[:100]}..."
            )
        
        return "\n".join(formatted)


