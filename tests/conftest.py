import sys
from pathlib import Path

import pytest


PROJE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJE))

from app import create_app


@pytest.fixture
def app(tmp_path):
    uygulama = create_app({
        "TESTING": True,
        "DATABASE_PATH": str(tmp_path / "test.db"),
        "SEED_DEMO": True,
    })
    return uygulama


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers(client):
    yanit = client.post("/api/auth/giris", json={"kullanici_adi": "admin", "sifre": "Admin123!"})
    assert yanit.status_code == 200
    return {"Authorization": f"Bearer {yanit.get_json()['token']}"}
