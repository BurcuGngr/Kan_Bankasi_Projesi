import sqlite3

def test_verilerini_ekle():
    conn = sqlite3.connect('kan_bankasi.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Test verileri ekleniyor...")

    kan_gruplari = [
        (1, 'A Rh+',), (2, 'A Rh-',),
        (3, 'B Rh+',), (4, 'B Rh-',),
        (5, '0 Rh+',), (6, '0 Rh-',),
        (7, 'AB Rh+',), (8, 'AB Rh-',)
    ]
    cursor.executemany("INSERT OR IGNORE INTO kan_gruplari (id, grup_adi) VALUES (?, ?)", kan_gruplari)

    stok_verileri = [
        (1, 15, 5), (2, 8, 5), (3, 12, 5), (4, 2, 5),
        (5, 20, 5), (6, 4, 5), (7, 10, 5), (8, 6, 5)
    ]
    # OR IGNORE: veritabani.py'deki UNIQUE(kan_grubu_id) kısıtı sayesinde,
    # bu script ikinci kez çalıştırılırsa (db silinmeden) hata vermek yerine
    # var olan kaydı sessizce atlar, tekrar satır eklemez.
    cursor.executemany("""
        INSERT OR IGNORE INTO stoklar (kan_grubu_id, torba_sayisi, kritik_esik)
        VALUES (?, ?, ?)
    """, stok_verileri)

    personel_listesi = [
        (1, 'Burcu', 'Güngör', 'Kadın', 'İbni Sina Yoğun Bakım', '05074652220', 'burcu.ornek@example.com', 1, 1, '2026-03-10'),
        (4, 'Esra', 'Ünal', 'Kadın', 'Acil Servis', '05312937656', 'esra.ornek@example.com', 1, 0, '2026-06-25'),
        (5, 'Adem', 'Çalışkan', 'Erkek', 'Genel Cerrahi Ameliyathanesi', '05456328035', 'adem.ornek@example.com', 0, 0, '2026-04-24'),
        (8, 'Rabia', 'Güngör', 'Kadın', 'Organ Nakli Merkezi', '05415216002', 'rabia.ornek@example.com', 1, 0, '2026-01-14')
    ]
    cursor.executemany("""
        INSERT OR IGNORE INTO kullaniciler
        (kan_grubu_id, kullanici_adi, kullanici_soyadi, kullanici_cinsiyet, kullanici_birim, kullanici_telefon, kullanici_eposta, kullanici_bildirim_izni, kullanici_gece_aranir_mi, kullanici_son_bagis_tarihi)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, personel_listesi)

    cursor.execute("SELECT id, kullanici_adi, kullanici_soyadi FROM kullaniciler")
    kullanicilar = cursor.fetchall()
    print("Eklenen Kullanıcılar (id, ad, soyad):", kullanicilar)

    id_map = {(ad, soyad): kid for kid, ad, soyad in kullanicilar}
    burcu_id = id_map[('Burcu', 'Güngör')]
    esra_id = id_map[('Esra', 'Ünal')]

    # NOT: OR IGNORE kaldırıldı. UNIQUE kısıtı olmadığı için gerek yok,
    # ve OR IGNORE burada satırların sessizce atlanmasına neden olabiliyordu.
    engel_verileri = [
        (burcu_id, 'Geçici', 'Dövme Yaptırma', '2026-10-01'),
        (esra_id, 'Kalıcı', 'Kronik Hepatit B', None)
    ]
    cursor.executemany("""
        INSERT INTO saglik_engelleri
        (kullanici_id, engel_turu, aciklama, bitis_tarihi)
        VALUES (?, ?, ?, ?)
    """, engel_verileri)

    # YENİ: Talep tahmini ve dinamik eşik algoritmalarını test edebilmek için
    # geçmişe dönük birkaç kan çıkışı kaydı ekliyoruz. Bu olmadan o iki
    # algoritma her zaman "veri yok" der.
    from datetime import datetime, timedelta
    bugun = datetime.now()
    kan_cikis_verileri = [
        (1, 2, (bugun - timedelta(days=5)).strftime('%Y-%m-%d')),
        (1, 1, (bugun - timedelta(days=10)).strftime('%Y-%m-%d')),
        (1, 3, (bugun - timedelta(days=20)).strftime('%Y-%m-%d')),
        (6, 1, (bugun - timedelta(days=3)).strftime('%Y-%m-%d')),
        (6, 1, (bugun - timedelta(days=8)).strftime('%Y-%m-%d')),
    ]
    cursor.executemany("""
        INSERT INTO kan_cikislari (kan_grubu_id, adet, tarih)
        VALUES (?, ?, ?)
    """, kan_cikis_verileri)

    conn.commit()
    conn.close()
    print("Test verileri başarıyla yüklendi!")

if __name__ == '__main__':
    test_verilerini_ekle()