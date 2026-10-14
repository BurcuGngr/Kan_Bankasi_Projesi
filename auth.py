"""Yönetici/personel ve bağışçı hesapları için token tabanlı kimlik doğrulama."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import veritabani
import audit


OTURUM_SURESI_SAAT = 8
ORNEK_EPOSTA_ALANLARI = {"example.com", "example.net", "example.org", "example.test"}


def bagisci_kaydi_olustur(veri: dict, ip_adresi: str | None = None) -> tuple[bool, dict | str]:
    """Bağışçı kaydı ile giriş hesabını tek transaction içinde oluşturur."""

    zorunlu = [
        "ad", "soyad", "cinsiyet", "birim", "telefon", "eposta",
        "kan_grubu_id", "kullanici_adi", "sifre",
    ]
    eksikler = [alan for alan in zorunlu if not str(veri.get(alan, "")).strip()]
    if eksikler:
        return False, f"Zorunlu alanlar eksik: {', '.join(eksikler)}"
    if veri["cinsiyet"] not in {"Kadın", "Erkek"}:
        return False, "Cinsiyet Kadın veya Erkek olarak seçilmelidir."

    kullanici_adi = str(veri["kullanici_adi"]).strip()
    sifre = str(veri["sifre"])
    eposta = str(veri["eposta"]).strip().lower()
    if len(kullanici_adi) < 3:
        return False, "Kullanıcı adı en az 3 karakter olmalıdır."
    if len(sifre) < 8:
        return False, "Şifre en az 8 karakter olmalıdır."
    if "@" not in eposta or eposta.rsplit("@", 1)[1] in ORNEK_EPOSTA_ALANLARI:
        return False, "Bildirim alabileceğiniz geçerli bir e-posta adresi yazın."

    try:
        with veritabani.baglanti_al() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bagiscilar
                    (kan_grubu_id, ad, soyad, cinsiyet, birim, telefon, eposta,
                     bildirim_izni, gece_aranir_mi)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
                """,
                (
                    int(veri["kan_grubu_id"]), str(veri["ad"]).strip(),
                    str(veri["soyad"]).strip(), veri["cinsiyet"],
                    str(veri["birim"]).strip(), str(veri["telefon"]).strip(), eposta,
                ),
            )
            bagisci_id = cursor.lastrowid
            bagisci_no = f"KB-{date.today().year}-{bagisci_id:04d}"
            conn.execute(
                "UPDATE bagiscilar SET bagisci_no = ? WHERE id = ?",
                (bagisci_no, bagisci_id),
            )
            conn.execute(
                """
                INSERT INTO bagisci_hesaplari (bagisci_id, kullanici_adi, sifre_hash)
                VALUES (?, ?, ?)
                """,
                (bagisci_id, kullanici_adi, generate_password_hash(sifre)),
            )
            audit.kaydet(
                None, "BAĞIŞÇI_KAYDI",
                f"{bagisci_no} numaralı bağışçı çevrim içi kayıt oluşturdu.",
                ip_adresi, conn,
            )
        return True, {
            "bagisci_id": bagisci_id,
            "bagisci_no": bagisci_no,
            "kullanici_adi": kullanici_adi,
        }
    except (ValueError, TypeError):
        return False, "Geçerli bir kan grubu seçilmelidir."
    except sqlite3.IntegrityError as exc:
        hata = str(exc)
        if "bagisci_hesaplari.kullanici_adi" in hata:
            return False, "Bu kullanıcı adı daha önce alınmış."
        if "bagiscilar.telefon" in hata:
            return False, "Bu telefon numarasıyla kayıtlı bir bağışçı zaten var."
        if "FOREIGN KEY" in hata:
            return False, "Seçilen kan grubu bulunamadı."
        return False, "Bağışçı kaydı oluşturulamadı. Bilgileri kontrol edin."


def kullanici_olustur(kullanici_adi: str, sifre: str, rol: str = "personel"):
    if rol not in {"admin", "personel"}:
        return False, "Rol yalnızca admin veya personel olabilir."
    try:
        with veritabani.baglanti_al() as conn:
            conn.execute(
                "INSERT INTO api_kullanicilari (kullanici_adi, sifre_hash, rol) VALUES (?, ?, ?)",
                (kullanici_adi.strip(), generate_password_hash(sifre), rol),
            )
        return True, "Kullanıcı başarıyla oluşturuldu."
    except Exception as exc:
        return False, f"Kullanıcı oluşturulamadı: {exc}"


def giris_yap(kullanici_adi: str, sifre: str, ip_adresi: str | None = None) -> dict:
    simdi = datetime.now()
    with veritabani.baglanti_al() as conn:
        conn.execute("DELETE FROM api_oturumlari WHERE son_kullanma_tarihi < ?", (simdi.isoformat(),))
        kullanici = conn.execute(
            "SELECT id, kullanici_adi, sifre_hash, rol FROM api_kullanicilari WHERE kullanici_adi = ?",
            (kullanici_adi.strip(),),
        ).fetchone()

        if not kullanici or not check_password_hash(kullanici["sifre_hash"], sifre):
            return {"basarili": False, "mesaj": "Hatalı kullanıcı adı veya şifre."}

        token = secrets.token_urlsafe(32)
        son_kullanma = simdi + timedelta(hours=OTURUM_SURESI_SAAT)
        conn.execute(
            """
            INSERT INTO api_oturumlari
                (api_kullanici_id, token, son_kullanma_tarihi, son_islem_tarihi, ip_adresi)
            VALUES (?, ?, ?, ?, ?)
            """,
            (kullanici["id"], token, son_kullanma.isoformat(), simdi.isoformat(), ip_adresi),
        )

    return {
        "basarili": True,
        "token": token,
        "kullanici": {
            "id": kullanici["id"],
            "kullanici_adi": kullanici["kullanici_adi"],
            "rol": kullanici["rol"],
            "rol_etiketi": "Yönetici" if kullanici["rol"] == "admin" else "Personel",
        },
        "oturum_suresi_saat": OTURUM_SURESI_SAAT,
    }


def token_dogrula(token: str | None) -> dict | None:
    if not token:
        return None
    simdi = datetime.now()
    with veritabani.baglanti_al() as conn:
        kayit = conn.execute(
            """
            SELECT k.id, k.kullanici_adi, k.rol, o.id AS oturum_id, o.son_kullanma_tarihi
            FROM api_oturumlari o
            JOIN api_kullanicilari k ON k.id = o.api_kullanici_id
            WHERE o.token = ?
            """,
            (token,),
        ).fetchone()
        if not kayit or datetime.fromisoformat(kayit["son_kullanma_tarihi"]) <= simdi:
            if kayit:
                conn.execute("DELETE FROM api_oturumlari WHERE id = ?", (kayit["oturum_id"],))
            return None
        conn.execute(
            "UPDATE api_oturumlari SET son_islem_tarihi = ? WHERE id = ?",
            (simdi.isoformat(), kayit["oturum_id"]),
        )
    return {
        "id": kayit["id"],
        "kullanici_adi": kayit["kullanici_adi"],
        "rol": kayit["rol"],
    }


def cikis_yap(token: str | None) -> None:
    if not token:
        return
    with veritabani.baglanti_al() as conn:
        conn.execute("DELETE FROM api_oturumlari WHERE token = ?", (token,))


def bagisci_giris_yap(kullanici_adi: str, sifre: str, ip_adresi: str | None = None) -> dict:
    """Bağışçı hesabını ayrı oturum tablosunda doğrular."""

    simdi = datetime.now()
    with veritabani.baglanti_al() as conn:
        conn.execute(
            "DELETE FROM bagisci_oturumlari WHERE son_kullanma_tarihi < ?",
            (simdi.isoformat(),),
        )
        hesap = conn.execute(
            """
            SELECT h.id, h.bagisci_id, h.kullanici_adi, h.sifre_hash,
                   b.bagisci_no, b.ad, b.soyad
            FROM bagisci_hesaplari h
            JOIN bagiscilar b ON b.id = h.bagisci_id
            WHERE h.kullanici_adi = ? AND h.aktif_mi = 1
            """,
            (kullanici_adi.strip(),),
        ).fetchone()
        if not hesap or not check_password_hash(hesap["sifre_hash"], sifre):
            return {"basarili": False, "mesaj": "Hatalı bağışçı kullanıcı adı veya şifre."}

        token = secrets.token_urlsafe(32)
        son_kullanma = simdi + timedelta(hours=OTURUM_SURESI_SAAT)
        conn.execute(
            """
            INSERT INTO bagisci_oturumlari
                (bagisci_hesabi_id, token, son_kullanma_tarihi, son_islem_tarihi, ip_adresi)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hesap["id"], token, son_kullanma.isoformat(), simdi.isoformat(), ip_adresi),
        )

    return {
        "basarili": True,
        "token": token,
        "kullanici": {
            "bagisci_id": hesap["bagisci_id"],
            "bagisci_no": hesap["bagisci_no"],
            "kullanici_adi": hesap["kullanici_adi"],
            "ad_soyad": f"{hesap['ad']} {hesap['soyad']}",
            "rol": "bagisci",
            "rol_etiketi": "Bağışçı",
        },
        "oturum_suresi_saat": OTURUM_SURESI_SAAT,
    }


def bagisci_token_dogrula(token: str | None) -> dict | None:
    if not token:
        return None
    simdi = datetime.now()
    with veritabani.baglanti_al() as conn:
        kayit = conn.execute(
            """
            SELECT h.id AS hesap_id, h.bagisci_id, h.kullanici_adi,
                   o.id AS oturum_id, o.son_kullanma_tarihi
            FROM bagisci_oturumlari o
            JOIN bagisci_hesaplari h ON h.id = o.bagisci_hesabi_id
            WHERE o.token = ? AND h.aktif_mi = 1
            """,
            (token,),
        ).fetchone()
        if not kayit or datetime.fromisoformat(kayit["son_kullanma_tarihi"]) <= simdi:
            if kayit:
                conn.execute("DELETE FROM bagisci_oturumlari WHERE id = ?", (kayit["oturum_id"],))
            return None
        conn.execute(
            "UPDATE bagisci_oturumlari SET son_islem_tarihi = ? WHERE id = ?",
            (simdi.isoformat(), kayit["oturum_id"]),
        )
    return {
        "hesap_id": kayit["hesap_id"],
        "bagisci_id": kayit["bagisci_id"],
        "kullanici_adi": kayit["kullanici_adi"],
        "rol": "bagisci",
    }


def bagisci_cikis_yap(token: str | None) -> None:
    if not token:
        return
    with veritabani.baglanti_al() as conn:
        conn.execute("DELETE FROM bagisci_oturumlari WHERE token = ?", (token,))
