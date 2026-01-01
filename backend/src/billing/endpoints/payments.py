"""
Payment Endpoints

API endpoints for credit purchases and transaction history.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from backend.src.billing.payments import payment_service
from backend.src.billing.shared.config import CREDITS_PER_DOLLAR
from .dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing-payments"])


# ============================================================================
# Request Models
# ============================================================================

class PurchaseCreditsRequest(BaseModel):
    """Request for credit purchase."""
    amount: Decimal = Field(..., gt=0, le=1000, description="Amount in USD")
    success_url: str
    cancel_url: str


class PackagePurchaseRequest(BaseModel):
    """Request for package purchase."""
    package_id: str
    success_url: str
    cancel_url: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/purchase-credits")
async def purchase_credits(
    request: PurchaseCreditsRequest,
    user_id: str = Depends(get_current_user_id)
) -> Dict:
    """
    Create checkout session for credit purchase.
    
    Only available for paid tier users.
    """
    try:
        result = await payment_service.create_checkout_session(
            account_id=user_id,
            amount=request.amount,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error purchasing credits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions")
async def get_transactions(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100, description="Number of transactions"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
) -> Dict:
    """Get credit transaction history."""
    try:
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, amount, type, description, created_at, metadata
                    FROM credit_ledger
                    WHERE account_id = :user_id::uuid
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"user_id": user_id, "limit": limit, "offset": offset}
            )
            rows = result.fetchall()
            
            transactions = []
            for row in rows:
                transactions.append({
                    'id': str(row.id),
                    'amount': float(row.amount) * CREDITS_PER_DOLLAR,
                    'type': row.type,
                    'description': row.description,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'metadata': row.metadata or {}
                })
            
            # Get total count
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM credit_ledger WHERE account_id = :user_id::uuid"),
                {"user_id": user_id}
            )
            total = count_result.scalar() or 0
        
        return {
            'transactions': transactions,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': total,
                'has_more': offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error(f"[BILLING] Error fetching transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions/summary")
async def get_transactions_summary(
    user_id: str = Depends(get_current_user_id),
    days: int = Query(30, ge=1, le=365, description="Days to look back")
) -> Dict:
    """Get transaction summary for a period."""
    try:
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        async with async_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT type, amount FROM credit_ledger
                    WHERE account_id = :user_id::uuid
                    AND created_at >= :since
                """),
                {"user_id": user_id, "since": since}
            )
            rows = result.fetchall()
        
        summary = {
            'period_days': days,
            'period_start': since.isoformat(),
            'period_end': datetime.now(timezone.utc).isoformat(),
            'total_spent': 0.0,
            'total_added': 0.0,
            'usage_count': 0,
            'purchase_count': 0,
            'by_type': {}
        }
        
        for row in rows:
            txn_type = row.type
            amount = float(row.amount)
            
            if txn_type not in summary['by_type']:
                summary['by_type'][txn_type] = {'count': 0, 'total': 0.0}
            
            summary['by_type'][txn_type]['count'] += 1
            summary['by_type'][txn_type]['total'] += amount
            
            if amount < 0:
                summary['total_spent'] += abs(amount) * CREDITS_PER_DOLLAR
                if txn_type == 'usage':
                    summary['usage_count'] += 1
            else:
                summary['total_added'] += amount * CREDITS_PER_DOLLAR
                if txn_type == 'purchase':
                    summary['purchase_count'] += 1
        
        return summary
        
    except Exception as e:
        logger.error(f"[BILLING] Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/credit-usage", name="billing_get_credit_usage")
async def get_credit_usage(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> Dict:
    """Get credit usage records."""
    try:
        from backend.database.db import async_db_session
        from sqlalchemy import text
        
        async with async_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, amount, description, created_at, metadata
                    FROM credit_ledger
                    WHERE account_id = :user_id::uuid
                    AND type = 'usage'
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"user_id": user_id, "limit": limit, "offset": offset}
            )
            rows = result.fetchall()
            
            usage_records = []
            for row in rows:
                metadata = row.metadata or {}
                usage_records.append({
                    'id': str(row.id),
                    'amount': abs(float(row.amount)) * CREDITS_PER_DOLLAR,
                    'description': row.description,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'message_id': metadata.get('message_id'),
                    'thread_id': metadata.get('thread_id'),
                    'model': metadata.get('model'),
                    'tokens': metadata.get('tokens')
                })
            
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM credit_ledger WHERE account_id = :user_id::uuid AND type = 'usage'"),
                {"user_id": user_id}
            )
            total = count_result.scalar() or 0
        
        return {
            'usage_records': usage_records,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': total,
                'has_more': offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error(f"[BILLING] Error fetching usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purchases")
async def get_purchases(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = Query(None, description="Filter by status")
) -> Dict:
    """Get credit purchase history."""
    try:
        result = await payment_service.list_purchases(
            account_id=user_id,
            limit=limit,
            status=status
        )
        return result
    except Exception as e:
        logger.error(f"[BILLING] Error fetching purchases: {e}")
        raise HTTPException(status_code=500, detail=str(e))
