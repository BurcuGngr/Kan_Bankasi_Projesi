"""
Kimlik doğrulama mantığı. servisler.py'den ayrı tutuluyor çünkü bu,
iş mantığından (kan bankası kuralları) tamamen farklı bir sorumluluk -
"kim bu sistemi kullanabilir" sorusu, "sistem ne yapar" sorusundan ayrı.
"""
import sqlite3
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_YOLU = 'kan_bankasi.db'
TOKEN_GECERLILIK_SAAT = 8  # Bir vardiya süresi varsayımıyla 8 saat


def veritabani_baglan():
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    return conn


def kullanici_olustur(kullanici_adi, sifre, rol='personel'):
    """
    Yeni bir API kullanıcısı oluşturur. Şifre asla düz metin olarak
    saklanmaz - generate_password_hash tek yönlü bir hash üretir,
    bu hash'ten orijinal şifreye geri dönülemez.
    """
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        sifre_hash = generate_password_hash(sifre)
        cursor.execute(
            "INSERT INTO api_kullanicilari (kullanici_adi, sifre_hash, rol) VALUES (?, ?, ?)",
            (kullanici_adi, sifre_hash, rol)
        )
        conn.commit()
        return True, "Kullanıcı oluşturuldu."
    except sqlite3.IntegrityError:
        return False, "Bu kullanıcı adı zaten alınmış."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def giris_yap(kullanici_adi, sifre):
    """
    Kullanıcı adı/şifre doğruysa yeni bir token üretir ve döner.
    Yanlışsa None döner - ama HANGİ kısmın yanlış olduğunu (kullanıcı adı mı,
    şifre mi) söylemez. Bu kasıtlı: "kullanıcı adı yok" ve "şifre yanlış"
    mesajlarını ayırmak, saldırganın hangi kullanıcı adlarının var olduğunu
    denemesine (enumeration) yardımcı olur.
    """
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, sifre_hash, rol FROM api_kullanicilari WHERE kullanici_adi = ?",
            (kullanici_adi,)
        )
        kullanici = cursor.fetchone()

        if not kullanici or not check_password_hash(kullanici['sifre_hash'], sifre):
            return None

        token = secrets.token_hex(32)
        simdi = datetime.now()
        bitis = simdi + timedelta(hours=TOKEN_GECERLILIK_SAAT)

        cursor.execute(
            "INSERT INTO api_oturumlari (token, api_kullanici_id, olusturma_tarihi, gecerlilik_tarihi) VALUES (?, ?, ?, ?)",
            (token, kullanici['id'], simdi.isoformat(), bitis.isoformat())
        )
        conn.commit()

        return {'token': token, 'rol': kullanici['rol'], 'gecerlilik_saat': TOKEN_GECERLILIK_SAAT}
    finally:
        conn.close()


def token_dogrula(token):
    """
    Token geçerliyse (var olan ve süresi dolmamış) kullanıcı bilgisini döner.
    Geçersizse None döner.
    """
    if not token:
        return None

    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT o.gecerlilik_tarihi, k.id, k.kullanici_adi, k.rol
            FROM api_oturumlari o
            JOIN api_kullanicilari k ON o.api_kullanici_id = k.id
            WHERE o.token = ?
        """, (token,))
        satir = cursor.fetchone()

        if not satir:
            return None

        gecerlilik = datetime.fromisoformat(satir['gecerlilik_tarihi'])
        if datetime.now() > gecerlilik:
            return None  # Token süresi dolmuş

        return {'id': satir['id'], 'kullanici_adi': satir['kullanici_adi'], 'rol': satir['rol']}
    finally:
        conn.close()


def cikis_yap(token):
    """Token'ı veritabanından siler - kullanıcı 'çıkış yap' dediğinde çağrılır."""
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM api_oturumlari WHERE token = ?", (token,))
        conn.commit()
        return True
    finally:
        conn.close()