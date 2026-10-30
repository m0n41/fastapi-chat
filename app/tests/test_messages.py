import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timezone
from app.users.jwt import decode_access_token
from app.main import app
from app.messages.models import Message

def test_create_message(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    data = response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    assert "access_token" not in client.cookies
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    assert log_response.status_code == 200
    
    mes_response = client.post("/api/messages", json={"content": "Привет, это тестовое сообщение!"})
    assert mes_response.status_code == 201
    
    mes_data = mes_response.json()
    assert mes_data["id"] > 0
    assert mes_data["user_id"] == data["id"]
    assert mes_data["username"] == "test_user"
    assert mes_data["content"] == "Привет, это тестовое сообщение!"
    
    created_at = datetime.fromisoformat(mes_data["created_at"])
    now = datetime.now(timezone.utc)
    
    assert abs((now - created_at).total_seconds()) < 5, (
        f"created_at={created_at} слишком отличается от now={now}"
    )
    
    result = db_session.execute(
        select(Message).where(Message.content == "Привет, это тестовое сообщение!")
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.user_id == data["id"]
    assert saved.content == "Привет, это тестовое сообщение!"
    
def test_get_messages(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    data = response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    assert "access_token" not in client.cookies
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    assert log_response.status_code == 200
    
    mes_response_one = client.post("/api/messages", json={"content": "Привет, это тестовое первое сообщение!"})
    mes_response_two = client.post("/api/messages", json={"content": "Привет, это тестовое второе сообщение!"})
    
    assert mes_response_one.status_code == 201
    assert mes_response_two.status_code == 201
    
    mes_data_one = mes_response_one.json()
    mes_data_two = mes_response_two.json()
    
    assert mes_data_one["content"] == "Привет, это тестовое первое сообщение!"
    assert mes_data_two["content"] == "Привет, это тестовое второе сообщение!"
    
    assert mes_data_one["username"] == "test_user"
    assert mes_data_two["username"] == "test_user"
    
    get_response = client.get("/api/messages")
    assert get_response.status_code == 200
    
    messages = get_response.json()
    
    assert isinstance(messages, list), "Ответ должен быть списком"
    
    contents = [m["content"] for m in messages]
    assert "Привет, это тестовое первое сообщение!" in contents
    assert "Привет, это тестовое второе сообщение!" in contents
    
    for msg in messages:
        if msg["content"] in (
            "Привет, это тестовое первое сообщение!",
            "Привет, это тестовое второе сообщение!",
        ):
            assert msg["username"] == "test_user"
    
def test_get_messages_unauthorized(db_session):
    client = TestClient(app=app)
    
    response = client.get("/api/messages")
    assert response.status_code == 401
    
def test_create_message_unauthorized(db_session):
    client = TestClient(app=app)
    
    response = client.post("/api/messages", json={"content": "Сообщение без авторизации"})
    assert response.status_code == 401
    assert "detail" in response.json()
    
    result = db_session.execute(
        select(Message).where(Message.content == "Сообщение без авторизации")
    )
    saved = result.scalar_one_or_none()
    assert saved is None, "Сообщение не должно было сохраниться без авторизации"
    
def test_get_messages_limit_50(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    reg_response = client.post("/api/auth/register", json=payload)
    assert reg_response.status_code == 201
    
    data = reg_response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    assert "access_token" not in client.cookies
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    assert log_response.status_code == 200
    
    total_messages = 55
    for i in range(total_messages):
        mes_response = client.post(
            "/api/messages",
            json={"content": f"Сообщение {i}"}
        )
        assert mes_response.status_code == 201, f"Сообщение {i} не создано"
        
    get_response = client.get("/api/messages")
    assert get_response.status_code == 200
    
    messages = get_response.json()
    
    assert len(messages) == 50, f"Ожидалось 50 сообщений, получено {len(messages)}"
    
    contents = [m["content"] for m in messages]
    
    for i in range(5, 55):
        assert f"Сообщение {i}" in contents, f"Сообщение {i} отсутствует в ответе"
        
    for i in range(0, 5):
        assert f"Сообщение {i}" not in contents, f"Сообщение {i} не должно быть в ответе"
        
def test_messages_belong_to_different_users(db_session):
    user_A = {
        "username": "test_user_A",
        "email": "test_user_A@example.com",
        "password": "test_password"
    }
    user_B = {
        "username": "test_user_B",
        "email": "test_user_B@example.com",
        "password": "test_password"
    }
    
    client_a = TestClient(app=app)
    reg_a = client_a.post("/api/auth/register", json=user_A)
    assert reg_a.status_code == 201
    data_a = reg_a.json()
    user_a_id = data_a["id"]
    
    log_a = client_a.post("/api/auth/login", json={
        "username": "test_user_A",
        "password": "test_password"
    })
    assert log_a.status_code == 200
    assert "access_token" in client_a.cookies
    
    client_b = TestClient(app=app)
    reg_b = client_b.post("/api/auth/register", json=user_B)
    assert reg_b.status_code == 201
    data_b = reg_b.json()
    user_b_id = data_b["id"]
    
    log_b = client_b.post("/api/auth/login", json={
        "username": "test_user_B",
        "password": "test_password"
    })
    assert log_b.status_code == 200
    assert "access_token" in client_b.cookies
    
    mes_a = client_a.post(
        "/api/messages",
        json={"content": "Сообщение пользователя A"}
    )
    assert mes_a.status_code == 201
    mes_a_data = mes_a.json()
    assert mes_a_data["username"] == "test_user_A"
    assert mes_a_data["user_id"] == user_a_id
    
    mes_b = client_b.post(
        "/api/messages",
        json={"content": "Сообщение пользователя B"}
    )
    assert mes_b.status_code == 201
    mes_b_data = mes_b.json()
    assert mes_b_data["username"] == "test_user_B"
    assert mes_b_data["user_id"] == user_b_id
    
    get_response = client_b.get("/api/messages")
    assert get_response.status_code == 200
    messages = get_response.json()
    
    contents = [m["content"] for m in messages]
    assert "Сообщение пользователя A" in contents
    assert "Сообщение пользователя B" in contents
    
    for msg in messages:
        if msg["content"] == "Сообщение пользователя A":
            assert msg["username"] == "test_user_A"
            assert msg["user_id"] == user_a_id
        elif msg["content"] == "Сообщение пользователя B":
            assert msg["username"] == "test_user_B"
            assert msg["user_id"] == user_b_id

    assert len(messages) >= 2
    
def test_create_message_empty_content(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    reg_response = client.post("/api/auth/register", json=payload)
    assert reg_response.status_code == 201
    
    data = reg_response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    assert "access_token" not in client.cookies
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    assert log_response.status_code == 200
    
    mes_response = client.post("/api/messages", json={"content": ""})
    assert mes_response.status_code == 422
    
    result = db_session.execute(
        select(Message).where(Message.content == "")
    )
    saved = result.scalar_one_or_none()
    assert saved is None, "Пустое сообщение не должно было сохраниться в БД"