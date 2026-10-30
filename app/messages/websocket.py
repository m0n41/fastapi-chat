from fastapi import WebSocket, WebSocketDisconnect, WebSocketException, status
from fastapi import APIRouter
from app.users.jwt import decode_access_token
from app.db.session import get_session
from app.users.models import User
from app.messages.models import Message
from sqlalchemy import select
import jwt
import json


router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
    async def broadcast(self, message: str, websocket: WebSocket):
        dead: list[WebSocket] = []
        
        for connection in list(self.active_connections):
            if connection == websocket:
                continue
            
            try:
                await connection.send_text(message)
            except (WebSocketDisconnect, RuntimeError, OSError):
                dead.append(connection)
                
        for d in dead:
            if d in self.active_connections:
                self.active_connections.remove(d)
                
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    cookie = websocket.cookies.get("access_token")
    if not cookie:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    
    try:
        user_id = decode_access_token(cookie)
    except jwt.InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    
    # Открываем сессию только для проверки пользователя
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
    if user is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            async with get_session() as session:
                message = Message(
                    user_id=user_id,
                    content=data
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)
            
            message_json = json.dumps({
                "id": message.id,
                "user_id": message.user_id,
                "username": user.username,
                "content": message.content,
                "created_at": message.created_at.isoformat()
            })
            await manager.broadcast(message_json, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
        