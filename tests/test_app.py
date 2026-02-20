from pathlib import Path

import pytest

from shopify_app.app import create_app


@pytest.fixture()
def app(tmp_path: Path):
    db_path = tmp_path / "test.db"
    app = create_app({"TESTING": True, "DATABASE": str(db_path), "SECRET_KEY": "test"})
    with app.app_context():
        pass
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client):
    client.post(
        "/register",
        data={"name": "Test User", "email": "test@example.com", "password": "secret"},
    )
    return client.post("/login", data={"email": "test@example.com", "password": "secret"})


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Shopify Lite" in response.data


def test_checkout_flow(client):
    register_and_login(client)
    client.post("/cart/add/1")
    cart_response = client.get("/cart")
    assert b"Nebula Headphones" in cart_response.data

    checkout_response = client.post("/checkout", follow_redirects=True)
    assert checkout_response.status_code == 200
    assert b"Order placed successfully" in checkout_response.data


def test_admin_can_open_product_admin(client):
    client.post("/login", data={"email": "admin@shopify.local", "password": "admin123"})
    response = client.get("/admin/products")
    assert response.status_code == 200
    assert b"Admin product management" in response.data
