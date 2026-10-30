from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timezone
from app.users.jwt import decode_access_token
from app.main import app
from app.users.models import User

def test_successful_registration(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 201
    
    data = response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    result = db_session.execute(select(User).where(User.username == "test_user"))
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.email == "test_user@example.com"
    
def test_re_registration(db_session):
    client = TestClient(app=app)
    
    payload_one = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password",
    }
    
    payload_two = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password",
    }
    
    response_one = client.post("/api/auth/register", json=payload_one)
    
    assert response_one.status_code == 201
    
    data = response_one.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    response_two = client.post("/api/auth/register", json=payload_two)
    
    assert response_two.status_code == 409
    assert response_two.json() == {
        "detail": "Такой пользователь уже существует"
    }
    
def test_incorrect_accounting_data(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 401
    assert response.json() == {
        "detail": "Неверный логин или пароль"
    }
    
def test_login_successful(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 201
    
    data = response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    
    assert log_response.status_code == 200
    
    log_data = log_response.json()
    assert log_data["username"] == "test_user"
    assert log_data["email"] == "test_user@example.com"
    assert "id" in log_data
    
    created_at = datetime.fromisoformat(log_data["created_at"])
    now = datetime.now(timezone.utc)
    
    assert abs((now - created_at).total_seconds()) < 5, (
        f"created_at={created_at} слишком отличается от now={now}"
    )
    
    assert "access_token" in client.cookies, "Токен не устанавливает в cookie"
    token = client.cookies["access_token"]
    assert token is not None
    assert token != ""
    
    decode_user_id = decode_access_token(token)
    assert decode_user_id == data["id"]
    
def test_login_wrong_password(db_session):
    client = TestClient(app=app)
    
    payload = {
        "username": "test_user",
        "email": "test_user@example.com",
        "password": "test_password"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 201
    
    data = response.json()
    assert data["username"] == "test_user"
    assert data["email"] == "test_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data
    
    log_payload = {
        "username": "test_user",
        "password": "wrong_password"
    }
    
    response = client.post("/api/auth/login", json=log_payload)
    
    assert response.status_code == 401
    assert response.json() == {
        "detail": "Неверный логин или пароль"
    }
    
    assert "access_token" not in client.cookies