"""
E-posta bildirim gönderimi. SMTP kimlik bilgileri KOD İÇİNE YAZILMAZ -
ortam değişkenlerinden (environment variables) okunur. Bu proje .env
dosyasından bu değişkenleri yükler (python-dotenv ile).

ÖNEMLİ GÜVENLİK NOTU: .env dosyası ASLA git'e eklenmemeli (.gitignore'da
zaten var). İçinde gerçek e-posta şifren/uygulama şifren olacak.

Gmail kullanacaksan normal şifreni DEĞİL, bir "Uygulama Şifresi" (App
Password) oluşturman gerekir: Google Hesabı -> Güvenlik -> 2 Adımlı
Doğrulama açık olmalı -> Uygulama Şifreleri -> yeni oluştur.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv kurulu değilse sessizce devam et - belki ortam
    # değişkenleri başka bir yolla (sistem seviyesinde) zaten ayarlanmıştır.
    pass


def _smtp_ayarlarini_al():
    return {
        'sunucu': os.environ.get('SMTP_SUNUCU', 'smtp.gmail.com'),
        'port': int(os.environ.get('SMTP_PORT', 587)),
        'kullanici': os.environ.get('SMTP_KULLANICI'),
        'sifre': os.environ.get('SMTP_SIFRE'),
    }


def eposta_gonder(alici_eposta, konu, icerik):
    """
    Basit bir metin e-postası gönderir.
    Döner: (basarili: bool, mesaj: str)
    """
    if not alici_eposta:
        return False, "Alıcı e-posta adresi boş."

    ayarlar = _smtp_ayarlarini_al()
    if not ayarlar['kullanici'] or not ayarlar['sifre']:
        return False, "SMTP_KULLANICI / SMTP_SIFRE ortam değişkenleri ayarlanmamış (.env dosyasını kontrol et)."

    try:
        mesaj = MIMEMultipart()
        mesaj['From'] = ayarlar['kullanici']
        mesaj['To'] = alici_eposta
        mesaj['Subject'] = konu
        mesaj.attach(MIMEText(icerik, 'plain', 'utf-8'))

        with smtplib.SMTP(ayarlar['sunucu'], ayarlar['port']) as sunucu:
            sunucu.starttls()
            sunucu.login(ayarlar['kullanici'], ayarlar['sifre'])
            sunucu.send_message(mesaj)

        return True, "E-posta gönderildi."
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP kimlik doğrulama hatası - kullanıcı adı/şifre (uygulama şifresi) yanlış."
    except Exception as e:
        return False, f"E-posta gönderilirken hata: {e}"


def acil_kan_ihtiyaci_bildirimi_olustur(kan_grubu_adi, hastane_adi="Hastane"):
    """Acil kan ihtiyacı e-postasının konu ve içeriğini hazırlar."""
    konu = f"🩸 ACİL: {kan_grubu_adi} Kan Bağışına İhtiyacımız Var"
    icerik = f"""Merhaba,

{hastane_adi} olarak {kan_grubu_adi} kan grubunda acil ihtiyacımız var.

Daha önce bağışçı olarak kayıt olduğunuz için size ulaşıyoruz. Bağış
yapmaya uygunsanız ve müsaitseniz, en kısa sürede kan bankamıza
başvurmanızı rica ederiz.

Bu bildirim otomatik olarak gönderilmiştir.

Teşekkürler,
{hastane_adi} Kan Bankası
"""
    return konu, icerik