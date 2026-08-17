import sqlite3

def veritabani_baslat():
    conn = sqlite3.connect('kan_bankasi.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Veritabanı bağlantısı başarılı. Tablolar oluşturuluyor...")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kan_gruplari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grup_adi TEXT NOT NULL UNIQUE
        )
    ''')

    # UNIQUE(kan_grubu_id): Bir kan grubunun stok tablosunda yalnızca TEK satırı
    # olabilir. Bu olmadan, veriler.py birden fazla kez çalıştırıldığında
    # (veritabanı silinmeden) her kan grubu için tekrar tekrar satır eklenir
    # ve kritik_stoklari_getir() gibi sorgular aynı kaydı birden çok kez döndürür.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stoklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kan_grubu_id INTEGER NOT NULL UNIQUE,
            torba_sayisi INTEGER NOT NULL DEFAULT 0,
            kritik_esik INTEGER NOT NULL DEFAULT 5,
            FOREIGN KEY (kan_grubu_id) REFERENCES kan_gruplari(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kullaniciler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kan_grubu_id INTEGER NOT NULL,
            kullanici_adi TEXT NOT NULL, 
            kullanici_soyadi TEXT NOT NULL,
            kullanici_cinsiyet TEXT NOT NULL,
            kullanici_birim TEXT NOT NULL,
            kullanici_telefon TEXT NOT NULL UNIQUE,
            kullanici_eposta TEXT,
            kullanici_bildirim_izni INTEGER NOT NULL DEFAULT 1,
            kullanici_gece_aranir_mi INTEGER NOT NULL DEFAULT 0,
            kullanici_son_bagis_tarihi TEXT,
            FOREIGN KEY (kan_grubu_id) REFERENCES kan_gruplari(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ilanlar_talepler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kan_grubu_id INTEGER NOT NULL,
            talep_eden_birim TEXT NOT NULL,
            ilan_talep_durum TEXT NOT NULL DEFAULT "AKTİF",
            ilan_talep_tarihi DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kan_grubu_id) REFERENCES kan_gruplari(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saglik_engelleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_id INTEGER NOT NULL,
            engel_turu TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            bitis_tarihi TEXT,
            FOREIGN KEY (kullanici_id) REFERENCES kullaniciler(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kan_cikislari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kan_grubu_id INTEGER NOT NULL,
            adet INTEGER NOT NULL,
            tarih TEXT NOT NULL,
            FOREIGN KEY (kan_grubu_id) REFERENCES kan_gruplari(id)
        )
    ''')

    # BAGISLAR TABLOSU (eskiden servisler.py içinde gizli oluşturuluyordu, artık burada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bagislar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bagisci_id INTEGER NOT NULL,
            tarih TEXT NOT NULL,
            FOREIGN KEY (bagisci_id) REFERENCES kullaniciler(id)
        )
    ''')

    # KAN_TORBALARI TABLOSU (SKT risk analizi için - eskiden fonksiyon içinde gizli oluşturuluyordu)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kan_torbalari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kan_grubu_id INTEGER NOT NULL,
            giris_tarihi TEXT NOT NULL,
            son_kullanma_tarihi TEXT NOT NULL,
            durum TEXT DEFAULT 'Aktif',
            FOREIGN KEY (kan_grubu_id) REFERENCES kan_gruplari(id)
        )
    ''')

    # YENİ (Adım 2 - Kimlik Doğrulama için): API kullanıcıları tablosu.
    # Bu, kan bankası personeli/kullanıcıları (kullaniciler tablosu) ile KARIŞTIRILMAMALI.
    # Bu tablo, API'ye kim giriş yapabilir sorusuna cevap verir.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_kullanicilari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT NOT NULL UNIQUE,
            sifre_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'personel', -- 'admin' veya 'personel'
            olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # YENİ: Oturum tokenları. Kullanıcı giriş yapınca burada bir token oluşur,
    # sonraki isteklerde bu token doğrulanır. Token'ın bir geçerlilik süresi
    # var (8 saat) - bu, çalınan bir token'ın sonsuza kadar geçerli kalmasını engeller.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_oturumlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            api_kullanici_id INTEGER NOT NULL,
            olusturma_tarihi TEXT NOT NULL,
            gecerlilik_tarihi TEXT NOT NULL,
            FOREIGN KEY (api_kullanici_id) REFERENCES api_kullanicilari(id)
        )
    ''')

    # YENİ: İşlem geçmişi (audit trail). Bir hastanede "kim, ne zaman, hangi
    # işlemi yaptı" sorusu düz bir "iyi olur" değil, çoğu zaman denetim/uyum
    # gereğidir. Bu tablo asla UPDATE veya DELETE edilmez, sadece INSERT -
    # yani geçmiş kayıtlar hiçbir zaman değiştirilemez/silinemez.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS islem_gecmisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT NOT NULL,
            rol TEXT NOT NULL,
            islem TEXT NOT NULL,
            detay TEXT,
            ip_adresi TEXT,
            tarih TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    print("Tablolar başarıyla oluşturuldu!")

if __name__ == '__main__':
    veritabani_baslat()