"""Akıllı Hastane Kan Bankası Yönetim Paneli REST API'si."""

from __future__ import annotations

from functools import wraps

from flask import Flask, g, jsonify, request
from flask_cors import CORS

import auth
import servisler
import veritabani
import veriler


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(SEED_DEMO=True)
    if test_config:
        app.config.update(test_config)
    if app.config.get("DATABASE_PATH"):
        veritabani.veritabani_yolunu_ayarla(app.config["DATABASE_PATH"])

    app.json.ensure_ascii = False
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    veritabani.veritabani_baslat()
    if app.config["SEED_DEMO"]:
        veriler.ornek_verileri_yukle()

    def istek_tokeni() -> str | None:
        baslik = request.headers.get("Authorization", "")
        return baslik.removeprefix("Bearer ").strip() or None

    def yetki_gerekli(*roller):
        def dekorator(fonksiyon):
            @wraps(fonksiyon)
            def sarmalayici(*args, **kwargs):
                kullanici = auth.token_dogrula(istek_tokeni())
                if not kullanici:
                    return jsonify({"durum": "hata", "mesaj": "Geçersiz veya süresi dolmuş oturum."}), 401
                if roller and kullanici["rol"] not in roller:
                    return jsonify({"durum": "hata", "mesaj": "Bu işlem için yönetici yetkisi gerekir."}), 403
                g.kullanici = kullanici
                return fonksiyon(*args, **kwargs)
            return sarmalayici
        return dekorator

    def bagisci_yetkisi_gerekli(fonksiyon):
        @wraps(fonksiyon)
        def sarmalayici(*args, **kwargs):
            kullanici = auth.bagisci_token_dogrula(istek_tokeni())
            if not kullanici:
                return jsonify({"durum": "hata", "mesaj": "Geçersiz veya süresi dolmuş bağışçı oturumu."}), 401
            g.bagisci_kullanici = kullanici
            return fonksiyon(*args, **kwargs)
        return sarmalayici

    @app.get("/api/health")
    def health_check():
        return jsonify({"durum": "ayakta", "mesaj": "Kan Bankası API çalışıyor."})

    @app.post("/api/auth/giris")
    @app.post("/api/giris")
    def giris():
        veri = request.get_json(silent=True) or {}
        if not veri.get("kullanici_adi") or not veri.get("sifre"):
            return jsonify({"basarili": False, "mesaj": "Kullanıcı adı ve şifre gereklidir."}), 400
        sonuc = auth.giris_yap(veri["kullanici_adi"], veri["sifre"], request.remote_addr)
        return jsonify(sonuc), 200 if sonuc["basarili"] else 401

    @app.post("/api/bagisci-auth/giris")
    def bagisci_giris():
        veri = request.get_json(silent=True) or {}
        if not veri.get("kullanici_adi") or not veri.get("sifre"):
            return jsonify({"basarili": False, "mesaj": "Kullanıcı adı ve şifre gereklidir."}), 400
        sonuc = auth.bagisci_giris_yap(
            veri["kullanici_adi"], veri["sifre"], request.remote_addr
        )
        return jsonify(sonuc), 200 if sonuc["basarili"] else 401

    @app.post("/api/bagisci-auth/kayit")
    def bagisci_kayit():
        basarili, sonuc = auth.bagisci_kaydi_olustur(
            request.get_json(silent=True) or {}, request.remote_addr
        )
        return jsonify({
            "durum": "basarili" if basarili else "hata",
            "veri": sonuc if basarili else None,
            "mesaj": "Kaydınız oluşturuldu. Kullanıcı adınızla giriş yapabilirsiniz."
            if basarili else sonuc,
        }), 201 if basarili else 400

    @app.get("/api/genel/kan-gruplari")
    def genel_kan_gruplari():
        return jsonify({"durum": "basarili", "veri": servisler.kan_gruplari_getir()})

    @app.post("/api/bagisci-auth/cikis")
    @bagisci_yetkisi_gerekli
    def bagisci_cikis():
        auth.bagisci_cikis_yap(istek_tokeni())
        return jsonify({"durum": "basarili", "mesaj": "Bağışçı oturumu kapatıldı."})

    @app.get("/api/bagisci-panel/ozet")
    @bagisci_yetkisi_gerekli
    def bagisci_panel_ozet():
        sonuc = servisler.bagisci_panel_ozeti(g.bagisci_kullanici["bagisci_id"])
        if not sonuc:
            return jsonify({"durum": "hata", "mesaj": "Bağışçı kaydı bulunamadı."}), 404
        return jsonify({"durum": "basarili", "veri": sonuc})

    @app.patch("/api/bagisci-panel/bildirim-izni")
    @bagisci_yetkisi_gerekli
    def bagisci_bildirim_izni():
        veri = request.get_json(silent=True) or {}
        servisler.bagisci_bildirim_izni_guncelle(
            g.bagisci_kullanici["bagisci_id"], bool(veri.get("bildirim_izni"))
        )
        return jsonify({"durum": "basarili", "mesaj": "Bildirim tercihi güncellendi."})

    @app.post("/api/bagisci-panel/on-degerlendirme")
    @bagisci_yetkisi_gerekli
    def bagisci_on_degerlendirme():
        basarili, sonuc = servisler.bagisci_on_degerlendirme_kaydet(
            g.bagisci_kullanici["bagisci_id"],
            request.get_json(silent=True) or {},
            request.remote_addr,
        )
        return jsonify({
            "durum": "basarili" if basarili else "hata",
            "veri": sonuc if basarili else None,
            "mesaj": sonuc["mesaj"] if basarili else sonuc,
        }), 201 if basarili else 400

    @app.post("/api/auth/cikis")
    @yetki_gerekli()
    def cikis():
        auth.cikis_yap(istek_tokeni())
        return jsonify({"durum": "basarili", "mesaj": "Oturum güvenli biçimde kapatıldı."})

    @app.get("/api/oturum")
    @yetki_gerekli()
    def oturum():
        kullanici = dict(g.kullanici)
        kullanici["rol_etiketi"] = "Yönetici" if kullanici["rol"] == "admin" else "Personel"
        return jsonify({"durum": "basarili", "veri": kullanici})

    @app.get("/api/ozet")
    @yetki_gerekli()
    def ozet():
        return jsonify({"durum": "basarili", "veri": servisler.ozet_getir()})

    @app.get("/api/kan-gruplari")
    @yetki_gerekli()
    def kan_gruplari():
        return jsonify({"durum": "basarili", "veri": servisler.kan_gruplari_getir()})

    @app.get("/api/stoklar")
    @app.get("/api/stok")
    @yetki_gerekli()
    def stoklar():
        return jsonify({"durum": "basarili", "veri": servisler.stok_durumu_getir()})

    @app.get("/api/acil-cagri-adaylari")
    @yetki_gerekli("admin")
    def acil_cagri_adaylari():
        kan_grubu = request.args.get("kan_grubu", "")
        if not kan_grubu:
            return jsonify({"durum": "hata", "mesaj": "Kan grubu seçilmelidir."}), 400
        return jsonify({
            "durum": "basarili",
            "veri": servisler.acil_cagri_adaylari_getir(
                kan_grubu, request.args.get("limit", 20)
            ),
        })

    @app.post("/api/acil-cagrilar")
    @yetki_gerekli("admin")
    def acil_cagri_olustur():
        veri = request.get_json(silent=True) or {}
        if not veri.get("kan_grubu_adi") or not veri.get("aciklama"):
            return jsonify({"durum": "hata", "mesaj": "Kan grubu ve açıklama zorunludur."}), 400
        basarili, sonuc = servisler.acil_cagri_olustur(
            veri["kan_grubu_adi"], veri["aciklama"], int(veri.get("limit", 20)),
            g.kullanici["id"], request.remote_addr,
            eposta_gonderilsin=veri.get("eposta_gonder") is True,
        )
        return jsonify({
            "durum": "basarili" if basarili else "hata",
            "veri": sonuc if basarili else None,
            "mesaj": sonuc["mesaj"] if basarili else sonuc,
        }), 201 if basarili else 400

    @app.get("/api/bildirim/ayar-durumu")
    @yetki_gerekli("admin")
    def bildirim_ayar_durumu():
        return jsonify({"durum": "basarili", "veri": servisler.eposta_ayar_durumu()})

    @app.get("/api/bildirim/eposta-gonderimleri")
    @yetki_gerekli("admin")
    def eposta_gonderimleri():
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        return jsonify({
            "durum": "basarili",
            "veri": servisler.eposta_gonderimleri_getir(limit),
        })

    @app.get("/api/bagiscilar")
    @yetki_gerekli()
    def bagiscilar():
        return jsonify({
            "durum": "basarili",
            "veri": servisler.bagiscilari_getir(request.args.get("arama", "")),
        })

    @app.post("/api/bagiscilar")
    @yetki_gerekli("admin")
    def bagisci_olustur():
        veri = request.get_json(silent=True) or {}
        veri.update(api_kullanici_id=g.kullanici["id"], ip_adresi=request.remote_addr)
        basarili, sonuc = servisler.bagisci_ekle(veri)
        return jsonify({"durum": "basarili" if basarili else "hata", "veri": sonuc if basarili else None,
                        "mesaj": "Bağışçı numarası sistem tarafından üretildi." if basarili else sonuc}), 201 if basarili else 400

    @app.get("/api/bagiscilar/<int:bagisci_id>/uygunluk")
    @yetki_gerekli()
    def bagisci_uygunluk(bagisci_id):
        sonuc = servisler.bagis_uygunluk_kontrol_et(bagisci_id)
        kod = 404 if sonuc["durum"] == "KAYIT BULUNAMADI" else 200
        return jsonify({"durum": "basarili" if kod == 200 else "hata", "veri": sonuc}), kod

    @app.post("/api/bagiscilar/<int:bagisci_id>/engeller")
    @yetki_gerekli("admin")
    def engel_ekle(bagisci_id):
        basarili, mesaj = servisler.saglik_engeli_ekle(
            bagisci_id, request.get_json(silent=True) or {}, g.kullanici["id"], request.remote_addr
        )
        return jsonify({"durum": "basarili" if basarili else "hata", "mesaj": mesaj}), 201 if basarili else 400

    @app.post("/api/bagislar")
    @app.post("/api/bagis")
    @yetki_gerekli()
    def bagis_kaydet():
        veri = request.get_json(silent=True) or {}
        if not veri.get("bagisci_id"):
            return jsonify({"durum": "hata", "mesaj": "Listeden bir bağışçı seçilmelidir."}), 400
        try:
            adet = int(veri.get("adet", 1))
        except (TypeError, ValueError):
            return jsonify({"durum": "hata", "mesaj": "Adet sayısal olmalıdır."}), 400
        basarili, mesaj = servisler.bagis_kaydet(
            int(veri["bagisci_id"]), veri.get("bilesen_turu", "Tam Kan"), adet,
            g.kullanici["id"], request.remote_addr,
        )
        return jsonify({"durum": "basarili" if basarili else "hata", "mesaj": mesaj}), 201 if basarili else 400

    @app.get("/api/envanter")
    @yetki_gerekli()
    def envanter():
        return jsonify({
            "durum": "basarili",
            "veri": servisler.envanter_getir(
                request.args.get("kan_grubu", ""),
                request.args.get("bilesen_turu", ""),
                request.args.get("durum", ""),
            ),
        })

    @app.post("/api/cikislar")
    @app.post("/api/cikis")
    @yetki_gerekli()
    def kan_cikis():
        veri = request.get_json(silent=True) or {}
        zorunlu = ["kan_grubu_adi", "bilesen_turu", "adet", "talep_eden_birim"]
        eksikler = [alan for alan in zorunlu if not veri.get(alan)]
        if eksikler:
            return jsonify({"durum": "hata", "mesaj": f"Eksik alanlar: {', '.join(eksikler)}"}), 400
        try:
            adet = int(veri["adet"])
        except (TypeError, ValueError):
            return jsonify({"durum": "hata", "mesaj": "Adet sayısal olmalıdır."}), 400
        basarili, mesaj = servisler.kan_cikis_yap(
            veri["kan_grubu_adi"], veri["bilesen_turu"], adet, veri["talep_eden_birim"],
            g.kullanici["id"], request.remote_addr,
        )
        return jsonify({"durum": "basarili" if basarili else "hata", "mesaj": mesaj}), 200 if basarili else 400

    @app.get("/api/kurallar")
    @yetki_gerekli()
    def kurallar():
        return jsonify({"durum": "basarili", "veri": servisler.kurallar_getir()})

    @app.get("/api/islemler")
    @yetki_gerekli()
    def islemler():
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        return jsonify({"durum": "basarili", "veri": servisler.islem_gecmisi_getir(limit)})

    @app.errorhandler(404)
    def bulunamadi(_error):
        return jsonify({"durum": "hata", "mesaj": "API adresi bulunamadı."}), 404

    @app.errorhandler(Exception)
    def beklenmeyen_hata(error):
        if app.config.get("TESTING"):
            raise error
        return jsonify({"durum": "hata", "mesaj": f"Beklenmeyen sunucu hatası: {error}"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
