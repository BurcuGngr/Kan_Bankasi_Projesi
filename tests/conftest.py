"""
pytest, bu dosyadaki fixture'ları OTOMATİK bulur ve testlere enjekte eder.
Buradaki en önemli fikir: testler ASLA gerçek kan_bankasi.db üzerinde
çalışmamalı. Her test, kendi geçici (temp) veritabanını kullanır, test
bitince o dosya silinir. Böylece:
  1) Testler birbirini etkilemez (her biri temiz bir db ile başlar)
  2) Gerçek/üretim verisini asla bozma riski olmaz
  3) Testleri istediğin kadar çalıştırabilirsin, hep aynı sonucu alırsın
"""
import os
import sys
import sqlite3
import pytest

# tests/ klasöründen bir üst dizindeki (proje kökü) modülleri import edebilmek için
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import veritabani
import servisler
import auth
import audit


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """
    Her test fonksiyonu bu fixture'ı parametre olarak istediğinde,
    pytest otomatik olarak:
      1. Geçici bir klasörde boş bir .db dosyası yolu üretir (tmp_path)
      2. servisler.py, auth.py ve veritabani.py'nin DB_YOLU'nu bu geçici
         dosyaya yönlendirir (monkeypatch) - gerçek kan_bankasi.db'ye HİÇ dokunulmaz
      3. Tabloları oluşturur
      4. Test bitince geçici dosyayı otomatik temizler (tmp_path'in doğal davranışı)
    """
    # ÖNEMLİ: veritabani.py sabit olarak 'kan_bankasi.db' adını kullanıyor
    # (parametre almıyor), o yüzden test dosyamıza da AYNI adı vermek zorundayız,
    # yoksa veritabani_baslat() bir dosyaya yazar, biz başka bir dosyaya bakarız.
    db_yolu = str(tmp_path / "kan_bankasi.db")

    monkeypatch.setattr(servisler, "DB_YOLU", db_yolu)
    monkeypatch.setattr(auth, "DB_YOLU", db_yolu)
    monkeypatch.setattr(audit, "DB_YOLU", db_yolu)

    # veritabani.py sabit 'kan_bankasi.db' kullanıyor, çalışma dizinini
    # geçici klasöre çevirerek onun da geçici dosyayı oluşturmasını sağlıyoruz
    eski_dizin = os.getcwd()
    os.chdir(tmp_path)
    veritabani.veritabani_baslat()
    os.chdir(eski_dizin)

    return db_yolu


@pytest.fixture
def ornek_veri(test_db):
    """
    test_db'nin üzerine birkaç örnek kayıt ekler: 2 kan grubu, 2 stok kaydı
    (biri kritik, biri normal), 1 kullanıcı. Çoğu test bu veriyi kullanır.
    """
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO kan_gruplari (id, grup_adi) VALUES (1, 'A Rh+'), (2, '0 Rh-')")
    cursor.execute("INSERT INTO stoklar (kan_grubu_id, torba_sayisi, kritik_esik) VALUES (1, 15, 5), (2, 3, 5)")
    cursor.execute("""
        INSERT INTO kullaniciler
        (id, kan_grubu_id, kullanici_adi, kullanici_soyadi, kullanici_cinsiyet, kullanici_birim, kullanici_telefon, kullanici_bildirim_izni, kullanici_gece_aranir_mi, kullanici_son_bagis_tarihi)
        VALUES (1, 1, 'Test', 'Kullanici', 'Erkek', 'Acil', '05001234567', 1, 1, NULL)
    """)
    conn.commit()
    conn.close()
    return test_db