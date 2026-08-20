"""
İşlem geçmişi (audit trail) kayıtlarını yönetir. servisler.py'den ayrı
tutulma nedeni: bu, iş mantığından bağımsız bir "yan etki" (cross-cutting
concern) - kan bankası kurallarıyla ilgisi yok, ama neredeyse her işlemin
yanında çalışması gerekiyor.
"""
import sqlite3
from datetime import datetime
import logging_config

DB_YOLU = 'kan_bankasi.db'
logger = logging_config.logger_al(__name__)


def veritabani_baglan():
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    return conn


def kaydet(kullanici_adi, rol, islem, detay="", ip_adresi=None):
    """
    Bir işlemi geçmişe kaydeder. Bu fonksiyon ASLA exception fırlatmamalı -
    loglama başarısız olduğu için asıl işlemin (örn. kan çıkışı) iptal
    olması kabul edilemez. Bu yüzden geniş bir try/except ile sarılı.
    """
    try:
        conn = veritabani_baglan()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO islem_gecmisi (kullanici_adi, rol, islem, detay, ip_adresi, tarih) VALUES (?, ?, ?, ?, ?, ?)",
            (kullanici_adi, rol, islem, detay, ip_adresi, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Loglama hatası sessizce yutuluyor ama konsola yazılıyor -
        # asıl işlemi asla bozmamalı, ama sorunu da görünmez kılmamalı.
        logger.error(f"Audit log kaydı başarısız oldu: {e}")


def gecmisi_getir(limit=100, kullanici_adi_filtre=None):
    """Son işlemleri, en yeniden en eskiye doğru döner."""
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        if kullanici_adi_filtre:
            cursor.execute(
                "SELECT * FROM islem_gecmisi WHERE kullanici_adi = ? ORDER BY tarih DESC LIMIT ?",
                (kullanici_adi_filtre, limit)
            )
        else:
            cursor.execute("SELECT * FROM islem_gecmisi ORDER BY tarih DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()