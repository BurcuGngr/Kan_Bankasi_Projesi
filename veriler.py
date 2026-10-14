"""Ekran kaydı ve geliştirme için anonim örnek veri yükleyicisi."""

from __future__ import annotations

from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import servisler
import veritabani


KAN_GRUPLARI = [
    ("A Rh+", 5), ("A Rh-", 5), ("B Rh+", 5), ("B Rh-", 5),
    ("0 Rh+", 5), ("0 Rh-", 5), ("AB Rh+", 5), ("AB Rh-", 5),
]


def _oncelikli_cagri_orneklerini_tamamla(conn, bugun: date) -> None:
    """Varsayılan 0 Rh+ acil çağrı ekranını uygun örnek adaylarla doldurur."""

    grup = conn.execute(
        "SELECT id FROM kan_gruplari WHERE grup_adi = '0 Rh+'"
    ).fetchone()
    if not grup:
        return

    ornekler = [
        (
            "Umut", "Aydın", "Erkek", "Acil Servis", "05550000101",
            "burcujungk00k97@gmail.com", 210, 1,
        ),
        (
            "Merve", "Kara", "Kadın", "Yoğun Bakım", "05550000102",
            "oncelik2@example.test", 190, 0,
        ),
        (
            "Kaan", "Erdem", "Erkek", "Laboratuvar", "05550000103",
            "oncelik3@example.test", 160, 1,
        ),
    ]
    for ad, soyad, cinsiyet, birim, telefon, eposta, gecen_gun, gece_aranir_mi in ornekler:
        mevcut = conn.execute(
            "SELECT id FROM bagiscilar WHERE telefon = ?", (telefon,)
        ).fetchone()
        if mevcut:
            continue
        cursor = conn.execute(
            """
            INSERT INTO bagiscilar
                (kan_grubu_id, ad, soyad, cinsiyet, birim, telefon, eposta,
                 bildirim_izni, gece_aranir_mi, son_bagis_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                grup["id"], ad, soyad, cinsiyet, birim, telefon, eposta,
                gece_aranir_mi, (bugun - timedelta(days=gecen_gun)).isoformat(),
            ),
        )
        bagisci_no = f"KB-{bugun.year}-{cursor.lastrowid:04d}"
        conn.execute(
            "UPDATE bagiscilar SET bagisci_no = ? WHERE id = ?",
            (bagisci_no, cursor.lastrowid),
        )


def _puan_ve_bagisci_panelini_tamamla(conn, bugun: date) -> None:
    """Mevcut demo verisini silmeden yeni puan ve bağışçı panelini tamamlar."""

    adem = conn.execute(
        "SELECT id, kan_grubu_id, son_bagis_tarihi FROM bagiscilar WHERE ad = 'Adem' LIMIT 1"
    ).fetchone()
    if not adem:
        adem = conn.execute(
            "SELECT id, kan_grubu_id, son_bagis_tarihi FROM bagiscilar ORDER BY id LIMIT 1"
        ).fetchone()
    if not adem:
        return

    conn.execute(
        """
        INSERT OR IGNORE INTO bagisci_hesaplari
            (bagisci_id, kullanici_adi, sifre_hash)
        VALUES (?, 'adem', ?)
        """,
        (adem["id"], generate_password_hash("Bagisci123!")),
    )

    # Adem'in kayıttaki eski bağış tarihi, kullanıcı panelindeki geçmişle de tutarlı olsun.
    if conn.execute(
        "SELECT COUNT(*) FROM bagislar WHERE bagisci_id = ?", (adem["id"],)
    ).fetchone()[0] == 0:
        conn.execute(
            """
            INSERT INTO bagislar
                (bagisci_id, kan_grubu_id, bilesen_turu, unite_sayisi, bagis_tarihi)
            VALUES (?, ?, 'Tam Kan', 1, ?)
            """,
            (adem["id"], adem["kan_grubu_id"], adem["son_bagis_tarihi"] or bugun.isoformat()),
        )

    if conn.execute("SELECT COUNT(*) FROM puan_hareketleri").fetchone()[0] == 0:
        kritik_gruplar = {
            row["id"]
            for row in conn.execute(
                """
                SELECT kg.id
                FROM kan_gruplari kg
                LEFT JOIN kan_torbalari kt
                  ON kt.kan_grubu_id = kg.id AND kt.durum = 'AKTİF'
                 AND kt.son_kullanma_tarihi >= date('now')
                GROUP BY kg.id
                HAVING COUNT(kt.id) <= kg.kritik_esik
                """
            ).fetchall()
        }
        for bagis in conn.execute(
            "SELECT id, bagisci_id, kan_grubu_id, bagis_tarihi FROM bagislar ORDER BY id"
        ).fetchall():
            conn.execute(
                """
                INSERT INTO puan_hareketleri (bagisci_id, bagis_id, puan, neden, tarih)
                VALUES (?, ?, 100, 'Standart kan bağışı', ?)
                """,
                (bagis["bagisci_id"], bagis["id"], f"{bagis['bagis_tarihi']} 12:00:00"),
            )
            if bagis["kan_grubu_id"] in kritik_gruplar:
                conn.execute(
                    """
                    INSERT INTO puan_hareketleri (bagisci_id, bagis_id, puan, neden, tarih)
                    VALUES (?, ?, 50, 'Kritik stok kan grubu bonusu', ?)
                    """,
                    (bagis["bagisci_id"], bagis["id"], f"{bagis['bagis_tarihi']} 12:01:00"),
                )

    if conn.execute("SELECT COUNT(*) FROM acil_cagrilar").fetchone()[0] == 0:
        grup = conn.execute(
            "SELECT id FROM kan_gruplari WHERE grup_adi = '0 Rh+'"
        ).fetchone()
        admin = conn.execute(
            "SELECT id FROM api_kullanicilari WHERE kullanici_adi = 'admin'"
        ).fetchone()
        if grup:
            conn.execute(
                """
                INSERT INTO acil_cagrilar
                    (kan_grubu_id, aciklama, aday_sayisi, olusturan_api_kullanici_id)
                VALUES (?, 'Acil servis için örnek 0 Rh+ çağrısı', 1, ?)
                """,
                (grup["id"], admin["id"] if admin else None),
            )


def ornek_verileri_yukle() -> None:
    veritabani.veritabani_baslat()
    bugun = date.today()
    with veritabani.baglanti_al() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO kan_gruplari (grup_adi, kritik_esik) VALUES (?, ?)",
            KAN_GRUPLARI,
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO api_kullanicilari (kullanici_adi, sifre_hash, rol)
            VALUES ('admin', ?, 'admin')
            """,
            (generate_password_hash("Admin123!"),),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO api_kullanicilari (kullanici_adi, sifre_hash, rol)
            VALUES ('personel', ?, 'personel')
            """,
            (generate_password_hash("Personel123!"),),
        )

        if conn.execute("SELECT COUNT(*) FROM bagiscilar").fetchone()[0] > 0:
            _puan_ve_bagisci_panelini_tamamla(conn, bugun)
            _oncelikli_cagri_orneklerini_tamamla(conn, bugun)
            return

        grup_id = {
            row["grup_adi"]: row["id"]
            for row in conn.execute("SELECT id, grup_adi FROM kan_gruplari").fetchall()
        }
        bagiscilar = [
            ("A Rh+", "Burcu", "Güngör", "Kadın", "Yoğun Bakım", "05000000001", 80),
            ("B Rh-", "Esra", "Ünal", "Kadın", "Acil Servis", "05000000002", 150),
            ("0 Rh+", "Adem", "Çalışkan", "Erkek", "Genel Cerrahi", "05000000003", 110),
            ("AB Rh-", "Rabia", "Güngör", "Kadın", "Organ Nakli", "05000000004", 150),
            ("A Rh-", "Derya", "Kaya", "Kadın", "Dahiliye", "05000000005", 500),
            ("0 Rh-", "Mehmet", "Yıldız", "Erkek", "Laboratuvar", "05000000006", 30),
            ("B Rh+", "Can", "Demir", "Erkek", "Radyoloji", "05000000007", 20),
            ("AB Rh+", "Elif", "Arslan", "Kadın", "Çocuk Servisi", "05000000008", 15),
            ("A Rh+", "Alp", "Koç", "Erkek", "Acil Servis", "05000000009", 10),
            ("B Rh-", "Zeynep", "Ak", "Kadın", "Kardiyoloji", "05000000010", 12),
            ("0 Rh+", "Cem", "Öztürk", "Erkek", "Ameliyathane", "05000000011", 18),
            ("A Rh-", "Seda", "Aydın", "Kadın", "Nöroloji", "05000000012", 16),
            ("0 Rh-", "Ozan", "Şahin", "Erkek", "Yoğun Bakım", "05000000013", 14),
            ("AB Rh-", "Nisa", "Çelik", "Kadın", "Hematoloji", "05000000014", 11),
        ]
        bagisci_idleri: dict[str, list[int]] = {grup: [] for grup, _ in KAN_GRUPLARI}
        for sira, (grup, ad, soyad, cinsiyet, birim, telefon, gecen_gun) in enumerate(bagiscilar, 1):
            cursor = conn.execute(
                """
                INSERT INTO bagiscilar
                    (bagisci_no, kan_grubu_id, ad, soyad, cinsiyet, birim, telefon, eposta,
                     bildirim_izni, gece_aranir_mi, son_bagis_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    f"KB-{bugun.year}-{sira:04d}", grup_id[grup], ad, soyad, cinsiyet, birim,
                    telefon, f"ornek{sira}@example.test", sira % 2,
                    (bugun - timedelta(days=gecen_gun)).isoformat(),
                ),
            )
            bagisci_idleri[grup].append(cursor.lastrowid)

        conn.execute(
            """
            INSERT INTO saglik_engelleri
                (bagisci_id, tur, aciklama, baslangic_tarihi, bitis_tarihi, kalici_mi)
            VALUES (?, 'Dövme', 'Son 12 ay içinde dövme yaptırma', ?, ?, 0)
            """,
            (
                bagisci_idleri["A Rh+"][0],
                (bugun - timedelta(days=100)).isoformat(),
                (bugun + timedelta(days=265)).isoformat(),
            ),
        )
        conn.execute(
            """
            INSERT INTO saglik_engelleri
                (bagisci_id, tur, aciklama, baslangic_tarihi, bitis_tarihi, kalici_mi)
            VALUES (?, 'Hepatit B', 'Hepatit B geçmişi', ?, NULL, 1)
            """,
            (bagisci_idleri["B Rh-"][0], (bugun - timedelta(days=900)).isoformat()),
        )
        conn.execute(
            """
            INSERT INTO saglik_engelleri
                (bagisci_id, tur, aciklama, baslangic_tarihi, bitis_tarihi, kalici_mi)
            VALUES (?, 'Dövme', 'Süresi dolmuş örnek dövme engeli', ?, ?, 0)
            """,
            (
                bagisci_idleri["A Rh-"][0],
                (bugun - timedelta(days=500)).isoformat(),
                (bugun - timedelta(days=135)).isoformat(),
            ),
        )

        hedefler = {
            "A Rh+": 15, "A Rh-": 8, "B Rh+": 12, "B Rh-": 2,
            "0 Rh+": 20, "0 Rh-": 4, "AB Rh+": 10, "AB Rh-": 6,
        }
        urunler = ["Eritrosit", "Tam Kan", "Eritrosit", "Trombosit"]
        # Uygun örnek bağışçıları (Adem, Derya, Rabia) yeni bağış senaryosunda
        # kullanılabilir bırak; mevcut stokları diğer aynı-grup bağışçıları üretir.
        stok_bagiscilari = {
            "A Rh+": bagisci_idleri["A Rh+"],
            "A Rh-": [bagisci_idleri["A Rh-"][-1]],
            "B Rh+": bagisci_idleri["B Rh+"],
            "B Rh-": [bagisci_idleri["B Rh-"][-1]],
            "0 Rh+": [bagisci_idleri["0 Rh+"][-1]],
            "0 Rh-": [bagisci_idleri["0 Rh-"][-1]],
            "AB Rh+": bagisci_idleri["AB Rh+"],
            "AB Rh-": [bagisci_idleri["AB Rh-"][-1]],
        }
        for grup_sirasi, (grup, miktar) in enumerate(hedefler.items(), 1):
            uygun_idler = stok_bagiscilari[grup]
            for sira in range(miktar):
                bagisci_id = uygun_idler[sira % len(uygun_idler)]
                urun = urunler[(sira + grup_sirasi) % len(urunler)]
                gecen_gun = 1 if urun == "Trombosit" else 3 + (sira % 8)
                bagis_tarihi = bugun - timedelta(days=gecen_gun)
                skt = bagis_tarihi + timedelta(days=servisler.URUN_KURALLARI[urun]["raf_omru_gun"])
                bagis = conn.execute(
                    """
                    INSERT INTO bagislar
                        (bagisci_id, kan_grubu_id, bilesen_turu, unite_sayisi, bagis_tarihi)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (bagisci_id, grup_id[grup], urun, bagis_tarihi.isoformat()),
                )
                torba = conn.execute(
                    """
                    INSERT INTO kan_torbalari
                        (bagis_id, bagisci_id, kan_grubu_id, bilesen_turu, bagis_tarihi,
                         son_kullanma_tarihi, saklama_konumu)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bagis.lastrowid, bagisci_id, grup_id[grup], urun,
                        bagis_tarihi.isoformat(), skt.isoformat(),
                        "Trombosit Dolabı" if urun == "Trombosit" else f"Soğuk Oda {chr(65 + grup_sirasi % 3)}",
                    ),
                )
                conn.execute(
                    "UPDATE kan_torbalari SET unite_kodu = ? WHERE id = ?",
                    (f"KT-{bugun:%Y%m%d}-{torba.lastrowid:05d}", torba.lastrowid),
                )
                conn.execute(
                    """
                    UPDATE bagiscilar
                    SET son_bagis_tarihi = ?
                    WHERE id = ? AND (son_bagis_tarihi IS NULL OR son_bagis_tarihi < ?)
                    """,
                    (bagis_tarihi.isoformat(), bagisci_id, bagis_tarihi.isoformat()),
                )

        admin_id = conn.execute(
            "SELECT id FROM api_kullanicilari WHERE kullanici_adi = 'admin'"
        ).fetchone()[0]
        conn.executemany(
            """
            INSERT INTO islem_gecmisi (api_kullanici_id, islem_turu, detay, tarih)
            VALUES (?, ?, ?, ?)
            """,
            [
                (admin_id, "SİSTEM", "Örnek veritabanı ve otomatik bağışçı numaraları oluşturuldu.", f"{bugun} 09:00:00"),
                (admin_id, "STOK_KONTROL", "Sekiz kan grubu için kritik eşik kontrolü çalıştırıldı.", f"{bugun} 09:10:00"),
                (admin_id, "UYGUNLUK", "Cinsiyet, son bağış ve sağlık engeli kuralları yeniden hesaplandı.", f"{bugun} 09:15:00"),
            ],
        )
        _puan_ve_bagisci_panelini_tamamla(conn, bugun)
        _oncelikli_cagri_orneklerini_tamamla(conn, bugun)


if __name__ == "__main__":
    ornek_verileri_yukle()
    print(f"Örnek veriler hazır: {veritabani.DB_YOLU}")
