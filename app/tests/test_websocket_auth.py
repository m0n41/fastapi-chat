import pytest
import time
import json
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.main import app
from app.messages.models import Message
from app.users.models import User
from app.users.jwt import create_access_token


# тест авторизации. неавторизованные пользователи не попадают в чат
def test_websocket_auth():
    client = TestClient(app=app, cookies={})
    
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws") as ws:
            pass
    
    assert exc_info.value.code == 1008


def test_token_websocket_auth():
    client = TestClient(app=app, cookies={"access_token": "token"})
    
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws") as ws:
            pass
    
    assert exc_info.value.code == 1008


# Успешная авторизация. проверяем подключение к /ws с валидным JWT существующего пользователя
def test_websocket_auth_success(db_session):
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="..."
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = create_access_token(user.id)
    
    client = TestClient(app=app, cookies={"access_token": token})
    with client.websocket_connect("/ws") as ws:
        ws.send_text("Hello, world!")
    
        deadline = time.time() + 2.0
        saved = None
        while time.time() < deadline:
            result = db_session.execute(select(Message).where(Message.content == "Hello, world!"))
            saved = result.scalar_one_or_none()
            if saved is not None:
                break
            time.sleep(0.05)
    
    assert saved is not None, "Сообщение не сохранилось"
    assert saved.user_id == user.id

# тестирование сообщений клиентов
def test_user_connect(db_session):
    user_1 = User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="..."
    )
    
    user_2 = User(
        id=2,
        username="testuser2",
        email="test2@example.com",
        hashed_password="..."
    )
    
    db_session.add_all([user_1, user_2])
    db_session.commit()
    for i in (user_1, user_2):
        db_session.refresh(i)
    
    token_1 = create_access_token(user_1.id)
    token_2 = create_access_token(user_2.id)
    
    with TestClient(app=app) as client:
        with client.websocket_connect("/ws", headers={"cookie": f"access_token={token_1}"}) as ws_1:        
            with client.websocket_connect("/ws", headers={"cookie": f"access_token={token_2}"}) as ws_2:
                ws_1.send_text("Hello from client 1")
                assert json.loads(ws_2.receive_text())["content"] == "Hello from client 1"
                
                ws_2.send_text("Hello from client 2")
                assert json.loads(ws_1.receive_text())["content"] == "Hello from client 2"