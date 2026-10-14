"""SMTP üzerinden acil kan ihtiyacı e-postaları gönderir."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


PROJE_DIZINI = Path(__file__).resolve().parent
ORNEK_EPOSTA_ALANLARI = {"example.com", "example.net", "example.org", "example.test"}
TEKNIK_TEST_IFADELERI = ("smtp", "bağlantı doğrulama", "dogrulama", "test")


def _bagisciya_uygun_aciklama(aciklama: str) -> str:
    """Teknik test ifadelerinin bağışçı e-postasına taşınmasını önler."""

    temiz = " ".join(str(aciklama or "").split())
    kucuk = temiz.casefold()
    if not temiz or any(ifade in kucuk for ifade in TEKNIK_TEST_IFADELERI):
        return "Acil servis için uygun bağışçı çağrısı"
    return temiz


def _yerel_env_degerleri() -> dict[str, str]:
    """Ek bağımlılık gerektirmeden proje kökündeki .env dosyasını okur."""

    env_yolu = PROJE_DIZINI / ".env"
    if not env_yolu.exists():
        return {}
    degerler: dict[str, str] = {}
    try:
        for ham_satir in env_yolu.read_text(encoding="utf-8").splitlines():
            satir = ham_satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            anahtar, deger = satir.split("=", 1)
            degerler[anahtar.strip()] = deger.strip().strip('"').strip("'")
    except OSError:
        return {}
    return degerler


def _ayar(anahtar: str, varsayilan: str = "") -> str:
    return os.environ.get(anahtar) or _yerel_env_degerleri().get(anahtar, varsayilan)


def _smtp_ayarlari() -> dict:
    sunucu = _ayar("SMTP_SUNUCU", "smtp.gmail.com")
    port_ham = _ayar("SMTP_PORT", "587")
    kullanici = _ayar("SMTP_KULLANICI")
    sifre = _ayar("SMTP_SIFRE")
    try:
        port = int(port_ham)
    except ValueError:
        port = 587
    return {
        "yapilandirildi": bool(sunucu and kullanici and sifre),
        "sunucu": sunucu,
        "port": port,
        "gonderen": kullanici or None,
        "sifre": sifre,
    }


def smtp_ayar_durumu() -> dict:
    """Kullanıcı adı ve parolayı açığa çıkarmadan SMTP durumunu döndürür."""

    ayarlar = _smtp_ayarlari()
    return {
        "yapilandirildi": ayarlar["yapilandirildi"],
        "sunucu": ayarlar["sunucu"],
        "port": ayarlar["port"],
    }


def acil_kan_ihtiyaci_bildirimi_olustur(
    kan_grubu_adi: str,
    aciklama: str,
    hastane_adi: str = "Kan Bankası",
) -> tuple[str, str]:
    """Acil çağrı için standart konu ve düz metin gövdesi oluşturur."""

    konu = f"Acil kan ihtiyacı: {kan_grubu_adi}"
    bagisci_aciklamasi = _bagisciya_uygun_aciklama(aciklama)
    icerik = f"""Sayın Bağışçımız,

{hastane_adi} bünyesinde {kan_grubu_adi} kan grubuna yönelik acil bağış ihtiyacı oluşmuştur.

İhtiyaç bilgisi: {bagisci_aciklamasi}

Bağış yapabilecek durumdaysanız Kan Bağış Merkezi ile iletişime geçmenizi rica ederiz. Kesin bağış uygunluğu merkezde yapılacak değerlendirme sonrasında belirlenir.

Sağlıklı günler dileriz.
Kan Bankası Bildirim Sistemi
"""
    return konu, icerik


def eposta_gonder(alici_eposta: str, konu: str, icerik: str) -> tuple[bool, str]:
    """Yapılandırılmış SMTP hesabıyla tek bir e-posta gönderir."""

    ayarlar = _smtp_ayarlari()
    if not ayarlar["yapilandirildi"]:
        return False, "SMTP ayarları eksik. .env dosyasındaki kullanıcı ve uygulama şifresini tamamlayın."
    if not alici_eposta or "@" not in alici_eposta:
        return False, "Geçerli bir alıcı e-posta adresi bulunamadı."
    alan_adi = alici_eposta.rsplit("@", 1)[1].strip().lower()
    if alan_adi in ORNEK_EPOSTA_ALANLARI:
        return False, (
            "Bu bağışçıda yalnızca örnek e-posta adresi var. "
            "Gerçek bir alıcı adresi kaydedilmelidir."
        )

    mesaj = EmailMessage()
    mesaj["From"] = _ayar("SMTP_GONDEREN_ADI", "Kan Bankası Bildirim Sistemi") + f" <{ayarlar['gonderen']}>"
    mesaj["To"] = alici_eposta
    mesaj["Subject"] = konu
    mesaj.set_content(icerik)

    try:
        baglam = ssl.create_default_context()
        if ayarlar["port"] == 465:
            with smtplib.SMTP_SSL(
                ayarlar["sunucu"], ayarlar["port"], timeout=15, context=baglam
            ) as sunucu:
                sunucu.login(ayarlar["gonderen"], ayarlar["sifre"])
                sunucu.send_message(mesaj)
        else:
            with smtplib.SMTP(ayarlar["sunucu"], ayarlar["port"], timeout=15) as sunucu:
                sunucu.ehlo()
                sunucu.starttls(context=baglam)
                sunucu.ehlo()
                sunucu.login(ayarlar["gonderen"], ayarlar["sifre"])
                sunucu.send_message(mesaj)
        return True, "E-posta başarıyla gönderildi."
    except (OSError, smtplib.SMTPException) as hata:
        return False, f"E-posta gönderilemedi: {hata}"
