# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""Prompts exports for the multi-agent template."""

from backend.src.agent_template.prompts.coordinator import COORDINATOR_SYSTEM_PROMPT
from backend.src.agent_template.prompts.planner import PLANNER_SYSTEM_PROMPT
from backend.src.agent_template.prompts.executor import EXECUTOR_SYSTEM_PROMPT
from backend.src.agent_template.prompts.reviewer import REVIEWER_SYSTEM_PROMPT
from backend.src.agent_template.prompts.reporter import REPORTER_SYSTEM_PROMPT

__all__ = [
    "COORDINATOR_SYSTEM_PROMPT",
    "PLANNER_SYSTEM_PROMPT",
    "EXECUTOR_SYSTEM_PROMPT",
    "REVIEWER_SYSTEM_PROMPT",
    "REPORTER_SYSTEM_PROMPT",
]
