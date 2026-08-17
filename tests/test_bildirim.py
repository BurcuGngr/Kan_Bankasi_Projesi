"""
smtplib.SMTP'yi gerçekten çağırmadan (mock ile sahteleyerek) bildirim.py'nin
mantığını test eder. Neden gerçek e-posta göndermiyoruz: birim testleri asla
gerçek dış servislere (SMTP sunucusu, ödeme API'si, vs.) bağlanmamalı -
yavaş olur, internet gerektirir, ve testin sonucu senin kontrolünde olmayan
bir dış sisteme bağımlı hale gelir. Mock, "SMTP sunucusu çağrıldı mı,
doğru parametrelerle mi çağrıldı" sorusunu, gerçek bağlantı kurmadan cevaplar.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
import bildirim


def test_smtp_bilgisi_eksikse_gonderilmez(monkeypatch):
    monkeypatch.delenv('SMTP_KULLANICI', raising=False)
    monkeypatch.delenv('SMTP_SIFRE', raising=False)

    basarili, mesaj = bildirim.eposta_gonder('test@example.com', 'Konu', 'İçerik')

    assert basarili is False
    assert 'ayarlanmamış' in mesaj


def test_alici_adresi_bossa_gonderilmez():
    basarili, mesaj = bildirim.eposta_gonder('', 'Konu', 'İçerik')
    assert basarili is False


@patch('bildirim.smtplib.SMTP')
def test_dogru_bilgilerle_smtp_dogru_cagriliyor(mock_smtp_class, monkeypatch):
    monkeypatch.setenv('SMTP_KULLANICI', 'gonderen@example.com')
    monkeypatch.setenv('SMTP_SIFRE', 'sahte-sifre')

    # SMTP() bir 'with' bloğu içinde kullanılıyor (context manager),
    # bu yüzden mock'un __enter__ metodunu da sahteleştirmemiz gerekiyor.
    mock_sunucu = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_sunucu

    basarili, mesaj = bildirim.eposta_gonder('alici@example.com', 'Acil Kan İhtiyacı', 'Test içeriği')

    assert basarili is True
    mock_sunucu.starttls.assert_called_once()
    mock_sunucu.login.assert_called_once_with('gonderen@example.com', 'sahte-sifre')
    mock_sunucu.send_message.assert_called_once()


@patch('bildirim.smtplib.SMTP')
def test_smtp_kimlik_hatasi_dogru_yakalaniyor(mock_smtp_class, monkeypatch):
    import smtplib
    monkeypatch.setenv('SMTP_KULLANICI', 'gonderen@example.com')
    monkeypatch.setenv('SMTP_SIFRE', 'yanlis-sifre')

    mock_sunucu = MagicMock()
    mock_sunucu.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Auth failed')
    mock_smtp_class.return_value.__enter__.return_value = mock_sunucu

    basarili, mesaj = bildirim.eposta_gonder('alici@example.com', 'Konu', 'İçerik')

    assert basarili is False
    assert 'kimlik doğrulama' in mesaj.lower()


def test_bildirim_metni_kan_grubunu_iceriyor():
    konu, icerik = bildirim.acil_kan_ihtiyaci_bildirimi_olustur('0 Rh-')
    assert '0 Rh-' in konu
    assert '0 Rh-' in icerik