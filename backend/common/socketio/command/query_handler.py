# Copyright (c) 2025
# SPDX-License-Identifier: MIT

"""
Handler for query command - the main chat message handler.

Routes messages to either:
- chat.py logic (no sandbox) for AgentType.CHAT
- agent.py logic (with sandbox) for all other AgentTypes
"""

import logging
import os
import uuid
import asyncio
import json
from typing import Dict, Any, Optional, List, Tuple

import socketio

from backend.common.socketio.command.base_handler import (
    CommandHandler,
    UserCommandType,
)
from backend.common.socketio.command.cancel_handler import (
    set_task_running,
    should_cancel,
)
from backend.database.db import async_db_session
from backend.app.agent.crud.crud_chat_session import chat_session_dao
from backend.app.agent.crud.crud_chat_event import chat_event_dao
from backend.app.agent.service.chat_session_service import chat_session_service
from backend.app.agent.model.chat_session import AgentType
from backend.app.agent.model.chat_event import ChatEventType
from backend.core.conf import settings

# Import II-Agent WebSocket Event Adapter for frontend compatibility
from backend.app.agent.event_adapter import (
    IIAgentWebSocketAdapter,
    transform_sse_to_websocket,
)

# Import billing integration for credit checking
from backend.src.billing.credits.integration import BillingIntegration

logger = logging.getLogger(__name__)

# Default model for billing when model_id not specified
DEFAULT_BILLING_MODEL = "gpt-4"


class QueryHandler(CommandHandler):
    """
    Handler for query command (user chat messages).

    This is the main handler that:
    1. Receives user messages via Socket.IO
    2. Determines if sandbox is needed based on agent_type
    3. Routes to:
       - chat.py logic (no sandbox) for AgentType.CHAT
       - agent.py logic (with sandbox) for all other types
    4. Streams events back to the client
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        super().__init__(sio=sio)

    def get_command_type(self) -> UserCommandType:
        return UserCommandType.QUERY

    async def _get_user_uuid(self, user_id: int) -> Optional[str]:
        """
        Get user's UUID from their integer user_id.

        The billing system uses UUIDs (account_id) while the WebSocket
        handler receives integer user_id. This method bridges the gap.

        :param user_id: Integer user ID
        :return: User's UUID string, or None if user not found
        """
        try:
            from backend.app.admin.crud.crud_user import user_dao

            async with async_db_session() as db:
                user = await user_dao.get(db, user_id)
                if user:
                    return user.uuid
                logger.warning(f"User not found for id: {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting user UUID for {user_id}: {e}")
            return None

    async def _check_credits_and_billing(
        self,
        user_id: int,
        model_id: Optional[str],
        sid: str,
        run_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-flight check for credits and billing before running agent.

        Validates:
        1. User has a billing account
        2. User has access to the requested model
        3. User has sufficient credits

        :param user_id: User's integer ID
        :param model_id: Requested model ID (optional)
        :param sid: Socket.IO session ID for error reporting
        :param run_id: Run ID for error reporting
        :return: Tuple of (can_proceed: bool, user_uuid: Optional[str])
        """
        # Get user UUID for billing
        user_uuid = await self._get_user_uuid(user_id)

        if not user_uuid:
            await self.send_error(
                room=sid,
                message="User account not found. Please contact support.",
                run_id=run_id
            )
            return False, None

        # Check billing and model access
        try:
            # Use provided model_id or default
            billing_model = model_id or DEFAULT_BILLING_MODEL

            can_run, message, details = await BillingIntegration.check_model_and_billing_access(
                account_id=user_uuid,
                model_name=billing_model,
                estimated_cost=None  # No estimate, just check balance
            )

            if not can_run:
                error_type = details.get('error_type', 'unknown')

                # Emit specific error event for billing issues
                await self.broadcast_to_session(
                    session_uuid=sid,  # Send to specific client
                    event_type='billing_error',
                    content={
                        'message': message,
                        'error_type': error_type,
                        'details': details,
                    },
                    run_id=run_id
                )

                # Also send standard error
                await self.send_error(
                    room=sid,
                    message=message,
                    run_id=run_id
                )

                logger.warning(
                    f"Billing check failed for user {user_id} (uuid: {user_uuid}): "
                    f"{message} [type: {error_type}]"
                )
                return False, user_uuid

            logger.debug(f"Billing check passed for user {user_id}: {message}")
            return True, user_uuid

        except Exception as e:
            # Fail open - allow operation if billing check errors
            # This prevents blocking users due to temporary billing system issues
            logger.error(f"Billing check error for user {user_id}: {e}", exc_info=True)
            logger.warning(f"Allowing operation despite billing check error (fail-open)")
            return True, user_uuid

    async def handle(
        self,
        content: Dict[str, Any],
        session_uuid: str,
        user_id: int,
        sid: str
    ) -> None:
        """
        Handle user query (chat message).
        
        Routes to appropriate backend logic based on agent_type:
        - "chat" -> chat.py (no sandbox)
        - Any other type -> agent.py (with sandbox)
        
        :param content: Contains 'message', optional 'files', 'agent_type', etc.
        :param session_uuid: Session UUID
        :param user_id: User ID
        :param sid: Socket.IO session ID
        """
        message = content.get('message', '') or content.get('text', '')
        files = content.get('files', [])
        agent_type_str = content.get('agent_type', 'general')
        model_id = content.get('model_id')
        resources = content.get('resources', [])
        locale = content.get('locale', 'en-US')
        
        if not message and not files:
            await self.send_error(
                room=sid,
                message="No message or files provided"
            )
            return
        
        # Generate run_id for this agent invocation
        run_id = str(uuid.uuid4())
        
        # Determine if this requires sandbox
        try:
            agent_type = AgentType(agent_type_str)
            requires_sandbox = agent_type.requires_sandbox
        except ValueError:
            # Default to CHAT (no sandbox) if invalid type
            agent_type = AgentType.CHAT
            requires_sandbox = False
        
        try:
            # Mark task as running
            set_task_running(session_uuid, True)
            
            # Send status update
            await self.send_status_update(
                room=session_uuid,
                status='running',
                run_id=run_id
            )
            
            # Store user message event and update session
            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, session_uuid)
                
                if not session:
                    await self.send_error(room=sid, message="Session not found")
                    return
                
                # Create user message event
                await chat_event_dao.create_user_message(
                    db=db,
                    session_id=session.id,
                    text=message,
                    file_ids=files if files else None,
                    run_id=run_id
                )
                
                # Update session name from first message
                session_name_updated = False
                new_session_name = None
                if not session.name and message:
                    new_session_name = message[:50] + ("..." if len(message) > 50 else "")
                    await chat_session_dao.update_name(db, session.id, new_session_name)
                    session_name_updated = True
                
                # Update agent type if changed
                if agent_type_str and session.agent_type != agent_type_str:
                    session.agent_type = agent_type_str

                await db.commit()

            # Emit session_updated event if name was set
            # This allows frontend to update session list in real-time
            if session_name_updated and new_session_name:
                await self.broadcast_to_session(
                    session_uuid=session_uuid,
                    event_type='session_updated',
                    content={
                        'session_id': session_uuid,
                        'name': new_session_name,
                    },
                    run_id=run_id
                )

            # Emit USER_MESSAGE event to frontend
            # This informs the frontend that the user's message was received
            # and allows it to display the message in the chat history immediately.
            # Must be emitted BEFORE processing to maintain correct event order.
            await self.broadcast_to_session(
                session_uuid=session_uuid,
                event_type='user_message',
                content={
                    'text': message,
                    'files': files if files else [],
                },
                run_id=run_id
            )

            # =====================================================
            # PRE-FLIGHT BILLING CHECK
            # Check credits and model access before running agent
            # =====================================================
            can_proceed, user_uuid = await self._check_credits_and_billing(
                user_id=user_id,
                model_id=model_id,
                sid=sid,
                run_id=run_id
            )

            if not can_proceed:
                # Credit check failed - error already sent to client
                # Update status back to idle and return
                await self.send_status_update(
                    room=session_uuid,
                    status='idle',
                    run_id=run_id
                )
                return

            # Notify that we're processing
            await self.broadcast_to_session(
                session_uuid=session_uuid,
                event_type='processing',
                content={
                    'message': f'Processing with {"chat" if not requires_sandbox else agent_type_str} mode...',
                    'run_id': run_id,
                    'requires_sandbox': requires_sandbox,
                },
                run_id=run_id
            )

            # Route to appropriate backend logic
            if requires_sandbox:
                # Route to agent.py logic (with sandbox)
                await self._run_agent_with_sandbox(
                    session_uuid=session_uuid,
                    user_id=user_id,
                    message=message,
                    files=files,
                    agent_type=agent_type,
                    model_id=model_id,
                    resources=resources,
                    locale=locale,
                    run_id=run_id,
                    sid=sid
                )
            else:
                # Route to chat.py logic (no sandbox)
                await self._run_chat_without_sandbox(
                    session_uuid=session_uuid,
                    user_id=user_id,
                    message=message,
                    files=files,
                    model_id=model_id,
                    resources=resources,
                    locale=locale,
                    run_id=run_id,
                    sid=sid
                )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            await self.send_error(
                room=session_uuid,
                message=f"Error processing message: {str(e)}",
                run_id=run_id
            )
        finally:
            # Mark task as no longer running
            set_task_running(session_uuid, False)
            
            # NOTE: We intentionally do NOT send status_update='idle' here.
            # The agent stream generator already emits a COMPLETE event which
            # is the authoritative signal for frontend stream completion.
            # Sending 'idle' here caused a race condition: the 'idle' status
            # could arrive at the frontend before all buffered events were
            # processed, prematurely setting isLoading=false and stopping
            # the streaming indicator while the agent was still working.
            # The COMPLETE event (handled by AgentEvent.COMPLETE) properly
            # sets both isCompleted=true and isLoading=false.

    async def _run_chat_without_sandbox(
        self,
        session_uuid: str,
        user_id: int,
        message: str,
        files: List[str],
        model_id: Optional[str],
        resources: list,
        locale: str,
        run_id: str,
        sid: str
    ) -> None:
        """
        Run chat without sandbox (uses chat.py logic).
        
        This calls the same LangGraph workflow as /chat/stream endpoint,
        but streams events through Socket.IO instead of HTTP SSE.
        """
        try:
            logger.info(f"Running chat (no sandbox) for session {session_uuid}")
            
            # Import the chat.py streaming generator
            from backend.app.agent.api.v1.chat import _astream_workflow_generator
            from backend.src.rag.retriever import Resource
            
            # ── Handle file context for chat (no sandbox) ──
            augmented_content = message
            if files:
                try:
                    file_texts, images_data = await self._handle_file_context_for_chat(
                        file_ids=files,
                        user_id=user_id,
                        session_uuid=session_uuid,
                    )
                    augmented_content = self._build_file_augmented_message(
                        message,
                        file_texts=file_texts,
                        images_data=images_data,
                    )
                except Exception as e:
                    logger.warning(f"Failed to retrieve file context for chat: {e}", exc_info=True)
                    # Fallback: just mention file IDs so the user message isn't lost
                    augmented_content = f"{message}\n\n[Attached files: {', '.join(files)}]"

            # Convert messages to LangChain format
            messages = [
                {
                    "role": "user",
                    "content": augmented_content,
                }
            ]
            
            # Create stateful event adapter for this run
            adapter = IIAgentWebSocketAdapter()

            # Accumulate AI text for conversation history persistence
            accumulated_text: List[str] = []

            # Resolve DB session ID for inline tool-event persistence
            chat_session_id: Optional[int] = None
            try:
                async with async_db_session() as _db:
                    _session = await chat_session_dao.get_by_uuid(_db, session_uuid)
                    if _session:
                        chat_session_id = _session.id
            except Exception:
                pass

            # Stream events from chat.py logic
            # save_messages=False because we accumulate and save here instead
            async for event_str in _astream_workflow_generator(
                messages=messages,
                thread_id=session_uuid,
                resources=resources,
                max_search_results=3,
                mcp_settings={},
                enable_background_investigation=False,
                enable_web_search=True,
                locale=locale,
                user_id=str(user_id),
                save_messages=False,
            ):
                # Check for cancellation
                if should_cancel(session_uuid):
                    await self.broadcast_to_session(
                        session_uuid=session_uuid,
                        event_type='cancelled',
                        content={'message': 'Task cancelled by user'},
                        run_id=run_id
                    )
                    return
                
                # Parse SSE event, forward via Socket.IO, and accumulate text
                await self._forward_sse_event(
                    session_uuid, event_str, run_id, adapter,
                    accumulated_text=accumulated_text,
                    session_id_int=chat_session_id,
                )
            
            # Flush any remaining buffered events
            if adapter:
                 flushed_events = adapter.buffer.flush()
                 for evt_type, evt_data in flushed_events:
                     evt_data['run_id'] = run_id
                     await self.broadcast_to_session(
                        session_uuid=session_uuid,
                        event_type=evt_type,
                        content=evt_data,
                        run_id=run_id
                     )

            # Store agent response with real accumulated text
            await self._store_agent_response(
                session_uuid, run_id, model_id,
                accumulated_text=accumulated_text,
            )
            
        except Exception as e:
            logger.error(f"Error in chat (no sandbox): {e}", exc_info=True)
            await self.send_error(
                room=session_uuid,
                message=f"Chat error: {str(e)}",
                run_id=run_id
            )

    async def _run_agent_with_sandbox(
        self,
        session_uuid: str,
        user_id: int,
        message: str,
        files: List[str],
        agent_type: AgentType,
        model_id: Optional[str],
        resources: list,
        locale: str,
        run_id: str,
        sid: str
    ) -> None:
        """
        Run agent with sandbox (uses agent.py logic).
        
        This calls the same logic as /agent/stream endpoint:
        - Creates/reuses sandbox based on session
        - Loads appropriate module based on agent_type
        - Streams events through Socket.IO
        """
        try:
            logger.info(f"Running agent (with sandbox, type={agent_type.value}) for session {session_uuid}")
            
            # Import sandbox and agent infrastructure
            from backend.src.services.sandbox_service import sandbox_service
            from backend.src.services.session_sandbox_manager import SessionSandboxManager
            from backend.src.config.skill_config import AgentCategory
            from backend.app.agent.api.v1.agent import (
                ModuleRegistry,
                AgentModuleType,
                _agent_stream_generator,
            )
            from backend.src.graph.checkpointer import checkpointer_manager
            
            # Get user's API key for MCP authentication
            user_api_key = await self._get_user_api_key(user_id)
            
            # Map AgentType to AgentModuleType
            try:
                module_type = AgentModuleType(agent_type.value)
            except ValueError:
                module_type = AgentModuleType.GENERAL
            
            # Get the agent module's graph
            try:
                graph = ModuleRegistry.get_graph(module_type)
            except (ValueError, NotImplementedError) as e:
                logger.warning(f"Module {agent_type.value} not available: {e}")
                await self.send_error(
                    room=session_uuid,
                    message=f"Agent module '{agent_type.value}' is not available",
                    run_id=run_id
                )
                return
            
            # Create sandbox manager for this session
            sandbox_manager = SessionSandboxManager(
                user_id=str(user_id),
                session_id=session_uuid,
                user_api_key=user_api_key,
                agent_category=self._get_agent_category(agent_type),
            )
            
            # ── Handle file uploads to sandbox ──
            augmented_content = message
            if files:
                try:
                    # Eagerly initialise the sandbox so we can upload files
                    # before the agent stream starts.  SessionSandboxManager
                    # caches the instance, so _agent_stream_generator will
                    # reuse the same sandbox (no double-creation).
                    sandbox, _ = await sandbox_manager.get_sandbox()

                    file_upload_paths, images_data = await self._handle_file_upload_to_sandbox(
                        file_ids=files,
                        sandbox=sandbox,
                        user_id=user_id,
                        session_uuid=session_uuid,
                        run_id=run_id,
                    )
                    augmented_content = self._build_file_augmented_message(
                        message,
                        file_upload_paths=file_upload_paths,
                        images_data=images_data,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to upload files to sandbox: {e}", exc_info=True
                    )
                    # Fallback: mention file IDs so the agent knows files were intended
                    augmented_content = f"{message}\n\n[Attached files: {', '.join(files)}]"

            # Convert messages to LangChain format
            messages = [{"role": "user", "content": augmented_content}]
            
            # Get database session for slide subscriber
            async with async_db_session() as db:
                # Create stateful event adapter for this run
                adapter = IIAgentWebSocketAdapter()

                # Accumulate AI text for conversation history persistence
                accumulated_text: List[str] = []

                # Resolve DB session ID for inline tool-event persistence
                chat_session_id: Optional[int] = None
                try:
                    _session = await chat_session_dao.get_by_uuid(db, session_uuid)
                    if _session:
                        chat_session_id = _session.id
                except Exception:
                    pass

                # Stream events from agent.py logic
                async for event_str in _agent_stream_generator(
                    graph=graph,
                    module_name=agent_type.value,
                    messages=messages,
                    thread_id=session_uuid,
                    sandbox_manager=sandbox_manager,
                    resources=resources,
                    max_plan_iterations=1,
                    max_step_num=3,
                    max_search_results=3,
                    auto_accepted_plan=True,
                    interrupt_feedback=None,
                    enable_background_investigation=False,
                    enable_web_search=True,
                    enable_added_tools=False,
                    locale=locale,
                    db_session=db,
                    user_api_key=user_api_key or "",
                    user_id=str(user_id),
                ):
                    # Check for cancellation
                    if should_cancel(session_uuid):
                        await self.broadcast_to_session(
                            session_uuid=session_uuid,
                            event_type='cancelled',
                            content={'message': 'Task cancelled by user'},
                            run_id=run_id
                        )
                        return
                    
                    # Parse SSE event, forward via Socket.IO, and accumulate text
                    await self._forward_sse_event(
                        session_uuid, event_str, run_id, adapter,
                        accumulated_text=accumulated_text,
                        session_id_int=chat_session_id,
                    )

                # Flush any remaining buffered events
                if adapter:
                     flushed_events = adapter.buffer.flush()
                     for evt_type, evt_data in flushed_events:
                         evt_data['run_id'] = run_id
                         await self.broadcast_to_session(
                            session_uuid=session_uuid,
                            event_type=evt_type,
                            content=evt_data,
                            run_id=run_id
                         )
            
            # Update session with sandbox ID if created
            if sandbox_manager.is_initialized:
                async with async_db_session() as db:
                    session = await chat_session_dao.get_by_uuid(db, session_uuid)
                    if session and not session.sandbox_id:
                        session.sandbox_id = sandbox_manager.sandbox_id
                        await db.commit()
            
            # Store agent response with real accumulated text
            await self._store_agent_response(
                session_uuid, run_id, model_id,
                accumulated_text=accumulated_text,
            )
            
        except Exception as e:
            logger.error(f"Error in agent (with sandbox): {e}", exc_info=True)
            await self.send_error(
                room=session_uuid,
                message=f"Agent error: {str(e)}",
                run_id=run_id
            )

    # =====================================================================
    # FILE UPLOAD HANDLING
    # =====================================================================

    async def _handle_file_upload_to_sandbox(
        self,
        file_ids: List[str],
        sandbox,
        user_id: int,
        session_uuid: str,
        run_id: str,
    ) -> Tuple[List[str], List[dict]]:
        """
        Download staged files from storage (S3/local) and upload them into
        the sandbox at /workspace/uploads/.

        Modeled on ii-agent's UserQueryHandler._handle_file_upload.

        Args:
            file_ids: List of staged file UUIDs from the frontend.
            sandbox: The BaseSandbox (or AgentSandbox) instance.
            user_id: Authenticated user's integer ID.
            session_uuid: Session/thread UUID (for file-thread association).
            run_id: Current run ID for status events.

        Returns:
            Tuple of:
              - file_upload_paths: List of sandbox paths where files were placed.
              - images_data: List of dicts with image content_type and URL for
                multimodal inputs.
        """
        from backend.app.agent.model.staged_file import StagedFile
        from backend.src.services.file_processing.storage import get_storage_backend
        from backend.src.config.configuration import Configuration
        from sqlalchemy import select, and_

        file_upload_paths: List[str] = []
        images_data: List[dict] = []

        if not file_ids:
            return file_upload_paths, images_data

        config = Configuration()
        upload_path = config.workspace_upload_path  # e.g. /workspace/uploads
        storage = get_storage_backend()

        logger.info(
            f"Uploading {len(file_ids)} files to sandbox at {upload_path} "
            f"for session {session_uuid}"
        )

        # Notify frontend that file upload is starting
        await self.broadcast_to_session(
            session_uuid=session_uuid,
            event_type='status',
            content={
                'type': 'file_upload',
                'message': f'Uploading {len(file_ids)} file(s) to sandbox...',
                'file_count': len(file_ids),
            },
            run_id=run_id,
        )

        # Create the uploads directory in the sandbox
        try:
            await sandbox.create_directory(upload_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create upload directory {upload_path} in sandbox: {e}")
            raise

        # Retrieve staged file records from DB
        async with async_db_session() as db:
            query = select(StagedFile).where(
                and_(
                    StagedFile.user_id == user_id,
                    StagedFile.file_id.in_(file_ids),
                )
            )
            result = await db.execute(query)
            staged_files = result.scalars().all()

            if not staged_files:
                logger.warning(f"No staged files found for file_ids: {file_ids}")
                return file_upload_paths, images_data

            for staged_file in staged_files:
                sandbox_file_path = os.path.join(upload_path, staged_file.filename)

                try:
                    # Download file bytes from storage (S3 / local)
                    file_bytes = await storage.download(staged_file.storage_path)
                    if file_bytes is None:
                        logger.warning(
                            f"File not found in storage: {staged_file.storage_path} "
                            f"(file_id={staged_file.file_id})"
                        )
                        continue

                    # Upload bytes into the sandbox
                    success = await sandbox.upload_file(file_bytes, sandbox_file_path)
                    if not success:
                        logger.warning(
                            f"Sandbox upload returned failure for {staged_file.filename}"
                        )
                        continue

                    file_upload_paths.append(sandbox_file_path)
                    logger.info(
                        f"Uploaded {staged_file.filename} -> {sandbox_file_path} "
                        f"({len(file_bytes):,} bytes)"
                    )

                    # Collect image data for multimodal support
                    if staged_file.is_image:
                        # Generate a signed URL for the image
                        image_storage_path = (
                            staged_file.image_url or staged_file.storage_path
                        )
                        signed_url = await storage.get_url(image_storage_path, 3600)
                        if signed_url:
                            images_data.append({
                                "content_type": staged_file.mime_type,
                                "url": signed_url,
                            })

                except Exception as e:
                    logger.error(
                        f"Failed to upload file {staged_file.filename} to sandbox: {e}",
                        exc_info=True,
                    )
                    # Continue with remaining files
                    continue

            # Associate files with the thread/session
            for staged_file in staged_files:
                if staged_file.thread_id != session_uuid:
                    staged_file.thread_id = session_uuid
            await db.commit()

        logger.info(
            f"File upload complete: {len(file_upload_paths)}/{len(file_ids)} files "
            f"uploaded to sandbox, {len(images_data)} images detected"
        )

        # Notify frontend that file upload is complete
        await self.broadcast_to_session(
            session_uuid=session_uuid,
            event_type='status',
            content={
                'type': 'file_upload_complete',
                'message': f'{len(file_upload_paths)} file(s) uploaded to sandbox',
                'file_count': len(file_upload_paths),
                'file_paths': file_upload_paths,
            },
            run_id=run_id,
        )

        return file_upload_paths, images_data

    async def _handle_file_context_for_chat(
        self,
        file_ids: List[str],
        user_id: int,
        session_uuid: str,
    ) -> Tuple[List[dict], List[dict]]:
        """
        Retrieve file content for chat mode (no sandbox).

        Instead of uploading to a sandbox, this extracts the parsed text
        content and image URLs from staged files so they can be injected
        directly into the LLM message.

        Args:
            file_ids: List of staged file UUIDs.
            user_id: Authenticated user's integer ID.
            session_uuid: Session/thread UUID.

        Returns:
            Tuple of:
              - file_texts: List of {"filename": str, "content": str, "mime_type": str}
                for documents with parsed text content.
              - images_data: List of {"content_type": str, "url": str} for images.
        """
        from backend.app.agent.model.staged_file import StagedFile
        from backend.src.services.file_processing.storage import get_storage_backend
        from sqlalchemy import select, and_

        file_texts: List[dict] = []
        images_data: List[dict] = []

        if not file_ids:
            return file_texts, images_data

        storage = get_storage_backend()

        async with async_db_session() as db:
            query = select(StagedFile).where(
                and_(
                    StagedFile.user_id == user_id,
                    StagedFile.file_id.in_(file_ids),
                )
            )
            result = await db.execute(query)
            staged_files = result.scalars().all()

            if not staged_files:
                logger.warning(f"No staged files found for chat file_ids: {file_ids}")
                return file_texts, images_data

            for staged_file in staged_files:
                if staged_file.is_image:
                    # Generate signed URL for the image
                    image_path = (
                        staged_file.image_url or staged_file.storage_path
                    )
                    signed_url = await storage.get_url(image_path, 3600)
                    if signed_url:
                        images_data.append({
                            "content_type": staged_file.mime_type,
                            "url": signed_url,
                        })
                elif staged_file.has_parsed_content:
                    # Include parsed text content for documents
                    file_texts.append({
                        "filename": staged_file.filename,
                        "content": staged_file.parsed_content,
                        "mime_type": staged_file.mime_type,
                    })
                else:
                    # File has no parsed content and is not an image;
                    # just note its name so the LLM knows it was attached.
                    file_texts.append({
                        "filename": staged_file.filename,
                        "content": f"[Binary file: {staged_file.filename} ({staged_file.mime_type}, {staged_file.file_size:,} bytes)]",
                        "mime_type": staged_file.mime_type,
                    })

            # Associate files with session
            for staged_file in staged_files:
                if staged_file.thread_id != session_uuid:
                    staged_file.thread_id = session_uuid
            await db.commit()

        logger.info(
            f"Chat file context: {len(file_texts)} text files, "
            f"{len(images_data)} images for session {session_uuid}"
        )
        return file_texts, images_data

    def _build_file_augmented_message(
        self,
        message: str,
        *,
        file_upload_paths: Optional[List[str]] = None,
        file_texts: Optional[List[dict]] = None,
        images_data: Optional[List[dict]] = None,
    ) -> Any:
        """
        Build the user message content with file context appended.

        For **sandbox mode** (file_upload_paths provided):
            Appends a list of sandbox file paths so the agent knows where to
            find the files in its workspace.

        For **chat mode** (file_texts provided):
            Appends parsed file contents inline and constructs multimodal
            content blocks for images.

        Args:
            message: The original user message text.
            file_upload_paths: Sandbox paths (agent mode).
            file_texts: Parsed text content dicts (chat mode).
            images_data: Image dicts with content_type and url.

        Returns:
            Either a string (text-only) or a list of content blocks
            (multimodal with images).
        """
        # ── SANDBOX MODE ──
        if file_upload_paths:
            files_section = "\n\nAttached files (uploaded to sandbox):\n"
            for path in file_upload_paths:
                files_section += f" - {path}\n"
            files_section += (
                "\nThese files have been uploaded to the sandbox workspace. "
                "You can read, analyze, and process them using your file tools."
            )
            augmented_text = message + files_section

            # If there are also images, create multimodal content
            if images_data:
                content_blocks = [{"type": "text", "text": augmented_text}]
                for img in images_data:
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": img["url"]},
                    })
                return content_blocks
            return augmented_text

        # ── CHAT MODE ──
        if file_texts:
            files_section = "\n\nAttached file contents:\n"
            for ft in file_texts:
                files_section += f"\n--- {ft['filename']} ---\n{ft['content']}\n"
            augmented_text = message + files_section

            # If there are also images, create multimodal content
            if images_data:
                content_blocks = [{"type": "text", "text": augmented_text}]
                for img in images_data:
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": img["url"]},
                    })
                return content_blocks
            return augmented_text

        # Images only (no text files)
        if images_data:
            content_blocks = [{"type": "text", "text": message}]
            for img in images_data:
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {"url": img["url"]},
                })
            return content_blocks

        # No files at all — return original message
        return message

    async def _forward_sse_event(
        self,
        session_uuid: str,
        event_str: str,
        run_id: str,
        adapter: IIAgentWebSocketAdapter = None,
        accumulated_text: list = None,
        session_id_int: int = None,
    ) -> None:
        """
        Parse SSE event string and forward via Socket.IO.

        Uses IIAgentWebSocketAdapter to transform SSE events to WebSocket format.
        This ensures the frontend receives events in the expected II-Agent format.

        Also accumulates text content and persists tool events to the database
        for conversation history replay.

        SSE format: "event: <type>\\ndata: <json>\\n\\n"

        :param accumulated_text: If provided, text deltas are appended here for
            later persistence as the full agent message.
        :param session_id_int: Database session ID, required for inline tool
            event persistence.
        """
        try:
            lines = event_str.strip().split('\n')
            event_type = None
            data = None

            for line in lines:
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                elif line.startswith('data:'):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {'raw': data_str}

            if event_type and data:
                # ── Accumulate text for conversation history ──
                # Only capture from II-Agent "content" deltas to avoid
                # duplication (each token also produces "message" and
                # "message_chunk" events).
                if accumulated_text is not None:
                    if event_type == "content" and data.get("status") == "delta" and "delta" in data:
                        text_delta = data["delta"]
                        if text_delta:
                            accumulated_text.append(text_delta)

                # ── Persist tool events inline ──
                # Save tool_call and tool_result to the database as they
                # stream through, so conversation history replay works.
                if session_id_int is not None:
                    await self._maybe_persist_tool_event(
                        event_type=event_type,
                        data=data,
                        session_id_int=session_id_int,
                        run_id=run_id,
                    )

                # Flush buffer before complete to ensure all content arrives first
                if event_type == "complete" and adapter:
                    flushed_events = adapter.buffer.flush()
                    for evt_type, evt_data in flushed_events:
                        evt_data['run_id'] = run_id
                        await self.broadcast_to_session(
                            session_uuid=session_uuid,
                            event_type=evt_type,
                            content=evt_data,
                            run_id=run_id
                        )

                # Transform SSE event to WebSocket format using the adapter
                if adapter:
                    ws_event_type, ws_data = adapter.process_event(event_type, data)
                else:
                    # Fallback for stateless usage (legacy)
                    ws_event_type, ws_data = IIAgentWebSocketAdapter.transform(event_type, data)

                if ws_event_type and ws_data:
                    # Add run_id to the data
                    ws_data['run_id'] = run_id

                    # Emit the transformed event
                    await self.broadcast_to_session(
                        session_uuid=session_uuid,
                        event_type=ws_event_type,
                        content=ws_data,
                        run_id=run_id
                    )

                # NOTE: We intentionally do NOT emit the raw SSE event here.
                # The transformed event (ws_event_type, ws_data) is the correct 
                # II-Agent WebSocket format. Raw SSE types like "tool_call_start",
                # "tool_call_args", "tool_call_end" do not match the frontend's 
                # AgentEvent enum and would cause the build panel to remain stuck
                # on "Generating" since these events are silently dropped.
                # See: frontend/src/hooks/use-app-events.tsx (AgentEvent.TOOL_CALL)


        except Exception as e:
            logger.debug(f"Error parsing SSE event: {e}")

    async def _maybe_persist_tool_event(
        self,
        event_type: str,
        data: dict,
        session_id_int: int,
        run_id: str,
    ) -> None:
        """
        Persist tool_call / tool_result events to the database inline
        during streaming so they appear in conversation history on reload.

        Uses the II-Agent format events ("tool_result") which carry the
        full structured data. "tool_call_start"/"tool_call_args"/"tool_call_end"
        are partial streaming events — we instead capture the consolidated
        "tool_result" event which contains tool_name, tool_input AND result.
        """
        try:
            if event_type == "tool_result":
                tool_name = data.get("tool_name", "unknown")
                tool_call_id = data.get("tool_call_id", "")
                tool_input = data.get("tool_input", {})
                result = data.get("result", "")

                async with async_db_session() as db:
                    # Save the tool call
                    tool_call_event = await chat_event_dao.create_tool_call(
                        db=db,
                        session_id=session_id_int,
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                        arguments=tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)},
                        run_id=run_id,
                    )
                    # Save the tool result
                    await chat_event_dao.create_tool_result(
                        db=db,
                        session_id=session_id_int,
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                        result=result if isinstance(result, dict) else {"output": str(result) if result else ""},
                        run_id=run_id,
                        parent_event_id=tool_call_event.id if tool_call_event else None,
                    )
                    await db.commit()
        except Exception as e:
            # Non-fatal — don't break the stream if persistence fails
            logger.debug(f"Failed to persist tool event ({event_type}): {e}")

    async def _store_agent_response(
        self,
        session_uuid: str,
        run_id: str,
        model_id: Optional[str],
        accumulated_text: Optional[List[str]] = None,
    ) -> None:
        """
        Store agent response event in database.

        :param accumulated_text: List of text deltas collected during streaming.
            If provided and non-empty, the joined text is saved as the agent
            message.  Otherwise a placeholder is used (legacy fallback).
        """
        try:
            agent_text = "".join(accumulated_text) if accumulated_text else ""
            if not agent_text:
                agent_text = "[Agent response completed]"

            async with async_db_session() as db:
                session = await chat_session_dao.get_by_uuid(db, session_uuid)
                if session:
                    await chat_event_dao.create_agent_message(
                        db=db,
                        session_id=session.id,
                        text=agent_text,
                        run_id=run_id,
                        model_name=model_id or 'default'
                    )
                    await db.commit()
                    logger.info(
                        f"Stored agent response for session {session_uuid}: "
                        f"{len(agent_text)} chars"
                    )
        except Exception as e:
            logger.warning(f"Failed to store agent response: {e}")

    async def _get_user_api_key(self, user_id: int) -> Optional[str]:
        """Get user's API key for MCP authentication."""
        try:
            from backend.common.security.jwt import create_access_token
            from backend.utils.timezone import timezone
            from datetime import timedelta
            
            # Create a short-lived token for MCP auth
            token = await create_access_token(
                sub=str(user_id),
                expires_delta=timedelta(hours=2),
                multi_login=True,
            )
            return token
        except Exception as e:
            logger.warning(f"Failed to get user API key: {e}")
            return None

    def _get_agent_category(self, agent_type: AgentType) -> Optional[str]:
        """
        Map AgentType to AgentCategory for skills injection.
        
        AgentCategory is a Literal["general", "scientific", "academic"], so we map
        all 11 AgentTypes to these 3 categories for skill folder selection.
        """
        # Map agent types to the 3 skill categories
        # "general" → basic skills
        # "scientific" → scientific_skills  
        # "academic" → academic skills
        mapping = {
            # No-sandbox type
            # AgentType.CHAT: "general",
            
            # General/default types
            AgentType.GENERAL: "general",
            AgentType.DEV: "general",
            AgentType.DESIGN: "general",
            AgentType.EXCALIDRAW: "general",
            
            # Scientific/research types
            AgentType.DEEP_RESEARCH: "scientific",
            AgentType.DATA_SCIENTIST: "scientific",
            AgentType.QUANT: "scientific",
            
            # Academic/document types
            AgentType.ACADEMIC: "academic",
            AgentType.SLIDES: "academic",
            AgentType.DOCUMENTS: "academic",
        }
        return mapping.get(agent_type, "general")