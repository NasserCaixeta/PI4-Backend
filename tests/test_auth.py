import pytest


@pytest.mark.anyio
async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "12345678",
        "name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.anyio
async def test_register_duplicate_email(client):
    # Primeiro registro
    await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "12345678",
    })
    # Segundo registro com mesmo email
    response = await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "87654321",
    })
    assert response.status_code == 400


@pytest.mark.anyio
async def test_login_success(client):
    # Registra usuário
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "12345678",
    })
    # Faz login
    response = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "12345678",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.anyio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "12345678",
    })
    response = await client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


@pytest.mark.anyio
async def test_me_authenticated(client):
    # Registra e pega token
    reg_response = await client.post("/auth/register", json={
        "email": "me@example.com",
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]

    # Chama /me com token
    response = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@pytest.mark.anyio
async def test_me_unauthenticated(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401  # HTTPBearer retorna 401 sem header


@pytest.mark.anyio
async def test_logout_returns_no_content(client):
    response = await client.post("/auth/logout")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_update_profile_name(client):
    reg = await client.post("/auth/register", json={
        "email": "update_name@example.com",
        "password": "12345678",
        "name": "Nome Original",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch("/auth/me", json={"name": "Novo Nome"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Novo Nome"


@pytest.mark.anyio
async def test_update_profile_password_success(client):
    reg = await client.post("/auth/register", json={
        "email": "update_pwd@example.com",
        "password": "senhavelha1",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch("/auth/me", json={
        "current_password": "senhavelha1",
        "new_password": "senhanova2",
    }, headers=headers)
    assert response.status_code == 200

    login = await client.post("/auth/login", json={
        "email": "update_pwd@example.com",
        "password": "senhanova2",
    })
    assert login.status_code == 200


@pytest.mark.anyio
async def test_update_profile_wrong_current_password(client):
    reg = await client.post("/auth/register", json={
        "email": "wrong_pwd@example.com",
        "password": "senha12345",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch("/auth/me", json={
        "current_password": "senhaerrada",
        "new_password": "senhanova9",
    }, headers=headers)
    assert response.status_code == 400
    assert "incorreta" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_update_profile_missing_current_password(client):
    reg = await client.post("/auth/register", json={
        "email": "missing_pwd@example.com",
        "password": "senha12345",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch("/auth/me", json={
        "new_password": "senhanova9",
    }, headers=headers)
    assert response.status_code == 400
