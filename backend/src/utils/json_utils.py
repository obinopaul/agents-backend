# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import json
import logging
import re
from typing import Any

import json_repair

logger = logging.getLogger(__name__)


# =============================================================================
# Safe JSON Serialization for Complex Objects
# =============================================================================

def make_serializable(obj: Any, seen: set = None) -> Any:
    """Recursively convert any object to a JSON-serializable form.
    
    This is a defensive serializer that NEVER raises exceptions.
    It handles:
    - Pydantic models (v1 and v2)
    - LangChain objects (ToolMessage, BaseTool, etc.)
    - Bytes, sets, tuples
    - Circular references
    - Any edge case with graceful fallback
    
    Args:
        obj: Any Python object
        seen: Set of id() values to detect circular references
        
    Returns:
        JSON-serializable representation
    """
    if seen is None:
        seen = set()
    
    # Handle None and primitives (most common case, fast path)
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float, str)):
        return obj
    
    # Detect circular references
    obj_id = id(obj)
    if obj_id in seen:
        return f"<circular ref: {type(obj).__name__}>"
    
    # Handle common iterables
    if isinstance(obj, (list, tuple)):
        seen.add(obj_id)
        return [make_serializable(item, seen) for item in obj]
    
    if isinstance(obj, set):
        seen.add(obj_id)
        return [make_serializable(item, seen) for item in obj]
    
    if isinstance(obj, dict):
        seen.add(obj_id)
        result = {}
        for k, v in obj.items():
            # Skip private/internal keys
            str_key = str(k) if not isinstance(k, str) else k
            if str_key.startswith('_'):
                continue
            result[str_key] = make_serializable(v, seen)
        return result
    
    # Handle bytes
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8', errors='replace')
        except Exception:
            return f"<bytes: {len(obj)} bytes>"
    
    # ── Handle LangChain message types BEFORE generic model_dump ──────
    # LangChain messages (ToolMessage, AIMessage, HumanMessage, etc.) are
    # Pydantic v2 models. If we call model_dump() on them, we get the FULL
    # message dict (content, type, tool_call_id, response_metadata, etc.)
    # which (a) can trigger false circular-ref detection due to id() reuse
    # in CPython, and (b) produces verbose output that pollutes downstream
    # consumers expecting just the message content.
    #
    # Detection: LangChain BaseMessage subclasses have both 'content' and
    # 'response_metadata' attrs. This is specific enough to avoid matching
    # arbitrary Pydantic models.
    if (hasattr(obj, 'content') and hasattr(obj, 'response_metadata')
            and hasattr(obj, 'model_dump')):
        try:
            seen.add(obj_id)
            return make_serializable(obj.content, seen)
        except Exception:
            pass

    # Handle Pydantic v2 models (most common in FastAPI)
    if hasattr(obj, 'model_dump'):
        try:
            seen.add(obj_id)
            return make_serializable(obj.model_dump(), seen)
        except Exception:
            pass
    
    # Handle Pydantic v1 models
    if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
        try:
            seen.add(obj_id)
            return make_serializable(obj.dict(), seen)
        except Exception:
            pass
    
    # Handle objects with content attribute (generic fallback)
    if hasattr(obj, 'content'):
        try:
            return make_serializable(obj.content, seen)
        except Exception:
            pass
    
    # Handle objects with __dict__ (general Python objects)
    if hasattr(obj, '__dict__'):
        try:
            seen.add(obj_id)
            # Filter out private attrs and callables
            public_attrs = {
                k: v for k, v in obj.__dict__.items()
                if not k.startswith('_') and not callable(v)
            }
            if public_attrs:
                return make_serializable(public_attrs, seen)
        except Exception:
            pass
    
    # Handle callables/functions
    if callable(obj):
        return f"<{type(obj).__name__}>"
    
    # Ultimate fallback - type name (never raises)
    return f"<{type(obj).__name__}>"


def safe_json_serialize(data: Any, ensure_ascii: bool = False) -> str:
    """Safely serialize any data to JSON string.
    
    This function NEVER raises an exception. It handles all edge cases
    including ToolMessage, ToolRuntime, complex LangChain objects, 
    Pydantic models, and circular references.
    
    Args:
        data: Any Python object or data structure
        ensure_ascii: Whether to escape non-ASCII characters (default: False)
        
    Returns:
        JSON string representation (always succeeds)
    """
    try:
        # First pass: make everything serializable
        serializable = make_serializable(data)
        # Second pass: dump to JSON
        return json.dumps(serializable, ensure_ascii=ensure_ascii)
    except Exception as e:
        # Absolute fallback - should never reach here
        logger.warning(f"JSON serialization fallback triggered: {e}")
        return json.dumps({"error": f"Serialization fallback: {str(data)[:200]}"})


def sanitize_args(args: Any) -> str:
    """
    Sanitize tool call arguments to prevent special character issues.

    Args:
        args: Tool call arguments string

    Returns:
        str: Sanitized arguments string
    """
    if not isinstance(args, str):
        return ""
    else:
        return (
            args.replace("[", "&#91;")
            .replace("]", "&#93;")
            .replace("{", "&#123;")
            .replace("}", "&#125;")
        )


def _extract_json_from_content(content: str) -> str:
    """
    Extract valid JSON from content that may have extra tokens.
    
    Attempts to find the last valid JSON closing bracket and truncate there.
    Handles both objects {} and arrays [].
    
    Args:
        content: String that may contain JSON with extra tokens
        
    Returns:
        String with potential JSON extracted or original content
    """
    content = content.strip()
    
    # Try to find a complete JSON object or array
    # Look for the last closing brace/bracket that could be valid JSON
    
    # Track counters and whether we've seen opening brackets
    brace_count = 0
    bracket_count = 0
    seen_opening_brace = False
    seen_opening_bracket = False
    in_string = False
    escape_next = False
    last_valid_end = -1
    
    for i, char in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == '{':
            brace_count += 1
            seen_opening_brace = True
        elif char == '}':
            brace_count -= 1
            # Only mark as valid end if we started with opening brace and reached balanced state
            if brace_count == 0 and seen_opening_brace:
                last_valid_end = i
        elif char == '[':
            bracket_count += 1
            seen_opening_bracket = True
        elif char == ']':
            bracket_count -= 1
            # Only mark as valid end if we started with opening bracket and reached balanced state
            if bracket_count == 0 and seen_opening_bracket:
                last_valid_end = i
    
    if last_valid_end > 0:
        truncated = content[:last_valid_end + 1]
        if truncated != content:
            logger.debug(f"Truncated content from {len(content)} to {len(truncated)} chars")
        return truncated
    
    return content


def repair_json_output(content: str) -> str:
    """
    Repair and normalize JSON output.

    Handles:
    - JSON with extra tokens after closing brackets
    - Incomplete JSON structures
    - Malformed JSON from quantized models
    
    Args:
        content (str): String content that may contain JSON

    Returns:
        str: Repaired JSON string, or original content if not JSON
    """
    content = content.strip()
    
    if not content:
        return content

    # First attempt: try to extract valid JSON if there are extra tokens
    content = _extract_json_from_content(content)

    try:
        # Try to repair and parse JSON
        repaired_content = json_repair.loads(content)
        if not isinstance(repaired_content, dict) and not isinstance(
            repaired_content, list
        ):
            logger.warning("Repaired content is not a valid JSON object or array.")
            return content
        content = json.dumps(repaired_content, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"JSON repair failed: {e}")

    return content


def sanitize_tool_response(content: str, max_length: int = 50000) -> str:
    """
    Sanitize tool response to remove extra tokens and invalid content.
    
    This function:
    - Strips whitespace and trailing tokens
    - Truncates excessively long responses
    - Cleans up common garbage patterns
    - Attempts JSON repair for JSON-like responses
    
    Args:
        content: Tool response content
        max_length: Maximum allowed length (default 50000 chars)
        
    Returns:
        Sanitized content string
    """
    if not content:
        return content
    
    content = content.strip()
    
    # First, try to extract valid JSON to remove trailing tokens
    if content.startswith('{') or content.startswith('['):
        content = _extract_json_from_content(content)
    
    # Truncate if too long to prevent token overflow
    if len(content) > max_length:
        logger.warning(f"Tool response truncated from {len(content)} to {max_length} chars")
        content = content[:max_length].rstrip() + "..."
    
    # Remove common garbage patterns that appear from some models
    # These are often seen from quantized models with output corruption
    garbage_patterns = [
        r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]',  # Control characters
    ]
    
    for pattern in garbage_patterns:
        content = re.sub(pattern, '', content)
    
    return content
