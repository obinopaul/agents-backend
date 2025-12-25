# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Configuration for the multi-agent template.

Provides centralized configuration for:
- LLM models
- Tool settings
- Workflow parameters
- Feature flags
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.core.conf import settings


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    
    name: str = "gpt-4o"
    provider: str = "openai"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    
    def __post_init__(self):
        """Load from environment if not set."""
        if self.api_key is None:
            if self.provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY", "")
                self.base_url = self.base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            elif self.provider == "anthropic":
                self.api_key = os.getenv("ANTHROPIC_API_KEY", "")


@dataclass
class ToolConfig:
    """Configuration for tool loading."""
    
    enable_mcp: bool = True
    enable_sandbox: bool = False
    mcp_timeout_seconds: int = 300
    sandbox_provider: str = "e2b"  # e2b or daytona
    
    # Tool filtering
    allowed_tools: List[str] = field(default_factory=list)  # Empty = all tools
    blocked_tools: List[str] = field(default_factory=list)  # Tools to exclude
    
    # Sandbox settings
    sandbox_mcp_port: int = 6060
    sandbox_code_port: int = 9000


@dataclass
class WorkflowConfig:
    """Configuration for workflow behavior."""
    
    # Iteration limits
    max_plan_iterations: int = 3
    max_step_retries: int = 2
    max_total_steps: int = 10
    
    # Feature flags
    enable_planning: bool = True
    enable_review: bool = True
    enable_human_approval: bool = False
    auto_approve_plans: bool = True
    
    # Timeouts
    node_timeout_seconds: int = 120
    total_timeout_seconds: int = 600


@dataclass
class AgentConfig:
    """
    Complete configuration for the multi-agent template.
    
    Usage:
        config = AgentConfig()
        config.model.name = "claude-3-sonnet"
        config.workflow.max_plan_iterations = 5
    """
    
    model: ModelConfig = field(default_factory=ModelConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    
    # Node-specific model overrides (optional)
    planner_model: Optional[ModelConfig] = None
    executor_model: Optional[ModelConfig] = None
    reviewer_model: Optional[ModelConfig] = None
    
    @classmethod
    def from_settings(cls) -> "AgentConfig":
        """Create config from application settings."""
        # Determine model name based on provider
        provider = getattr(settings, "LLM_PROVIDER", "openai")
        model_names = {
            "openai": getattr(settings, "OPENAI_MODEL", "gpt-4o"),
            "anthropic": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "gemini": getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash"),
            "deepseek": getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
            "groq": getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant"),
            "huggingface": getattr(settings, "HUGGINGFACE_REPO_ID", "microsoft/Phi-3-mini-4k-instruct"),
            "ollama": getattr(settings, "OLLAMA_MODEL", "llama3"),
            "openai_compat": getattr(settings, "OPENAI_COMPAT_MODEL", ""),
        }
        
        return cls(
            model=ModelConfig(
                name=model_names.get(provider, "gpt-4o"),
                provider=provider,
                temperature=getattr(settings, "LLM_TEMPERATURE", 0.7),
            ),
            tools=ToolConfig(
                enable_mcp=getattr(settings, "AGENT_MCP_ENABLED", True),
                mcp_timeout_seconds=getattr(settings, "AGENT_MCP_TIMEOUT_SECONDS", 300),
                sandbox_provider=getattr(settings, "SANDBOX_PROVIDER", "e2b"),
            ),
            workflow=WorkflowConfig(
                max_plan_iterations=getattr(settings, "AGENT_MAX_PLAN_ITERATIONS", 3),
                max_total_steps=getattr(settings, "AGENT_MAX_STEP_NUM", 10),
            ),
        )
    
    def get_model_for_node(self, node_name: str) -> ModelConfig:
        """Get the model config for a specific node."""
        if node_name == "planner" and self.planner_model:
            return self.planner_model
        if node_name == "executor" and self.executor_model:
            return self.executor_model
        if node_name == "reviewer" and self.reviewer_model:
            return self.reviewer_model
        return self.model


# Default configuration instance
default_config = AgentConfig()
