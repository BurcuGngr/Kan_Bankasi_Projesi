"""
Flask'ın kendi test_client()'ı gerçek bir sunucu (python app.py) başlatmadan
HTTP isteklerini simüle eder. Böylece "sunucuyu aç, curl ile dene, kapat"
döngüsünü elle tekrar tekrar yapmak yerine, tüm bunlar otomatik ve saniyeler
içinde çalışır.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import app as flask_app_module
import auth


@pytest.fixture
def client(test_db):
    flask_app_module.app.config['TESTING'] = True
    with flask_app_module.app.test_client() as client:
        yield client


def test_health_endpoint_token_gerektirmiyor(client):
    yanit = client.get('/api/health')
    assert yanit.status_code == 200
    assert yanit.get_json()['durum'] == 'ayakta'


def test_token_olmadan_kritik_stok_401(client):
    yanit = client.get('/api/stoklar/kritik')
    assert yanit.status_code == 401


def test_yanlis_sifreyle_giris_401(client, test_db):
    auth.kullanici_olustur('testuser', 'dogru-sifre', 'personel')
    yanit = client.post('/api/auth/giris', json={'kullanici_adi': 'testuser', 'sifre': 'yanlis'})
    assert yanit.status_code == 401


def test_dogru_girisle_token_alip_veriye_erisebiliyor(client, ornek_veri):
    auth.kullanici_olustur('testuser', 'dogru-sifre', 'personel')
    giris_yaniti = client.post('/api/auth/giris', json={'kullanici_adi': 'testuser', 'sifre': 'dogru-sifre'})
    assert giris_yaniti.status_code == 200
    token = giris_yaniti.get_json()['token']

    veri_yaniti = client.get('/api/stoklar/kritik', headers={'Authorization': f'Bearer {token}'})
    assert veri_yaniti.status_code == 200


def test_personel_admin_only_endpointe_erisemez(client, ornek_veri):
    auth.kullanici_olustur('personeltest', 'sifre123', 'personel')
    giris_yaniti = client.post('/api/auth/giris', json={'kullanici_adi': 'personeltest', 'sifre': 'sifre123'})
    token = giris_yaniti.get_json()['token']

    yanit = client.get('/api/bagiscilar/uygunluk/1', headers={'Authorization': f'Bearer {token}'})
    assert yanit.status_code == 403


def test_admin_admin_only_endpointe_erisebilir(client, ornek_veri):
    auth.kullanici_olustur('admintest', 'sifre123', 'admin')
    giris_yaniti = client.post('/api/auth/giris', json={'kullanici_adi': 'admintest', 'sifre': 'sifre123'})
    token = giris_yaniti.get_json()['token']

    yanit = client.get('/api/bagiscilar/uygunluk/1', headers={'Authorization': f'Bearer {token}'})
    assert yanit.status_code == 200


def test_eksik_alanla_kan_cikis_400(client, ornek_veri):
    auth.kullanici_olustur('testuser', 'sifre123', 'admin')
    giris_yaniti = client.post('/api/auth/giris', json={'kullanici_adi': 'testuser', 'sifre': 'sifre123'})
    token = giris_yaniti.get_json()['token']

    # 'adet' alanı eksik - 400 dönmeli, 500 değil
    yanit = client.post(
        '/api/stoklar/cikis',
        json={'kan_grubu_id': 1},
        headers={'Authorization': f'Bearer {token}'}
    )
    assert yanit.status_code == 400