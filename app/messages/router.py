from fastapi import APIRouter, Depends
from app.messages.schemas import MessageResponse, MessageCreate
from app.db.session import SessionDep
from app.users.dependencies import get_current_user
from app.users.models import User
from app.messages.models import Message
from typing import Annotated
from sqlalchemy import select

router = APIRouter()

@router.post("/api/messages", response_model=MessageResponse, status_code=201)
async def post_api_messages(
    message: MessageCreate, session: SessionDep, user: Annotated[User, Depends(get_current_user)]
) -> MessageResponse:
    new_message = Message(
        user_id=user.id, content=message.content
    )
    
    session.add(new_message)
    await session.commit()
    await session.refresh(new_message)
    
    return MessageResponse(
        id=new_message.id,
        user_id=new_message.user_id,
        username=user.username,
        content=new_message.content,
        created_at=new_message.created_at,
    )

@router.get("/api/messages", response_model=list[MessageResponse])
async def get_api_messages(
    session: SessionDep, user: Annotated[User, Depends(get_current_user)]
) -> list[MessageResponse]:
    subq = (
        select(Message.id).order_by(Message.created_at.desc())
        .limit(50).subquery()
    )
    
    query = (
        select(Message, User.username)
        .join(User, Message.user_id == User.id)
        .where(Message.id.in_(select(subq.c.id)))
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(query)
    rows = result.all()   
    
    return [
        MessageResponse(
            id=message.id,
            user_id=message.user_id,
            username=username,
            content=message.content,
            created_at=message.created_at,
        )
        for message, username in rows
    ]