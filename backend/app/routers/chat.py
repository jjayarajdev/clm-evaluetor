"""Chat session API — persistent conversation history."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, CurrentTenantId, get_db
from app.models.chat_session import ChatSession, ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------- Pydantic schemas ----------

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list | None = None
    follow_ups: list | None = None
    visualizations: list | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: str
    title: str
    contract_id: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailOut(SessionOut):
    messages: list[MessageOut] = []


class SessionCreate(BaseModel):
    title: str = "New Chat"
    contract_id: str | None = None


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    sources: list | None = None
    follow_ups: list | None = None
    visualizations: list | None = None


class SessionUpdateTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


# ---------- Endpoints ----------

@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """List all chat sessions for the current user, newest first."""
    result = await db.execute(
        select(
            ChatSession,
            func.count(ChatMessage.id).label("msg_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.tenant_id == tenant_id,
        )
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows = result.all()
    return [
        SessionOut(
            id=str(s.id),
            title=s.title,
            contract_id=str(s.contract_id) if s.contract_id else None,
            message_count=cnt,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s, cnt in rows
    ]


@router.post("/sessions", response_model=SessionDetailOut, status_code=201)
async def create_session(
    body: SessionCreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = ChatSession(
        tenant_id=tenant_id,
        user_id=current_user.id,
        title=body.title,
        contract_id=UUID(body.contract_id) if body.contract_id else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionDetailOut(
        id=str(session.id),
        title=session.title,
        contract_id=str(session.contract_id) if session.contract_id else None,
        message_count=0,
        messages=[],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Get a session with all its messages."""
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetailOut(
        id=str(session.id),
        title=session.title,
        contract_id=str(session.contract_id) if session.contract_id else None,
        message_count=len(session.messages),
        messages=[
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                sources=m.sources,
                follow_ups=m.follow_ups,
                visualizations=m.visualizations,
                created_at=m.created_at,
            )
            for m in session.messages
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session_title(
    session_id: UUID,
    body: SessionUpdateTitle,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Update session title."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = body.title
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=str(session.id),
        title=session.title,
        contract_id=str(session.contract_id) if session.contract_id else None,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


@router.post("/sessions/{session_id}/messages", response_model=MessageOut, status_code=201)
async def add_message(
    session_id: UUID,
    body: MessageCreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Add a message to a session."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg = ChatMessage(
        session_id=session.id,
        role=body.role,
        content=body.content,
        sources=body.sources,
        follow_ups=body.follow_ups,
        visualizations=body.visualizations,
    )
    db.add(msg)

    # Auto-title from first user message
    if body.role == "user" and session.title == "New Chat":
        session.title = body.content[:60] + ("..." if len(body.content) > 60 else "")

    # Touch updated_at
    session.updated_at = func.now()

    await db.commit()
    await db.refresh(msg)
    return MessageOut(
        id=str(msg.id),
        role=msg.role,
        content=msg.content,
        sources=msg.sources,
        follow_ups=msg.follow_ups,
        visualizations=msg.visualizations,
        created_at=msg.created_at,
    )
