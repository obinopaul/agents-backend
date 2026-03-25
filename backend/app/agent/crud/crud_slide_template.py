from typing import Optional, Sequence, Tuple
from sqlalchemy import select, or_, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.agent.model.slide_template import SlideTemplate

class CRUDSlideTemplate(CRUDPlus[SlideTemplate]):
    """CRUD operations for SlideTemplate model."""

    async def get_by_template_id(self, db: AsyncSession, template_id: str) -> Optional[SlideTemplate]:
        """Get template by unique template_id string."""
        query = select(SlideTemplate).where(SlideTemplate.template_id == template_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_active(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None
    ) -> Tuple[Sequence[SlideTemplate], int]:
        """Get paginated active templates."""
        filters = [SlideTemplate.is_active == True]
        
        if search:
            filters.append(or_(
                SlideTemplate.name.ilike(f"%{search}%"),
                SlideTemplate.description.ilike(f"%{search}%")
            ))
            
        combined_filter = and_(*filters)
        
        # Count
        count_query = select(func.count()).select_from(SlideTemplate).where(combined_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Query
        offset = (page - 1) * per_page
        query = (
            select(SlideTemplate)
            .where(combined_filter)
            .order_by(desc(SlideTemplate.created_at))
            .offset(offset)
            .limit(per_page)
        )
        
        result = await db.execute(query)
        return result.scalars().all(), total

slide_template_dao = CRUDSlideTemplate(SlideTemplate)
