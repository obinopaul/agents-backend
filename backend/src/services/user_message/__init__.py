# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
User Message Services Package.

This package provides services for processing user messages from the agent,
specifically handling attachments from the message_user tool.

Usage:
    from backend.src.services.user_message import user_message_subscriber
    
    # In agent.py on_tool_end handler:
    if tool_name == "message_user":
        enhanced = await user_message_subscriber.on_tool_complete(
            tool_name=tool_name,
            tool_result=tool_output,
            thread_id=thread_id,
            sandbox_download_func=sandbox_download,
        )
        if enhanced:
            tool_output = enhanced
"""

from .user_message_subscriber import (
    UserMessageSubscriber,
    user_message_subscriber,
    ProcessedAttachment,
    AttachmentProcessingResult,
    FileCategory,
    get_file_category,
    get_mime_type,
    is_remote_url,
)

__all__ = [
    # Main subscriber
    "UserMessageSubscriber",
    "user_message_subscriber",
    # Data classes
    "ProcessedAttachment",
    "AttachmentProcessingResult",
    # Utilities
    "FileCategory",
    "get_file_category",
    "get_mime_type",
    "is_remote_url",
]
