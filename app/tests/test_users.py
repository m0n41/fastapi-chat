import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_authorized_user(db_session):
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
    
    assert "access_token" not in client.cookies
    
    log_payload = {
        "username": "test_user",
        "password": "test_password"
    }
    
    log_response = client.post("/api/auth/login", json=log_payload)
    assert log_response.status_code == 200
    
    assert "access_token" in client.cookies
    token = client.cookies["access_token"]
    assert token != ""
    
    me_response = client.get("/api/users/me")
    assert me_response.status_code == 200
    
    me_data = me_response.json()
    assert me_data["username"] == "test_user"
    assert me_data["email"] == "test_user@example.com"
    assert me_data["id"] == data["id"]
    assert "hashed_password" not in me_data
    
def test_without_authorization(db_session):
    client = TestClient(app=app)
    
    response = client.get("/api/users/me")
    assert response.status_code == 401