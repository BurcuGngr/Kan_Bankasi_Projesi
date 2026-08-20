"""
Bu dosya, servisler.py'deki iş mantığını HTTP üzerinden erişilebilir hale getirir.
Kural: Bu dosyada iş mantığı YAZILMAZ. Sadece:
  1. HTTP isteğini al
  2. Parametreleri servisler.py'ye ilet
  3. Dönen sonucu JSON'a çevirip geri gönder
Neden bu ayrım önemli: İş mantığı burada karışırsa, hem test etmek zorlaşır
hem de yarın bir CLI veya farklı bir arayüz eklemek istediğinde her şeyi
tekrar yazman gerekir.
"""
from functools import wraps
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import servisler
import auth
import audit
import bildirim
from openapi import OPENAPI_SEMA

app = Flask(__name__)

# YENİ: Rate limiting. IP adresine göre istek sayısını sınırlar.
# En önemli kullanım yeri /api/auth/giris - bu olmadan biri saniyede
# binlerce şifre denemesi gönderebilir (brute-force saldırısı).
# Testler sırasında bu sınırlamanın testleri bozmaması için
# RATELIMIT_ENABLED, test fixture'ında False'a çekiliyor (tests/conftest.py).
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],  # varsayılan olarak sınır yok, sadece işaretlediğimiz endpoint'lerde var
    storage_uri="memory://"
)


# ============================================================
# KİMLİK DOĞRULAMA DEKORATÖRÜ
# ============================================================
def giris_gerekli(rol=None):
    """
    Bir endpoint'i korumak için kullanılır: @giris_gerekli() ya da
    belirli bir rol gerektiriyorsa @giris_gerekli(rol='admin').

    Nasıl çalışır: İstekteki Authorization header'ından token'ı okur,
    auth.token_dogrula ile geçerliliğini kontrol eder. Geçerliyse
    kullanıcı bilgisini request.kullanici'ye koyar ve endpoint'i çalıştırır.
    Geçersizse 401 (yetkisiz) döner, endpoint hiç çalışmaz.
    """
    def dekorator(fonksiyon):
        @wraps(fonksiyon)
        def sarmalayici(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({'hata': 'Yetkisiz. Authorization: Bearer <token> header\'ı gerekli.'}), 401

            token = auth_header.replace('Bearer ', '', 1)
            kullanici = auth.token_dogrula(token)

            if not kullanici:
                return jsonify({'hata': 'Geçersiz veya süresi dolmuş token. Tekrar giriş yapın.'}), 401

            if rol and kullanici['rol'] != rol:
                return jsonify({'hata': f'Bu işlem için "{rol}" rolü gerekli.'}), 403

            request.kullanici = kullanici
            return fonksiyon(*args, **kwargs)
        return sarmalayici
    return dekorator


# ============================================================
# Ortak yardımcı: querystring'den boolean okumak
# ============================================================
def _bool_param(ad, varsayilan=False):
    deger = request.args.get(ad, str(varsayilan)).lower()
    return deger in ('1', 'true', 'evet', 'yes')


# ============================================================
# GİRİŞ (AUTH) ENDPOINT'İ
# ============================================================
@app.route('/api/auth/giris', methods=['POST'])
@limiter.limit("5 per minute")
def giris():
    veri = request.get_json(silent=True) or {}
    kullanici_adi = veri.get('kullanici_adi')
    sifre = veri.get('sifre')

    if not kullanici_adi or not sifre:
        return jsonify({'hata': 'kullanici_adi ve sifre zorunludur.'}), 400

    sonuc = auth.giris_yap(kullanici_adi, sifre)
    if not sonuc:
        audit.kaydet(kullanici_adi, 'bilinmiyor', 'GIRIS_BASARISIZ', ip_adresi=request.remote_addr)
        return jsonify({'hata': 'Kullanıcı adı veya şifre hatalı.'}), 401

    audit.kaydet(kullanici_adi, sonuc['rol'], 'GIRIS_BASARILI', ip_adresi=request.remote_addr)
    return jsonify(sonuc)


@app.route('/api/auth/cikis', methods=['POST'])
@giris_gerekli()
def cikis():
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '', 1)
    auth.cikis_yap(token)
    return jsonify({'basarili': True})


# ============================================================
# STOK ENDPOINT'LERİ
# ============================================================
@app.route('/api/stoklar/kritik', methods=['GET'])
@giris_gerekli()
def kritik_stoklar():
    return jsonify(servisler.kritik_stoklari_getir())


@app.route('/api/stoklar/dinamik-kritik', methods=['GET'])
@giris_gerekli()
def dinamik_kritik_stoklar():
    guvenlik_gun = request.args.get('guvenlik_gun', 5, type=int)
    return jsonify(servisler.dinamik_kritik_stoklari_getir(guvenlik_gun_sayisi=guvenlik_gun))


@app.route('/api/stoklar/tahmin', methods=['GET'])
@giris_gerekli()
def tum_stok_tahmini():
    gun_sayisi = request.args.get('gun_sayisi', 30, type=int)
    return jsonify(servisler.tum_gruplar_icin_stok_tahmini(gun_sayisi=gun_sayisi))


@app.route('/api/stoklar/tahmin/<int:kan_grubu_id>', methods=['GET'])
@giris_gerekli()
def tekil_stok_tahmini(kan_grubu_id):
    sonuc = servisler.stok_tahmini_yap(kan_grubu_id)
    if sonuc is None:
        return jsonify({'hata': 'Bu kan grubu için stok kaydı bulunamadı.'}), 404
    return jsonify(sonuc)


@app.route('/api/stoklar/uyumlu/<kan_grubu_adi>', methods=['GET'])
@giris_gerekli()
def uyumlu_stok(kan_grubu_adi):
    return jsonify(servisler.uygun_yedek_stok_getir(kan_grubu_adi))


@app.route('/api/stoklar/skt-risk', methods=['GET'])
@giris_gerekli()
def skt_risk():
    return jsonify(servisler.sktt_riskli_stoklari_getir())


@app.route('/api/stoklar/cikis', methods=['POST'])
@giris_gerekli()
def kan_cikis():
    veri = request.get_json(silent=True) or {}
    kan_grubu_id = veri.get('kan_grubu_id')
    adet = veri.get('adet')

    if kan_grubu_id is None or adet is None:
        return jsonify({'hata': 'kan_grubu_id ve adet zorunludur.'}), 400

    basarili, mesaj = servisler.kan_cikis_yap(kan_grubu_id, adet)
    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'KAN_CIKISI' if basarili else 'KAN_CIKISI_BASARISIZ',
        detay=f"kan_grubu_id={kan_grubu_id}, adet={adet}, sonuc={mesaj}",
        ip_adresi=request.remote_addr
    )
    if not basarili:
        return jsonify({'hata': mesaj}), 400
    return jsonify({'basarili': True, 'uyari': mesaj})


# ============================================================
# BAĞIŞÇI ENDPOINT'LERİ
# ============================================================
@app.route('/api/bagiscilar/uygun/<int:kan_grubu_id>', methods=['GET'])
@giris_gerekli()
def uygun_bagiscilar(kan_grubu_id):
    gece_mi = _bool_param('gece')
    return jsonify(servisler.uygun_bagiscilari_getir(kan_grubu_id, gece_mi=gece_mi))


# NOT: Bu endpoint 'admin' rolü gerektiriyor - çünkü döndürdüğü mesaj
# saglik_engelleri tablosundaki hassas bilgiyi (örn. "Kronik Hepatit B")
# içerebiliyor. Sıradan personel rolü bu veriye erişemez, sadece admin.
@app.route('/api/bagiscilar/uygunluk/<int:kullanici_id>', methods=['GET'])
@giris_gerekli(rol='admin')
def bagis_uygunluk(kullanici_id):
    gece_cagrisi_mi = _bool_param('gece_cagrisi')
    return jsonify(servisler.bagis_uygunluk_kontrol_et(kullanici_id, gece_cagrisi_mi=gece_cagrisi_mi))


@app.route('/api/bagiscilar/puan/<int:bagisci_id>', methods=['GET'])
@giris_gerekli()
def bagisci_puan(bagisci_id):
    sonuc = servisler.bagisci_puan_ve_rozet_hesapla(bagisci_id)
    if sonuc is None:
        return jsonify({'hata': 'Puan hesaplanamadı.'}), 500
    return jsonify(sonuc)


@app.route('/api/bagiscilar/bagis-ekle', methods=['POST'])
@giris_gerekli()
def bagis_ekle():
    veri = request.get_json(silent=True) or {}
    kullanici_id = veri.get('kullanici_id')
    kan_grubu_id = veri.get('kan_grubu_id')

    if kullanici_id is None or kan_grubu_id is None:
        return jsonify({'hata': 'kullanici_id ve kan_grubu_id zorunludur.'}), 400

    basarili = servisler.bagis_ekle(kullanici_id, kan_grubu_id)
    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'BAGIS_EKLENDI' if basarili else 'BAGIS_EKLEME_BASARISIZ',
        detay=f"kullanici_id={kullanici_id}, kan_grubu_id={kan_grubu_id}",
        ip_adresi=request.remote_addr
    )
    if not basarili:
        return jsonify({'hata': 'Bağış eklenemedi.'}), 500
    return jsonify({'basarili': True})


# ============================================================
# YENİ BAĞIŞÇI (KULLANICI) EKLEME
# ============================================================
@app.route('/api/bagiscilar/ekle', methods=['POST'])
@giris_gerekli()
def bagisci_ekle_endpoint():
    veri = request.get_json(silent=True) or {}
    zorunlu_alanlar = ['kan_grubu_id', 'ad', 'soyad', 'cinsiyet', 'birim', 'telefon']
    eksikler = [a for a in zorunlu_alanlar if not veri.get(a)]
    if eksikler:
        return jsonify({'hata': f"Eksik alan(lar): {', '.join(eksikler)}"}), 400

    basarili, sonuc = servisler.kullanici_ekle(
        kan_grubu_id=veri['kan_grubu_id'],
        ad=veri['ad'],
        soyad=veri['soyad'],
        cinsiyet=veri['cinsiyet'],
        birim=veri['birim'],
        telefon=veri['telefon'],
        eposta=veri.get('eposta'),
        bildirim_izni=veri.get('bildirim_izni', 1),
        gece_aranir_mi=veri.get('gece_aranir_mi', 0)
    )

    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'BAGISCI_EKLENDI' if basarili else 'BAGISCI_EKLEME_BASARISIZ',
        detay=f"ad={veri.get('ad')} soyad={veri.get('soyad')}, sonuc={sonuc}",
        ip_adresi=request.remote_addr
    )

    if not basarili:
        return jsonify({'hata': sonuc}), 400
    return jsonify({'basarili': True, 'kullanici_id': sonuc})


# ============================================================
# ELLE STOK GİRİŞİ (bağış dışı - transfer, kampanya vb.)
# ============================================================
@app.route('/api/stoklar/giris', methods=['POST'])
@giris_gerekli(rol='admin')
def stok_girisi():
    veri = request.get_json(silent=True) or {}
    kan_grubu_id = veri.get('kan_grubu_id')
    adet = veri.get('adet')

    if kan_grubu_id is None or adet is None:
        return jsonify({'hata': 'kan_grubu_id ve adet zorunludur.'}), 400
    if not isinstance(adet, int) or adet <= 0:
        return jsonify({'hata': 'adet pozitif bir tam sayı olmalıdır.'}), 400

    basarili, mesaj = servisler.stok_girisi_yap(kan_grubu_id, adet)
    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'STOK_GIRISI' if basarili else 'STOK_GIRISI_BASARISIZ',
        detay=f"kan_grubu_id={kan_grubu_id}, adet={adet}, sonuc={mesaj}",
        ip_adresi=request.remote_addr
    )
    if not basarili:
        return jsonify({'hata': mesaj}), 400
    return jsonify({'basarili': True, 'mesaj': mesaj})


# ============================================================
# BİRİM BAZLI KAN TALEBİ
# ============================================================
@app.route('/api/talepler', methods=['GET'])
@giris_gerekli()
def talepleri_getir():
    return jsonify(servisler.aktif_talepleri_getir())


@app.route('/api/talepler', methods=['POST'])
@giris_gerekli()
def talep_olustur_endpoint():
    veri = request.get_json(silent=True) or {}
    kan_grubu_id = veri.get('kan_grubu_id')
    talep_eden_birim = veri.get('talep_eden_birim')

    if not kan_grubu_id or not talep_eden_birim:
        return jsonify({'hata': 'kan_grubu_id ve talep_eden_birim zorunludur.'}), 400

    basarili, sonuc = servisler.talep_olustur(kan_grubu_id, talep_eden_birim)
    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'TALEP_OLUSTURULDU' if basarili else 'TALEP_OLUSTURMA_BASARISIZ',
        detay=f"kan_grubu_id={kan_grubu_id}, birim={talep_eden_birim}",
        ip_adresi=request.remote_addr
    )
    if not basarili:
        return jsonify({'hata': sonuc}), 400
    return jsonify({'basarili': True, 'talep_id': sonuc})


@app.route('/api/talepler/<int:talep_id>/kapat', methods=['POST'])
@giris_gerekli(rol='admin')
def talep_kapat_endpoint(talep_id):
    basarili, mesaj = servisler.talep_kapat(talep_id)
    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'TALEP_KAPATILDI' if basarili else 'TALEP_KAPATMA_BASARISIZ',
        detay=f"talep_id={talep_id}",
        ip_adresi=request.remote_addr
    )
    if not basarili:
        return jsonify({'hata': mesaj}), 404
    return jsonify({'basarili': True, 'mesaj': mesaj})


# ============================================================
# ACİL ÇAĞRI ENDPOINT'LERİ
# ============================================================
@app.route('/api/acil-cagri/<int:kan_grubu_id>', methods=['GET'])
@giris_gerekli()
def acil_cagri(kan_grubu_id):
    return jsonify(servisler.acil_cagri_listesi_hazirla(kan_grubu_id))


@app.route('/api/acil-cagri/<int:kan_grubu_id>/agirlikli', methods=['GET'])
@giris_gerekli()
def acil_cagri_agirlikli(kan_grubu_id):
    gece_cagrisi_mi = _bool_param('gece_cagrisi')
    return jsonify(servisler.agirlikli_acil_liste_hazirla(kan_grubu_id, gece_cagrisi_mi=gece_cagrisi_mi))


# ============================================================
# BİLDİRİM ENDPOINT'İ
# ============================================================
@app.route('/api/bildirim/acil-cagri-gonder', methods=['POST'])
@giris_gerekli()
def acil_cagri_bildirimi_gonder():
    veri = request.get_json(silent=True) or {}
    kullanici_id = veri.get('kullanici_id')
    kan_grubu_adi = veri.get('kan_grubu_adi')

    if not kullanici_id or not kan_grubu_adi:
        return jsonify({'hata': 'kullanici_id ve kan_grubu_adi zorunludur.'}), 400

    kullanici = servisler.kullanici_getir(kullanici_id)
    if not kullanici:
        return jsonify({'hata': 'Kullanıcı bulunamadı.'}), 404

    if not kullanici['kullanici_eposta']:
        return jsonify({'hata': 'Bu kullanıcının kayıtlı e-posta adresi yok.'}), 400

    konu, icerik = bildirim.acil_kan_ihtiyaci_bildirimi_olustur(kan_grubu_adi)
    basarili, mesaj = bildirim.eposta_gonder(kullanici['kullanici_eposta'], konu, icerik)

    audit.kaydet(
        request.kullanici['kullanici_adi'], request.kullanici['rol'],
        'BILDIRIM_GONDERILDI' if basarili else 'BILDIRIM_BASARISIZ',
        detay=f"kullanici_id={kullanici_id}, kan_grubu={kan_grubu_adi}, sonuc={mesaj}",
        ip_adresi=request.remote_addr
    )

    if not basarili:
        return jsonify({'hata': mesaj}), 500
    return jsonify({'basarili': True, 'mesaj': mesaj})


# ============================================================
# İŞLEM GEÇMİŞİ (AUDIT TRAIL) ENDPOINT'İ
# ============================================================
@app.route('/api/audit/gecmis', methods=['GET'])
@giris_gerekli(rol='admin')
def audit_gecmisi():
    limit = request.args.get('limit', 100, type=int)
    kullanici_filtre = request.args.get('kullanici_adi')
    return jsonify(audit.gecmisi_getir(limit=limit, kullanici_adi_filtre=kullanici_filtre))


# ============================================================
# API DOKÜMANTASYONU (Swagger UI)
# ============================================================
@app.route('/api/openapi.json', methods=['GET'])
def openapi_semasi():
    return jsonify(OPENAPI_SEMA)


@app.route('/docs', methods=['GET'])
def docs():
    # Swagger UI, CDN üzerinden yüklenir - proje içine ekstra dosya/kütüphane
    # kurmaya gerek kalmaz. Sayfa sadece /api/openapi.json'daki şemayı okuyup
    # interaktif dokümantasyon oluşturur.
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Kan Bankası API Dokümantasyonu</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: '/api/openapi.json',
                dom_id: '#swagger-ui'
            });
        };
    </script>
</body>
</html>
"""


# ============================================================
# SAĞLIK KONTROLÜ (API ayakta mı?)
# ============================================================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'durum': 'ayakta'})


if __name__ == '__main__':
    # debug=True SADECE geliştirme aşamasında kullanılır.
    # Üretimde (gerçek hastanede) asla debug=True ile çalıştırılmamalı,
    # çünkü hata sayfaları sunucu içindeki kodu ve dosya yollarını
    # tarayıcıya sızdırır. Bunu ileride hatırlat.
    app.run(debug=True, port=5000)