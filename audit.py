"""Sistem işlem geçmişi (audit trail) yardımcıları."""

import veritabani


def kaydet(api_kullanici_id=None, islem_turu="", detay="", ip_adresi=None, conn=None):
    """İşlemi denetim günlüğüne yazar; varsa mevcut transaction'ı kullanır."""

    sahip = conn is None
    if sahip:
        conn = veritabani.baglanti_al()
    try:
        conn.execute(
            """
            INSERT INTO islem_gecmisi (api_kullanici_id, islem_turu, detay, ip_adresi)
            VALUES (?, ?, ?, ?)
            """,
            (api_kullanici_id, islem_turu, detay, ip_adresi),
        )
        if sahip:
            conn.commit()
        return True
    except Exception:
        if sahip:
            conn.rollback()
        return False
    finally:
        if sahip:
            conn.close()


def gecmis_listele(limit=50):
    with veritabani.baglanti_al() as conn:
        satirlar = conn.execute(
            """
            SELECT g.id, COALESCE(k.kullanici_adi, 'sistem') AS kullanici_adi,
                   g.islem_turu, g.detay, g.ip_adresi, g.tarih
            FROM islem_gecmisi g
            LEFT JOIN api_kullanicilari k ON g.api_kullanici_id = k.id
            ORDER BY g.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(satir) for satir in satirlar]
