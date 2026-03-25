# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Command handler factory.

Registry for command handlers that routes incoming messages to the appropriate handler.
"""

import logging
from typing import Dict, Optional

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)
from backend.common.log import log

logger = logging.getLogger(__name__)


class CommandHandlerFactory:
    """
    Factory for managing command handlers.
    
    This class maintains a registry of command handlers and provides
    methods to retrieve the appropriate handler for a given command type.
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        """
        Initialize the command handler factory.
        
        :param sio: Socket.IO server instance
        """
        self._sio = sio
        self._handlers: Dict[UserCommandType, CommandHandler] = {}
        self._initialize_handlers()

    def _initialize_handlers(self) -> None:
        """Initialize all command handlers with their dependencies."""
        # Import handlers here to avoid circular imports
        from backend.common.socketio.command.ping_handler import PingHandler
        from backend.common.socketio.command.cancel_handler import CancelHandler
        from backend.common.socketio.command.sandbox_status_handler import SandboxStatusHandler
        from backend.common.socketio.command.awake_sandbox_handler import AwakeSandboxHandler
        from backend.common.socketio.command.workspace_info_handler import WorkspaceInfoHandler
        from backend.common.socketio.command.query_handler import QueryHandler
        from backend.common.socketio.command.enhance_prompt_handler import EnhancePromptHandler
        from backend.common.socketio.command.publish_handler import PublishProjectHandler

        self._handlers = {
            UserCommandType.PING: PingHandler(self._sio),
            UserCommandType.CANCEL: CancelHandler(self._sio),
            UserCommandType.SANDBOX_STATUS: SandboxStatusHandler(self._sio),
            UserCommandType.AWAKE_SANDBOX: AwakeSandboxHandler(self._sio),
            UserCommandType.WORKSPACE_INFO: WorkspaceInfoHandler(self._sio),
            UserCommandType.QUERY: QueryHandler(self._sio),
            UserCommandType.ENHANCE_PROMPT: EnhancePromptHandler(self._sio),
            UserCommandType.PUBLISH_PROJECT: PublishProjectHandler(self._sio),
        }

        logger.info(f"Initialized {len(self._handlers)} command handlers")

    def get_handler(self, command_type: UserCommandType) -> Optional[CommandHandler]:
        """
        Get handler for a specific command type.
        
        :param command_type: Command type enum value
        :return: CommandHandler or None if not found
        """
        return self._handlers.get(command_type)

    def get_handler_by_string(self, command_type_str: str) -> Optional[CommandHandler]:
        """
        Get handler by command type string.
        
        :param command_type_str: Command type as string (e.g., 'query', 'ping')
        :return: CommandHandler or None if not found
        """
        if not command_type_str:
            return None
            
        try:
            command_type = UserCommandType(command_type_str)
            return self.get_handler(command_type)
        except ValueError:
            logger.warning(f"Unknown command type: {command_type_str}")
            return None

    def register_handler(
        self, 
        command_type: UserCommandType, 
        handler: CommandHandler
    ) -> None:
        """
        Register a new command handler.
        
        :param command_type: Command type to register for
        :param handler: Handler instance
        """
        self._handlers[command_type] = handler
        logger.debug(f"Registered handler for {command_type.value}")

    def get_available_commands(self) -> list[str]:
        """
        Get list of available command types.
        
        :return: List of command type strings
        """
        return [cmd.value for cmd in self._handlers.keys()]
