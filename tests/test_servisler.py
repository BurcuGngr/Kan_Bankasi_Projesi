"""
servisler.py'deki iş mantığını test eder. Flask'a hiç dokunmaz,
sadece fonksiyonları doğrudan çağırır.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import servisler


# ============================================================
# KRİTİK STOK TESTLERİ
# ============================================================
def test_kritik_stok_dogru_grubu_buluyor(ornek_veri):
    # ornek_veri fixture'ı: A Rh+ = 15 torba (normal), 0 Rh- = 3 torba (kritik, eşik 5)
    sonuc = servisler.kritik_stoklari_getir()

    assert len(sonuc) == 1
    assert sonuc[0]['grup_adi'] == '0 Rh-'
    assert sonuc[0]['torba_sayisi'] == 3


def test_kritik_stok_normal_grubu_listelemiyor(ornek_veri):
    sonuc = servisler.kritik_stoklari_getir()
    grup_adlari = [s['grup_adi'] for s in sonuc]
    assert 'A Rh+' not in grup_adlari


# ============================================================
# ÇAPRAZ KAN UYUMLULUĞU TESTLERİ (regresyon önleme - bu bir tıbbi kural,
# yanlış hesaplanırsa gerçek dünyada tehlikeli olur, bu yüzden özellikle test edildi)
# ============================================================
def test_0_negatif_sadece_kendinden_alabilir():
    # Medikal kural: 0 Rh- "genel verici"dir ama SADECE kendinden alabilir
    uyumlular = servisler.UYUM_HARITASI['0 Rh-']
    assert uyumlular == ['0 Rh-']


def test_ab_pozitif_herkesten_alabilir():
    # Medikal kural: AB Rh+ "genel alıcı"dır, tüm gruplardan alabilir
    uyumlular = servisler.UYUM_HARITASI['AB Rh+']
    assert len(uyumlular) == 8  # 8 kan grubunun hepsi


# ============================================================
# KAN ÇIKIŞI TESTLERİ
# ============================================================
def test_yetersiz_stok_reddedilir(ornek_veri):
    # 0 Rh- grubunda sadece 3 torba var, 10 torba istemek başarısız olmalı
    basarili, mesaj = servisler.kan_cikis_yap(kan_grubu_id=2, adet=10)
    assert basarili is False
    assert "yetersiz" in mesaj.lower() or "Yetersiz" in mesaj


def test_yeterli_stok_cikisi_basarili(ornek_veri):
    basarili, mesaj = servisler.kan_cikis_yap(kan_grubu_id=1, adet=5)
    assert basarili is True

    # Stoğun gerçekten düştüğünü doğrula
    guncel = servisler.kritik_stoklari_getir()
    # A Rh+ hâlâ kritik değil (15-5=10, eşik 5), listede olmamalı
    grup_adlari = [s['grup_adi'] for s in guncel]
    assert 'A Rh+' not in grup_adlari


def test_var_olmayan_kan_grubuna_cikis_basarisiz(ornek_veri):
    basarili, mesaj = servisler.kan_cikis_yap(kan_grubu_id=999, adet=1)
    assert basarili is False


# ============================================================
# AĞIRLIKLI ÖNCELİK SKORU TESTLERİ
# ============================================================
def test_oncelik_skoru_daha_cok_bekleyen_daha_yuksek_puan_alir():
    dusuk_skor = servisler.oncelik_skoru_hesapla(
        gecen_gun=100, toplam_bagis=0, gece_uygun_mu=True, gece_cagrisi_mi=False
    )
    yuksek_skor = servisler.oncelik_skoru_hesapla(
        gecen_gun=300, toplam_bagis=0, gece_uygun_mu=True, gece_cagrisi_mi=False
    )
    assert yuksek_skor > dusuk_skor


def test_gece_cagrisinda_gece_uygun_olmayan_dusuk_puan_alir():
    gece_uygun = servisler.oncelik_skoru_hesapla(
        gecen_gun=100, toplam_bagis=0, gece_uygun_mu=True, gece_cagrisi_mi=True
    )
    gece_uygun_degil = servisler.oncelik_skoru_hesapla(
        gecen_gun=100, toplam_bagis=0, gece_uygun_mu=False, gece_cagrisi_mi=True
    )
    assert gece_uygun > gece_uygun_degil


# ============================================================
# BAĞIŞ UYGUNLUK TESTLERİ
# ============================================================
def test_hic_bagis_yapmamis_kullanici_uygun(ornek_veri):
    sonuc = servisler.bagis_uygunluk_kontrol_et(kullanici_id=1)
    assert sonuc['uygun_mu'] is True


def test_var_olmayan_kullanici_icin_hata_donuyor(ornek_veri):
    sonuc = servisler.bagis_uygunluk_kontrol_et(kullanici_id=999)
    assert sonuc['uygun_mu'] is False
    assert 'bulunamadı' in sonuc['mesaj'].lower()


# ============================================================
# YENİ BAĞIŞÇI EKLEME TESTLERİ
# ============================================================
def test_yeni_bagisci_eklenebiliyor(ornek_veri):
    basarili, sonuc = servisler.kullanici_ekle(
        kan_grubu_id=1, ad='Yeni', soyad='Kisi', cinsiyet='Erkek',
        birim='Test Birimi', telefon='05551112233'
    )
    assert basarili is True
    assert isinstance(sonuc, int)  # yeni kullanıcının id'si döner


def test_ayni_telefonla_iki_kez_eklenemiyor(ornek_veri):
    servisler.kullanici_ekle(
        kan_grubu_id=1, ad='Birinci', soyad='Kisi', cinsiyet='Erkek',
        birim='X', telefon='05551112233'
    )
    basarili, mesaj = servisler.kullanici_ekle(
        kan_grubu_id=1, ad='Ikinci', soyad='Kisi', cinsiyet='Kadın',
        birim='Y', telefon='05551112233'
    )
    assert basarili is False
    assert 'zaten var' in mesaj.lower()


# ============================================================
# ELLE STOK GİRİŞİ TESTLERİ
# ============================================================
def test_stok_girisi_torba_sayisini_artiriyor(ornek_veri):
    # ornek_veri: A Rh+ = 15 torba
    basarili, mesaj = servisler.stok_girisi_yap(kan_grubu_id=1, adet=5)
    assert basarili is True

    guncel = servisler.kritik_stoklari_getir()
    # A Rh+ zaten kritik değildi, hala olmamalı ama stoğun arttığını
    # dolaylı olarak kan_cikis_yap ile test edelim
    basarili2, _ = servisler.kan_cikis_yap(kan_grubu_id=1, adet=19)  # 15+5-19=1, mümkün olmalı
    assert basarili2 is True


def test_var_olmayan_kan_grubuna_stok_girisi_basarisiz(ornek_veri):
    basarili, mesaj = servisler.stok_girisi_yap(kan_grubu_id=999, adet=5)
    assert basarili is False


# ============================================================
# KAN TALEBİ TESTLERİ
# ============================================================
def test_talep_olusturulup_listelenebiliyor(ornek_veri):
    basarili, talep_id = servisler.talep_olustur(kan_grubu_id=1, talep_eden_birim='Acil Servis')
    assert basarili is True

    aktif_liste = servisler.aktif_talepleri_getir()
    assert len(aktif_liste) == 1
    assert aktif_liste[0]['talep_eden_birim'] == 'Acil Servis'
    assert aktif_liste[0]['grup_adi'] == 'A Rh+'


def test_kapatilan_talep_aktif_listede_gorunmuyor(ornek_veri):
    basarili, talep_id = servisler.talep_olustur(kan_grubu_id=1, talep_eden_birim='Acil Servis')
    kapatma_basarili, _ = servisler.talep_kapat(talep_id)
    assert kapatma_basarili is True

    aktif_liste = servisler.aktif_talepleri_getir()
    assert len(aktif_liste) == 0


def test_var_olmayan_talep_kapatilamiyor(ornek_veri):
    basarili, mesaj = servisler.talep_kapat(talep_id=999)
    assert basarili is False