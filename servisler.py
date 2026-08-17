"""
Bu dosya saf iş mantığını (business logic) içerir.
Flask, HTTP, request/response gibi hiçbir web kavramı burada YOKTUR.
Neden ayrıldı: Bu fonksiyonlar hem API'den, hem ileride bir CLI'dan,
hem de testlerden bağımsız olarak çağrılabilmeli. Web katmanına
bağımlı olsaydı, test yazmak ve yeniden kullanmak zorlaşırdı.
"""
import sqlite3
from datetime import datetime, timedelta

DB_YOLU = 'kan_bankasi.db'


def veritabani_baglan():
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# KRİTİK STOK KONTROLÜ
# ============================================================
def kritik_stoklari_getir():
    conn = veritabani_baglan()
    cursor = conn.cursor()
    sorgu = """
    SELECT g.grup_adi, s.torba_sayisi, s.kritik_esik
    FROM stoklar s
    JOIN kan_gruplari g ON s.kan_grubu_id = g.id
    WHERE s.torba_sayisi <= s.kritik_esik
    """
    cursor.execute(sorgu)
    sonuc = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sonuc


# ============================================================
# UYGUN BAĞIŞÇILAR
# ============================================================
def uygun_bagiscilari_getir(kan_grubu_id, gece_mi=False):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    sorgu = """
    SELECT id, kullanici_adi, kullanici_soyadi, kullanici_birim, kullanici_cinsiyet,
    kullanici_telefon, kullanici_gece_aranir_mi, kullanici_son_bagis_tarihi
    FROM kullaniciler
    WHERE kan_grubu_id = ? AND kullanici_bildirim_izni = 1
    """
    if gece_mi:
        sorgu += " AND kullanici_gece_aranir_mi = 1"
    cursor.execute(sorgu, (kan_grubu_id,))
    tum_adaylar = cursor.fetchall()
    conn.close()

    uygun_bagiscilar = []
    bugun = datetime.now()

    for aday in tum_adaylar:
        son_bagis_str = aday['kullanici_son_bagis_tarihi']
        cinsiyet = str(aday['kullanici_cinsiyet']).lower()
        gerekli_gun = 120 if cinsiyet in ['kadin', 'kadın'] else 90
        if son_bagis_str:
            try:
                temiz_tarih_str = str(son_bagis_str).strip()[:10]
                son_bagis_tarihi = datetime.strptime(temiz_tarih_str, '%Y-%m-%d')
                gecen_gun = (bugun - son_bagis_tarihi).days
                if gecen_gun >= gerekli_gun:
                    uygun_bagiscilar.append({
                        'ad_soyad': f"{aday['kullanici_adi']} {aday['kullanici_soyadi']}",
                        'birim': aday['kullanici_birim'],
                        'telefon': aday['kullanici_telefon'],
                        'gecen_gun': gecen_gun
                    })
            except ValueError:
                print(f"⚠️ Hatalı tarih formatı: {son_bagis_str}")
        else:
            uygun_bagiscilar.append({
                'ad_soyad': f"{aday['kullanici_adi']} {aday['kullanici_soyadi']}",
                'birim': aday['kullanici_birim'],
                'telefon': aday['kullanici_telefon'],
                'gecen_gun': 'Daha önce vermedi'
            })
    return uygun_bagiscilar


# ============================================================
# BAĞIŞ EKLEME / KAN ÇIKIŞI
# ============================================================
def bagis_ekle(kullanici_id, kan_grubu_id):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        bugun_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("UPDATE kullaniciler SET kullanici_son_bagis_tarihi = ? WHERE id = ?", (bugun_str, kullanici_id))
        cursor.execute("UPDATE stoklar SET torba_sayisi = torba_sayisi + 1 WHERE kan_grubu_id = ?", (kan_grubu_id,))
        cursor.execute("INSERT INTO bagislar (bagisci_id, tarih) VALUES (?, ?)", (kullanici_id, bugun_str))
        conn.commit()
        return True
    except Exception as e:
        print(f"Bağış eklenirken hata oluştu: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def kan_cikis_yap(kan_grubu_id, adet):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT torba_sayisi, kritik_esik FROM stoklar WHERE kan_grubu_id = ?", (kan_grubu_id,))
        stok = cursor.fetchone()
        if not stok:
            return False, "Bu kan grubu için stok kaydı bulunamadı."

        mevcut_torba = stok['torba_sayisi']
        kritik_esik = stok['kritik_esik']

        if mevcut_torba < adet:
            return False, "Yetersiz stok."

        yeni_stok = mevcut_torba - adet
        cursor.execute("UPDATE stoklar SET torba_sayisi = ? WHERE kan_grubu_id = ?", (yeni_stok, kan_grubu_id))

        bugun_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            "INSERT INTO kan_cikislari (kan_grubu_id, adet, tarih) VALUES (?, ?, ?)",
            (kan_grubu_id, adet, bugun_str)
        )
        conn.commit()

        uyari = None
        if yeni_stok <= kritik_esik:
            uyari = "Stok kritik seviyenin altına düştü!"
        return True, uyari
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ============================================================
# ÇAPRAZ KAN UYUMLULUĞU
# ============================================================
UYUM_HARITASI = {
    'A Rh+':  ['A Rh+', 'A Rh-', '0 Rh+', '0 Rh-'],
    'A Rh-':  ['A Rh-', '0 Rh-'],
    'B Rh+':  ['B Rh+', 'B Rh-', '0 Rh+', '0 Rh-'],
    'B Rh-':  ['B Rh-', '0 Rh-'],
    'AB Rh+': ['AB Rh+', 'AB Rh-', 'A Rh+', 'A Rh-', 'B Rh+', 'B Rh-', '0 Rh+', '0 Rh-'],
    'AB Rh-': ['AB Rh-', 'A Rh-', 'B Rh-', '0 Rh-'],
    '0 Rh+':  ['0 Rh+', '0 Rh-'],
    '0 Rh-':  ['0 Rh-']
}


def uygun_yedek_stok_getir(kan_grubu_adi):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        kabul_edilebilir_gruplar = UYUM_HARITASI.get(kan_grubu_adi, [kan_grubu_adi])
        jokering = ','.join(['?'] * len(kabul_edilebilir_gruplar))
        sorgu = f"""
                SELECT kg.grup_adi, s.torba_sayisi
                FROM stoklar s
                JOIN kan_gruplari kg ON s.kan_grubu_id = kg.id
                WHERE kg.grup_adi IN ({jokering}) AND s.torba_sayisi > 0
            """
        cursor.execute(sorgu, kabul_edilebilir_gruplar)
        alternatif_stoklar = [dict(row) for row in cursor.fetchall()]
        return alternatif_stoklar
    except Exception as e:
        print(f"❌ Bir hata oluştu: {e}")
        return []
    finally:
        conn.close()


# ============================================================
# BAĞIŞÇI PUAN VE ROZET
# ============================================================
def bagisci_puan_ve_rozet_hesapla(bagisci_id):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM bagislar WHERE bagisci_id = ?", (bagisci_id,))
        toplam_bagis = cursor.fetchone()[0]
        puan = toplam_bagis * 100
        if puan >= 300:
            rozet = "🥇Altın Bağışçı"
        elif puan >= 200:
            rozet = "🥈Gümüş Bağışçı"
        elif puan >= 100:
            rozet = "🥉Bronz Bağışçı"
        else:
            rozet = "🏅Yeni Bağışçı"
        return {"toplam_bagis": toplam_bagis, "puan": puan, "rozet": rozet}
    except Exception as e:
        print(f"❌ Puan hesaplanırken hata oluştu: {e}")
        return None
    finally:
        conn.close()


# ============================================================
# ACİL ÇAĞRI LİSTESİ (basit sürüm)
# ============================================================
def acil_cagri_listesi_hazirla(kan_grubu_id):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        sorgu = """
        SELECT id, kullanici_adi, kullanici_soyadi, kullanici_birim, kullanici_telefon, kullanici_son_bagis_tarihi, kullanici_cinsiyet
        FROM kullaniciler
        WHERE kan_grubu_id = ? AND kullanici_bildirim_izni = 1
        ORDER BY kullanici_son_bagis_tarihi ASC
        """
        cursor.execute(sorgu, (kan_grubu_id,))
        adaylar = cursor.fetchall()
        acil_liste = []
        bugun = datetime.now()

        for aday in adaylar:
            son_bagis_str = aday['kullanici_son_bagis_tarihi']
            cinsiyet = str(aday['kullanici_cinsiyet']).lower()
            gerekli_gun = 120 if cinsiyet in ['kadin', 'kadın'] else 90

            if son_bagis_str:
                son_bagis_tarihi = datetime.strptime(son_bagis_str, '%Y-%m-%d')
                gecen_gun = (bugun - son_bagis_tarihi).days
                if gecen_gun >= gerekli_gun:
                    acil_liste.append({
                        'ad_soyad': f"{aday['kullanici_adi']} {aday['kullanici_soyadi']}",
                        'birim': aday['kullanici_birim'],
                        'telefon': aday['kullanici_telefon'],
                        'gecen_gun': gecen_gun
                    })
            else:
                acil_liste.append({
                    'ad_soyad': f"{aday['kullanici_adi']} {aday['kullanici_soyadi']}",
                    'birim': aday['kullanici_birim'],
                    'telefon': aday['kullanici_telefon'],
                    'gecen_gun': 'Daha önce vermedi(Hemen verebilir)'
                })
        return acil_liste
    except Exception as e:
        print(f"❌ Acil çağrı listesi oluşturulurken hata: {e}")
        return []
    finally:
        conn.close()


# ============================================================
# SKT RİSK ANALİZİ
# ============================================================
def sktt_riskli_stoklari_getir():
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        select_sorgu = """
        SELECT t.id, kg.grup_adi, t.giris_tarihi, t.son_kullanma_tarihi
        FROM kan_torbalari t
        JOIN kan_gruplari kg ON t.kan_grubu_id = kg.id
        WHERE t.durum = 'Aktif'
        ORDER BY t.son_kullanma_tarihi ASC
        """
        cursor.execute(select_sorgu)
        stoklar = cursor.fetchall()

        rapor_listesi = []
        bugun = datetime.now()

        for torba in stoklar:
            skt_tarihi = datetime.strptime(torba['son_kullanma_tarihi'], '%Y-%m-%d')
            kalan_gun = (skt_tarihi - bugun).days
            if kalan_gun < 0:
                durum_mesaji = "‼️ Süresi Doldu (İmha Edilmeli)"
            elif kalan_gun <= 7:
                durum_mesaji = "⚠️ Kritik Risk (Öncelikle Kullan)"
            else:
                durum_mesaji = "Güvenli Stok"

            rapor_listesi.append({
                'torba_id': torba['id'],
                'kan_grubu': torba['grup_adi'],
                'giris_tarihi': torba['giris_tarihi'],
                'skt': torba['son_kullanma_tarihi'],
                'kalan_gun': kalan_gun,
                'durum': durum_mesaji
            })
        return rapor_listesi
    except Exception as e:
        print(f"❌ Stok risk analizi hatası: {e}")
        return []
    finally:
        conn.close()


# ============================================================
# BAĞIŞ UYGUNLUK KONTROLÜ (çok aşamalı filtre)
# ============================================================
def bagis_uygunluk_kontrol_et(kullanici_id, gece_cagrisi_mi=False):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        sorgu = """
        SELECT kullanici_adi, kullanici_soyadi, kullanici_cinsiyet,
               kullanici_son_bagis_tarihi, kullanici_bildirim_izni, kullanici_gece_aranir_mi
        FROM kullaniciler
        WHERE id = ?
        """
        cursor.execute(sorgu, (kullanici_id,))
        kisi = cursor.fetchone()

        if not kisi:
            return {'uygun_mu': False, 'mesaj': '❌ Kullanıcı bulunamadı.', 'kalan_gun': None}

        ad_soyad = f"{kisi['kullanici_adi']} {kisi['kullanici_soyadi']}"
        cinsiyet = str(kisi['kullanici_cinsiyet']).lower()

        if kisi['kullanici_bildirim_izni'] == 0:
            return {'uygun_mu': False, 'mesaj': f"🚫 Sayın {ad_soyad}, bildirim izinleriniz kapalı olduğu için çağrı yapılamıyor.", 'kalan_gun': None}

        if gece_cagrisi_mi and kisi['kullanici_gece_aranir_mi'] == 0:
            return {'uygun_mu': False, 'mesaj': f"🌙 Sayın {ad_soyad}, gece aranma izniniz kapalıdır.", 'kalan_gun': None}

        cursor.execute("SELECT engel_turu, aciklama, bitis_tarihi FROM saglik_engelleri WHERE kullanici_id = ?", (kullanici_id,))
        engeller = cursor.fetchall()
        bugun = datetime.now()

        for engel in engeller:
            if str(engel['engel_turu']).lower() == 'kalici':
                return {
                    'uygun_mu': False,
                    'mesaj': f"❌ Sayın {ad_soyad}, sistemde kalıcı sağlık engeliniz ({engel['aciklama']}) bulunmaktadır. Bağış yapamazsınız.",
                    'kalan_gun': None
                }
            elif engel['bitis_tarihi']:
                bitis_tarihi = datetime.strptime(engel['bitis_tarihi'][:10], '%Y-%m-%d')
                if bugun < bitis_tarihi:
                    kalan_engel_gun = (bitis_tarihi - bugun).days
                    return {
                        'uygun_mu': False,
                        'mesaj': f"⏳ Sayın {ad_soyad}, geçici sağlık engeliniz ({engel['aciklama']}) devam ediyor. Engel bitişine {kalan_engel_gun} gün kaldı.",
                        'kalan_gun': kalan_engel_gun
                    }

        gerekli_bekleme_gunu = 120 if cinsiyet in ['kadin', 'kadın'] else 90
        son_bagis_str = kisi['kullanici_son_bagis_tarihi']

        if not son_bagis_str:
            return {
                'uygun_mu': True,
                'mesaj': f"✅ Sayın {ad_soyad}, sistemde daha önce kayıtlı bağışınız bulunmamaktadır. Bağış yapmaya uygunsunuz!",
                'kalan_gun': 0
            }

        temiz_tarih_str = str(son_bagis_str).strip()[:10]
        son_bagis_tarihi = datetime.strptime(temiz_tarih_str, '%Y-%m-%d')
        gecen_gun = (bugun - son_bagis_tarihi).days

        if gecen_gun >= gerekli_bekleme_gunu:
            return {
                'uygun_mu': True,
                'mesaj': f"✅ Sayın {ad_soyad}, son bağışınızın üzerinden {gecen_gun} gün geçti ({'Kadın' if gerekli_bekleme_gunu == 120 else 'Erkek'} kuralı: {gerekli_bekleme_gunu} gün). Bağışa uygunsunuz!",
                'kalan_gun': 0
            }
        else:
            kalan_gun = gerekli_bekleme_gunu - gecen_gun
            return {
                'uygun_mu': False,
                'mesaj': f"⏳ Sayın {ad_soyad}, son bağışınızın üzerinden {gecen_gun} gün geçmiş. Cinsiyete göre gerekli bekleme sürenizi doldurmak için {kalan_gun} gün daha beklemeniz gerekmektedir.",
                'kalan_gun': kalan_gun
            }
    except Exception as e:
        return {'uygun_mu': False, 'mesaj': f"❌ Hata oluştu: {e}", 'kalan_gun': None}
    finally:
        conn.close()


# ============================================================
# AĞIRLIKLI ÖNCELİK SKORU
# ============================================================
def oncelik_skoru_hesapla(gecen_gun, toplam_bagis, gece_uygun_mu, gece_cagrisi_mi):
    gecikme_puani = min(gecen_gun / 30, 10) if isinstance(gecen_gun, (int, float)) else 10
    deneyim_puani = min(toplam_bagis * 0.5, 10)
    uygunluk_puani = 10 if (not gece_cagrisi_mi or gece_uygun_mu) else 0
    toplam_skor = (gecikme_puani * 0.4) + (deneyim_puani * 0.3) + (uygunluk_puani * 0.3)
    return round(toplam_skor, 2)


def agirlikli_acil_liste_hazirla(kan_grubu_id, gece_cagrisi_mi=False):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        sorgu = """
        SELECT k.id, k.kullanici_adi, k.kullanici_soyadi, k.kullanici_birim,
               k.kullanici_telefon, k.kullanici_son_bagis_tarihi, k.kullanici_cinsiyet,
               k.kullanici_gece_aranir_mi,
               COALESCE((SELECT COUNT(*) FROM bagislar b WHERE b.bagisci_id = k.id), 0) AS toplam_bagis
        FROM kullaniciler k
        WHERE k.kan_grubu_id = ? AND k.kullanici_bildirim_izni = 1
        """
        cursor.execute(sorgu, (kan_grubu_id,))
        adaylar = cursor.fetchall()

        bugun = datetime.now()
        skorlu_liste = []

        for aday in adaylar:
            cinsiyet = str(aday['kullanici_cinsiyet']).lower()
            gerekli_gun = 120 if cinsiyet in ['kadin', 'kadın'] else 90
            son_bagis_str = aday['kullanici_son_bagis_tarihi']
            gece_uygun_mu = bool(aday['kullanici_gece_aranir_mi'])

            if son_bagis_str:
                try:
                    temiz_tarih_str = str(son_bagis_str).strip()[:10]
                    son_bagis_tarihi = datetime.strptime(temiz_tarih_str, '%Y-%m-%d')
                    gecen_gun = (bugun - son_bagis_tarihi).days
                except ValueError:
                    continue
                if gecen_gun < gerekli_gun:
                    continue
            else:
                gecen_gun = 9999

            skor = oncelik_skoru_hesapla(gecen_gun, aday['toplam_bagis'], gece_uygun_mu, gece_cagrisi_mi)

            skorlu_liste.append({
                'ad_soyad': f"{aday['kullanici_adi']} {aday['kullanici_soyadi']}",
                'birim': aday['kullanici_birim'],
                'telefon': aday['kullanici_telefon'],
                'gecen_gun': gecen_gun if gecen_gun != 9999 else 'Daha önce vermedi',
                'toplam_bagis': aday['toplam_bagis'],
                'gece_uygun_mu': gece_uygun_mu,
                'oncelik_skoru': skor
            })

        skorlu_liste.sort(key=lambda x: x['oncelik_skoru'], reverse=True)
        return skorlu_liste
    except Exception as e:
        print(f"❌ Öncelik skoru hesaplanırken hata: {e}")
        return []
    finally:
        conn.close()


# ============================================================
# TALEP TAHMİNİ
# ============================================================
def gunluk_ortalama_tuketim_hesapla(kan_grubu_id, gun_sayisi=30):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        baslangic_tarihi = (datetime.now() - timedelta(days=gun_sayisi)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COALESCE(SUM(adet), 0) AS toplam
            FROM kan_cikislari
            WHERE kan_grubu_id = ? AND tarih >= ?
        """, (kan_grubu_id, baslangic_tarihi))
        toplam = cursor.fetchone()['toplam']
        return round(toplam / gun_sayisi, 2)
    except Exception as e:
        print(f"❌ Ortalama tüketim hesaplanırken hata: {e}")
        return 0
    finally:
        conn.close()


def stok_tahmini_yap(kan_grubu_id, gun_sayisi=30):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.torba_sayisi, kg.grup_adi
            FROM stoklar s
            JOIN kan_gruplari kg ON s.kan_grubu_id = kg.id
            WHERE s.kan_grubu_id = ?
        """, (kan_grubu_id,))
        stok = cursor.fetchone()
        if not stok:
            return None
    finally:
        conn.close()

    gunluk_ortalama = gunluk_ortalama_tuketim_hesapla(kan_grubu_id, gun_sayisi)

    if gunluk_ortalama <= 0:
        return {
            'kan_grubu': stok['grup_adi'],
            'mevcut_stok': stok['torba_sayisi'],
            'gunluk_ortalama_tuketim': 0,
            'tahmini_bitis_gunu': None,
            'mesaj': f"ℹ️ {stok['grup_adi']} için son {gun_sayisi} günde çıkış kaydı yok, tahmin yapılamıyor."
        }

    tahmini_gun = round(stok['torba_sayisi'] / gunluk_ortalama, 1)

    if tahmini_gun <= 3:
        durum_mesaji = f"‼️ ÇOK ACİL: {stok['grup_adi']} stoğu {tahmini_gun} gün içinde tükenecek!"
    elif tahmini_gun <= 7:
        durum_mesaji = f"⚠️ RİSKLİ: {stok['grup_adi']} stoğu yaklaşık {tahmini_gun} güne yetecek."
    else:
        durum_mesaji = f"✅ {stok['grup_adi']} güvenli seviyede, tahmini {tahmini_gun} gün yeter."

    return {
        'kan_grubu': stok['grup_adi'],
        'mevcut_stok': stok['torba_sayisi'],
        'gunluk_ortalama_tuketim': gunluk_ortalama,
        'tahmini_bitis_gunu': tahmini_gun,
        'mesaj': durum_mesaji
    }


def tum_gruplar_icin_stok_tahmini(gun_sayisi=30):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM kan_gruplari")
    gruplar = cursor.fetchall()
    conn.close()

    rapor = []
    for grup in gruplar:
        tahmin = stok_tahmini_yap(grup['id'], gun_sayisi)
        if tahmin:
            rapor.append(tahmin)
    rapor.sort(key=lambda x: (x['tahmini_bitis_gunu'] is None, x['tahmini_bitis_gunu']))
    return rapor


# ============================================================
# KULLANICI BİLGİSİ (bildirim göndermek için gerekli)
# ============================================================
def kullanici_getir(kullanici_id):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, kullanici_adi, kullanici_soyadi, kullanici_eposta, kullanici_telefon FROM kullaniciler WHERE id = ?",
            (kullanici_id,)
        )
        satir = cursor.fetchone()
        return dict(satir) if satir else None
    finally:
        conn.close()


# ============================================================
# DİNAMİK KRİTİK EŞİK
# ============================================================
def dinamik_kritik_esik_hesapla(kan_grubu_id, guvenlik_gun_sayisi=5, gun_sayisi=30):
    gunluk_ortalama = gunluk_ortalama_tuketim_hesapla(kan_grubu_id, gun_sayisi)
    if gunluk_ortalama <= 0:
        return None
    dinamik_esik = round(gunluk_ortalama * guvenlik_gun_sayisi)
    return max(dinamik_esik, 1)


def dinamik_kritik_stoklari_getir(guvenlik_gun_sayisi=5, gun_sayisi=30):
    conn = veritabani_baglan()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.kan_grubu_id, kg.grup_adi, s.torba_sayisi, s.kritik_esik
            FROM stoklar s
            JOIN kan_gruplari kg ON s.kan_grubu_id = kg.id
        """)
        tum_stoklar = cursor.fetchall()
    finally:
        conn.close()

    rapor = []
    for stok in tum_stoklar:
        dinamik_esik = dinamik_kritik_esik_hesapla(stok['kan_grubu_id'], guvenlik_gun_sayisi, gun_sayisi)
        kullanilan_esik = dinamik_esik if dinamik_esik is not None else stok['kritik_esik']
        kaynak = "dinamik (tüketim verisine göre)" if dinamik_esik is not None else "sabit (yeterli veri yok)"

        if stok['torba_sayisi'] <= kullanilan_esik:
            rapor.append({
                'kan_grubu': stok['grup_adi'],
                'mevcut_stok': stok['torba_sayisi'],
                'kullanilan_esik': kullanilan_esik,
                'esik_kaynagi': kaynak
            })
    return rapor