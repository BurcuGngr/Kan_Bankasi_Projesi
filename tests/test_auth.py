import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth


def test_yanlis_sifreyle_giris_basarisiz(test_db):
    auth.kullanici_olustur('testuser', 'dogru-sifre-123', 'personel')
    sonuc = auth.giris_yap('testuser', 'yanlis-sifre')
    assert sonuc is None


def test_dogru_sifreyle_giris_token_donduruyor(test_db):
    auth.kullanici_olustur('testuser', 'dogru-sifre-123', 'personel')
    sonuc = auth.giris_yap('testuser', 'dogru-sifre-123')
    assert sonuc is not None
    assert 'token' in sonuc
    assert sonuc['rol'] == 'personel'


def test_gecerli_token_dogrulanabiliyor(test_db):
    auth.kullanici_olustur('testuser', 'dogru-sifre-123', 'admin')
    giris_sonucu = auth.giris_yap('testuser', 'dogru-sifre-123')
    token = giris_sonucu['token']

    dogrulama = auth.token_dogrula(token)
    assert dogrulama is not None
    assert dogrulama['kullanici_adi'] == 'testuser'
    assert dogrulama['rol'] == 'admin'


def test_uydurma_token_reddediliyor(test_db):
    dogrulama = auth.token_dogrula('bu-hic-var-olmayan-bir-token')
    assert dogrulama is None


def test_ayni_kullanici_adi_iki_kez_olusturulamiyor(test_db):
    basarili1, _ = auth.kullanici_olustur('testuser', 'sifre123', 'personel')
    basarili2, mesaj2 = auth.kullanici_olustur('testuser', 'baska-sifre', 'admin')
    assert basarili1 is True
    assert basarili2 is False
    assert 'alınmış' in mesaj2.lower()


def test_cikis_yapinca_token_gecersiz_oluyor(test_db):
    auth.kullanici_olustur('testuser', 'sifre123', 'personel')
    giris_sonucu = auth.giris_yap('testuser', 'sifre123')
    token = giris_sonucu['token']

    assert auth.token_dogrula(token) is not None  # önce geçerli
    auth.cikis_yap(token)
    assert auth.token_dogrula(token) is None  # çıkış sonrası geçersiz