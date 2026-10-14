"""SQLite veritabanı bağlantısı ve şema yönetimi.

Varsayılan veritabanı proje içindeki ``data/kan_bankasi.db`` dosyasıdır;
``DATABASE_PATH`` ortam değişkeniyle farklı bir yol seçilebilir.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


PROJE_DIZINI = Path(__file__).resolve().parent
DB_YOLU = Path(os.environ.get("DATABASE_PATH", PROJE_DIZINI / "data" / "kan_bankasi.db"))


def veritabani_yolunu_ayarla(yol: str | os.PathLike[str]) -> None:
    """Test veya farklı çalışma ortamı için etkin veritabanı yolunu değiştirir."""

    global DB_YOLU
    DB_YOLU = Path(yol)


def baglanti_al() -> sqlite3.Connection:
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SEMA = """
CREATE TABLE IF NOT EXISTS kan_gruplari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grup_adi TEXT UNIQUE NOT NULL,
    kritik_esik INTEGER NOT NULL DEFAULT 5 CHECK (kritik_esik >= 0)
);

CREATE TABLE IF NOT EXISTS bagiscilar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_no TEXT UNIQUE,
    kan_grubu_id INTEGER NOT NULL REFERENCES kan_gruplari(id),
    ad TEXT NOT NULL,
    soyad TEXT NOT NULL,
    cinsiyet TEXT NOT NULL CHECK (cinsiyet IN ('Kadın', 'Erkek')),
    birim TEXT NOT NULL,
    telefon TEXT UNIQUE NOT NULL,
    eposta TEXT,
    bildirim_izni INTEGER NOT NULL DEFAULT 1 CHECK (bildirim_izni IN (0, 1)),
    gece_aranir_mi INTEGER NOT NULL DEFAULT 0 CHECK (gece_aranir_mi IN (0, 1)),
    son_bagis_tarihi TEXT,
    olusturma_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saglik_engelleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id) ON DELETE CASCADE,
    tur TEXT NOT NULL,
    aciklama TEXT NOT NULL,
    baslangic_tarihi TEXT,
    bitis_tarihi TEXT,
    kalici_mi INTEGER NOT NULL DEFAULT 0 CHECK (kalici_mi IN (0, 1)),
    aktif_mi INTEGER NOT NULL DEFAULT 1 CHECK (aktif_mi IN (0, 1))
);

CREATE TABLE IF NOT EXISTS api_kullanicilari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici_adi TEXT UNIQUE NOT NULL,
    sifre_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'personel' CHECK (rol IN ('admin', 'personel')),
    olusturma_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_kullanici_id INTEGER NOT NULL REFERENCES api_kullanicilari(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    son_kullanma_tarihi TEXT NOT NULL,
    son_islem_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_adresi TEXT
);

CREATE TABLE IF NOT EXISTS bagisci_hesaplari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_id INTEGER UNIQUE NOT NULL REFERENCES bagiscilar(id) ON DELETE CASCADE,
    kullanici_adi TEXT UNIQUE NOT NULL,
    sifre_hash TEXT NOT NULL,
    aktif_mi INTEGER NOT NULL DEFAULT 1 CHECK (aktif_mi IN (0, 1)),
    olusturma_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bagisci_oturumlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_hesabi_id INTEGER NOT NULL REFERENCES bagisci_hesaplari(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    son_kullanma_tarihi TEXT NOT NULL,
    son_islem_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_adresi TEXT
);

CREATE TABLE IF NOT EXISTS bagisci_on_degerlendirmeleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id) ON DELETE CASCADE,
    dovme_piercing_mi INTEGER NOT NULL DEFAULT 0 CHECK (dovme_piercing_mi IN (0, 1)),
    dovme_tarihi TEXT,
    ates_enfeksiyon_mi INTEGER NOT NULL DEFAULT 0 CHECK (ates_enfeksiyon_mi IN (0, 1)),
    antibiyotik_ilac_mi INTEGER NOT NULL DEFAULT 0 CHECK (antibiyotik_ilac_mi IN (0, 1)),
    ameliyat_transfuzyon_mi INTEGER NOT NULL DEFAULT 0 CHECK (ameliyat_transfuzyon_mi IN (0, 1)),
    hamilelik_emzirme_mi INTEGER NOT NULL DEFAULT 0 CHECK (hamilelik_emzirme_mi IN (0, 1)),
    aciklama TEXT,
    durum TEXT NOT NULL DEFAULT 'BİLDİRİLDİ' CHECK (durum IN ('BİLDİRİLDİ', 'DEĞERLENDİRİLDİ')),
    kayit_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bagislar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id),
    kan_grubu_id INTEGER NOT NULL REFERENCES kan_gruplari(id),
    bilesen_turu TEXT NOT NULL,
    unite_sayisi INTEGER NOT NULL DEFAULT 1 CHECK (unite_sayisi > 0),
    bagis_tarihi TEXT NOT NULL DEFAULT CURRENT_DATE,
    kaydeden_api_kullanici_id INTEGER REFERENCES api_kullanicilari(id)
);

CREATE TABLE IF NOT EXISTS kan_torbalari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unite_kodu TEXT UNIQUE,
    bagis_id INTEGER NOT NULL REFERENCES bagislar(id),
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id),
    kan_grubu_id INTEGER NOT NULL REFERENCES kan_gruplari(id),
    bilesen_turu TEXT NOT NULL,
    bagis_tarihi TEXT NOT NULL,
    son_kullanma_tarihi TEXT NOT NULL,
    saklama_konumu TEXT NOT NULL DEFAULT 'Soğuk Oda A',
    durum TEXT NOT NULL DEFAULT 'AKTİF' CHECK (durum IN ('AKTİF', 'KULLANILDI', 'SÜRESİ DOLDU', 'KARANTİNA')),
    kullanilma_tarihi TEXT
);

CREATE TABLE IF NOT EXISTS kan_cikislari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kan_grubu_id INTEGER NOT NULL REFERENCES kan_gruplari(id),
    bilesen_turu TEXT NOT NULL,
    adet INTEGER NOT NULL CHECK (adet > 0),
    talep_eden_birim TEXT NOT NULL,
    cikis_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    kaydeden_api_kullanici_id INTEGER REFERENCES api_kullanicilari(id)
);

CREATE TABLE IF NOT EXISTS puan_hareketleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id) ON DELETE CASCADE,
    bagis_id INTEGER REFERENCES bagislar(id) ON DELETE SET NULL,
    puan INTEGER NOT NULL,
    neden TEXT NOT NULL,
    tarih TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acil_cagrilar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kan_grubu_id INTEGER NOT NULL REFERENCES kan_gruplari(id),
    aciklama TEXT NOT NULL,
    aday_sayisi INTEGER NOT NULL DEFAULT 0,
    durum TEXT NOT NULL DEFAULT 'HAZIR' CHECK (durum IN ('HAZIR', 'KAPATILDI')),
    olusturan_api_kullanici_id INTEGER REFERENCES api_kullanicilari(id) ON DELETE SET NULL,
    olusturma_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eposta_gonderimleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acil_cagri_id INTEGER NOT NULL REFERENCES acil_cagrilar(id) ON DELETE CASCADE,
    bagisci_id INTEGER NOT NULL REFERENCES bagiscilar(id) ON DELETE CASCADE,
    alici_eposta TEXT NOT NULL,
    konu TEXT NOT NULL,
    durum TEXT NOT NULL CHECK (durum IN ('GÖNDERİLDİ', 'BAŞARISIZ')),
    hata_mesaji TEXT,
    gonderim_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS islem_gecmisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_kullanici_id INTEGER REFERENCES api_kullanicilari(id) ON DELETE SET NULL,
    islem_turu TEXT NOT NULL,
    detay TEXT NOT NULL,
    tarih TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_adresi TEXT
);

CREATE INDEX IF NOT EXISTS idx_torba_stok
    ON kan_torbalari(kan_grubu_id, bilesen_turu, durum, son_kullanma_tarihi);
CREATE INDEX IF NOT EXISTS idx_engel_bagisci
    ON saglik_engelleri(bagisci_id, aktif_mi);
CREATE INDEX IF NOT EXISTS idx_puan_bagisci
    ON puan_hareketleri(bagisci_id, tarih);
CREATE INDEX IF NOT EXISTS idx_cagri_kan_grubu
    ON acil_cagrilar(kan_grubu_id, durum, olusturma_tarihi);
CREATE INDEX IF NOT EXISTS idx_eposta_cagri
    ON eposta_gonderimleri(acil_cagri_id, gonderim_tarihi);
CREATE INDEX IF NOT EXISTS idx_on_degerlendirme_bagisci
    ON bagisci_on_degerlendirmeleri(bagisci_id, kayit_tarihi);
"""


def veritabani_baslat() -> None:
    """Tabloları veri silmeden oluşturur veya eksik yapıları tamamlar."""

    with baglanti_al() as conn:
        conn.executescript(SEMA)


def veritabani_sifirla() -> None:
    """Yalnızca otomatik testlerde kullanılan kontrollü sıfırlama yardımcısı."""

    if DB_YOLU.exists():
        DB_YOLU.unlink()
    veritabani_baslat()


if __name__ == "__main__":
    veritabani_baslat()
    print(f"Veritabanı hazır: {DB_YOLU}")
