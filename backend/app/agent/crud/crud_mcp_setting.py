"""CRUD operations for MCP Settings."""

from typing import Optional, Sequence

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.agent.model.mcp_setting import MCPSetting


class CRUDMCPSetting(CRUDPlus[MCPSetting]):
    """CRUD operations for MCPSetting model."""

    async def get_by_user_id(
        self, 
        db: AsyncSession, 
        user_id: int,
        only_active: bool = False
    ) -> Sequence[MCPSetting]:
        """
        Get all MCP settings for a user.
        
        :param db: Database session
        :param user_id: User ID
        :param only_active: If True, only return active settings
        :return: List of MCP settings
        """
        query = select(MCPSetting).where(MCPSetting.user_id == user_id)
        
        if only_active:
            query = query.where(MCPSetting.is_active == True)
        
        query = query.order_by(MCPSetting.created_time.desc())
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_user_and_type(
        self, 
        db: AsyncSession, 
        user_id: int, 
        tool_type: str
    ) -> Optional[MCPSetting]:
        """
        Get MCP setting for a specific user and tool type.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type (codex, claude_code, etc.)
        :return: MCP setting or None
        """
        result = await db.execute(
            select(MCPSetting).where(
                and_(
                    MCPSetting.user_id == user_id,
                    MCPSetting.tool_type == tool_type
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_type(
        self, 
        db: AsyncSession, 
        user_id: int, 
        tool_type: str
    ) -> Optional[MCPSetting]:
        """
        Get active MCP setting for a specific user and tool type.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :return: Active MCP setting or None
        """
        result = await db.execute(
            select(MCPSetting).where(
                and_(
                    MCPSetting.user_id == user_id,
                    MCPSetting.tool_type == tool_type,
                    MCPSetting.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        db: AsyncSession,
        user_id: int,
        tool_type: str,
        mcp_config: dict,
        auth_json: Optional[dict] = None,
        metadata_json: Optional[dict] = None,
        store_path: Optional[str] = None,
        is_active: bool = True
    ) -> MCPSetting:
        """
        Create or update MCP setting for a user and tool type.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :param mcp_config: MCP configuration
        :param auth_json: Authentication JSON
        :param metadata_json: Additional metadata
        :param store_path: Credential store path in sandbox
        :param is_active: Whether setting is active
        :return: Created or updated MCP setting
        """
        existing = await self.get_by_user_and_type(db, user_id, tool_type)
        
        if existing:
            # Update existing setting
            existing.mcp_config = mcp_config
            if auth_json is not None:
                existing.auth_json = auth_json
            if metadata_json is not None:
                existing.metadata_json = metadata_json
            if store_path is not None:
                existing.store_path = store_path
            existing.is_active = is_active
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            # Create new setting
            new_setting = MCPSetting(
                user_id=user_id,
                tool_type=tool_type,
                mcp_config=mcp_config,
                auth_json=auth_json,
                metadata_json=metadata_json,
                store_path=store_path,
                is_active=is_active
            )
            db.add(new_setting)
            await db.commit()
            await db.refresh(new_setting)
            return new_setting

    async def delete_by_user_and_type(
        self, 
        db: AsyncSession, 
        user_id: int, 
        tool_type: str
    ) -> bool:
        """
        Delete MCP setting for a user and tool type.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :return: True if deleted, False if not found
        """
        setting = await self.get_by_user_and_type(db, user_id, tool_type)
        if setting:
            await db.delete(setting)
            await db.commit()
            return True
        return False

    async def set_active(
        self, 
        db: AsyncSession, 
        user_id: int, 
        tool_type: str, 
        is_active: bool
    ) -> Optional[MCPSetting]:
        """
        Set active status for MCP setting.
        
        :param db: Database session
        :param user_id: User ID
        :param tool_type: Tool type
        :param is_active: Active status
        :return: Updated setting or None
        """
        setting = await self.get_by_user_and_type(db, user_id, tool_type)
        if setting:
            setting.is_active = is_active
            await db.commit()
            await db.refresh(setting)
            return setting
        return None


# Singleton instance
mcp_setting_dao: CRUDMCPSetting = CRUDMCPSetting(MCPSetting)
