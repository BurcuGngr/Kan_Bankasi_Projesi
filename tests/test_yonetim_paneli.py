from datetime import date, timedelta

import bildirim


def test_health_herkese_acik(client):
    yanit = client.get("/api/health")
    assert yanit.status_code == 200
    assert yanit.get_json()["durum"] == "ayakta"


def test_yanlis_sifre_reddedilir(client):
    yanit = client.post("/api/auth/giris", json={"kullanici_adi": "admin", "sifre": "yanlis"})
    assert yanit.status_code == 401


def test_korumali_uclar_token_ister(client):
    assert client.get("/api/stoklar").status_code == 401
    assert client.get("/api/bagiscilar").status_code == 401
    assert client.get("/api/envanter").status_code == 401


def test_sekiz_kan_grubu_stokta_gorunur(client, admin_headers):
    yanit = client.get("/api/stoklar", headers=admin_headers)
    veri = yanit.get_json()["veri"]
    assert yanit.status_code == 200
    assert len(veri) == 8
    assert {kayit["grup_adi"] for kayit in veri} == {
        "A Rh+", "A Rh-", "B Rh+", "B Rh-", "0 Rh+", "0 Rh-", "AB Rh+", "AB Rh-"
    }


def test_bagisci_numarasi_sistem_tarafindan_uretilir(client, admin_headers):
    yanit = client.post("/api/bagiscilar", headers=admin_headers, json={
        "ad": "Test", "soyad": "Bağışçı", "cinsiyet": "Erkek", "birim": "Acil",
        "telefon": "05559990000", "kan_grubu_id": 1,
    })
    govde = yanit.get_json()
    assert yanit.status_code == 201
    assert govde["veri"]["bagisci_no"].startswith("KB-")
    assert isinstance(govde["veri"]["id"], int)


def test_ayni_telefonla_kimlik_karisikligi_engellenir(client, admin_headers):
    veri = {
        "ad": "Bir", "soyad": "Kişi", "cinsiyet": "Kadın", "birim": "Acil",
        "telefon": "05558887766", "kan_grubu_id": 1,
    }
    assert client.post("/api/bagiscilar", headers=admin_headers, json=veri).status_code == 201
    veri["ad"] = "İkinci"
    yanit = client.post("/api/bagiscilar", headers=admin_headers, json=veri)
    assert yanit.status_code == 400
    assert "zaten var" in yanit.get_json()["mesaj"]


def test_cinsiyet_bekleme_suresi_ve_dovme_aciklanir(client, admin_headers):
    bagiscilar = client.get("/api/bagiscilar", headers=admin_headers).get_json()["veri"]
    burcu = next(b for b in bagiscilar if b["ad"] == "Burcu")
    assert burcu["uygunluk"]["bagis_araligi_gun"] == 120
    assert burcu["uygunluk"]["uygun_mu"] is False
    assert any("Dövme" in neden or "dövme" in neden for neden in burcu["uygunluk"]["nedenler"])


def test_kalici_saglik_engeli_bagisi_reddeder(client, admin_headers):
    bagiscilar = client.get("/api/bagiscilar", headers=admin_headers).get_json()["veri"]
    esra = next(b for b in bagiscilar if b["ad"] == "Esra")
    yanit = client.post("/api/bagislar", headers=admin_headers, json={
        "bagisci_id": esra["id"], "bilesen_turu": "Tam Kan", "adet": 1,
    })
    assert yanit.status_code == 400
    assert "kalıcı" in yanit.get_json()["mesaj"].lower()


def test_bagista_kan_grubu_profilden_otomatik_alinir(client, admin_headers):
    bagiscilar = client.get("/api/bagiscilar", headers=admin_headers).get_json()["veri"]
    adem = next(b for b in bagiscilar if b["ad"] == "Adem")
    assert adem["uygunluk"]["uygun_mu"] is True
    yanit = client.post("/api/bagislar", headers=admin_headers, json={
        "bagisci_id": adem["id"], "bilesen_turu": "Tam Kan", "adet": 1,
        "kan_grubu_adi": "AB Rh-",
    })
    assert yanit.status_code == 201
    envanter = client.get("/api/envanter", headers=admin_headers).get_json()["veri"]
    yeni = max(envanter, key=lambda kayit: kayit["id"])
    assert yeni["bagisci_no"] == adem["bagisci_no"]
    assert yeni["grup_adi"] == "0 Rh+"


def test_envanter_unite_izlenebilirligi_saglar(client, admin_headers):
    veri = client.get("/api/envanter", headers=admin_headers).get_json()["veri"]
    assert veri
    beklenen = {
        "unite_kodu", "bagisci_no", "bagisci", "grup_adi", "bilesen_turu",
        "bagis_tarihi", "son_kullanma_tarihi", "kalan_gun", "saklama_konumu", "durum",
    }
    assert beklenen.issubset(veri[0])


def test_fifo_cikisi_stogu_azaltir(client, admin_headers):
    once = client.get("/api/stoklar", headers=admin_headers).get_json()["veri"]
    aday = next(s for s in once if s["unite_sayisi"] > 5)
    envanter = client.get("/api/envanter", headers=admin_headers).get_json()["veri"]
    urun = next(u["bilesen_turu"] for u in envanter if u["grup_adi"] == aday["grup_adi"] and u["durum"] == "AKTİF")
    yanit = client.post("/api/cikislar", headers=admin_headers, json={
        "kan_grubu_adi": aday["grup_adi"], "bilesen_turu": urun,
        "adet": 1, "talep_eden_birim": "Test Acil",
    })
    assert yanit.status_code == 200
    sonra = client.get("/api/stoklar", headers=admin_headers).get_json()["veri"]
    guncel = next(s for s in sonra if s["grup_adi"] == aday["grup_adi"])
    assert guncel["unite_sayisi"] == aday["unite_sayisi"] - 1


def test_kurallar_panelde_gorunur(client, admin_headers):
    veri = client.get("/api/kurallar", headers=admin_headers).get_json()["veri"]
    assert {k["gun"] for k in veri["bagis_araliklari"]} == {90, 120}
    assert any(k["kural"] == "Dövme" and "12 ay" in k["bekleme"] for k in veri["saglik_kurallari"])
    assert any(k["urun"] == "Eritrosit" and k["raf_omru_gun"] == 42 for k in veri["urun_kurallari"])


def test_staj_kayitlari_ayri_tablo_yerine_islem_gecmisine_eklenir(client, admin_headers):
    islemler = client.get("/api/islemler", headers=admin_headers).get_json()["veri"]
    rapor_kayitlari = [kayit for kayit in islemler if kayit["kaynak"] == "STAJ RAPORU"]
    assert len(rapor_kayitlari) == 6
    assert any(kayit["tarih"].startswith("2026-08-27") for kayit in rapor_kayitlari)
    assert all(kayit["kullanici_adi"] == "staj raporu" for kayit in rapor_kayitlari)
    assert any(kayit["kaynak"] == "CANLI SİSTEM" for kayit in islemler)


def test_bagisci_kendi_kaydini_olusturup_giris_yapabilir(client):
    gruplar = client.get("/api/genel/kan-gruplari")
    assert gruplar.status_code == 200
    assert len(gruplar.get_json()["veri"]) == 8

    kayit = client.post("/api/bagisci-auth/kayit", json={
        "ad": "Yeni", "soyad": "Bağışçı", "cinsiyet": "Kadın",
        "birim": "Merkez Hastane", "telefon": "05550001122",
        "eposta": "yeni.bagisci@gmail.com", "kan_grubu_id": 1,
        "kullanici_adi": "yenibagisci", "sifre": "Guvenli123!",
    })
    assert kayit.status_code == 201
    assert kayit.get_json()["veri"]["bagisci_no"].startswith("KB-")

    giris = client.post("/api/bagisci-auth/giris", json={
        "kullanici_adi": "yenibagisci", "sifre": "Guvenli123!",
    })
    assert giris.status_code == 200
    assert giris.get_json()["kullanici"]["ad_soyad"] == "Yeni Bağışçı"


def test_bagisci_kaydi_cakismalari_ve_ornek_epostayi_reddeder(client):
    temel = {
        "ad": "Deneme", "soyad": "Kişi", "cinsiyet": "Erkek",
        "birim": "Merkez", "telefon": "05550002233",
        "eposta": "deneme@gmail.com", "kan_grubu_id": 1,
        "kullanici_adi": "denemekisi", "sifre": "Guvenli123!",
    }
    assert client.post("/api/bagisci-auth/kayit", json=temel).status_code == 201
    cakisan = {**temel, "kullanici_adi": "baskakisi"}
    assert client.post("/api/bagisci-auth/kayit", json=cakisan).status_code == 400
    ornek = {
        **temel, "telefon": "05550003344", "kullanici_adi": "ornekhesap",
        "eposta": "ornek@example.test",
    }
    yanit = client.post("/api/bagisci-auth/kayit", json=ornek)
    assert yanit.status_code == 400
    assert "geçerli bir e-posta" in yanit.get_json()["mesaj"]


def test_bagisci_tokeni_sadece_kendi_panelini_acar(client):
    giris = client.post("/api/bagisci-auth/giris", json={
        "kullanici_adi": "adem", "sifre": "Bagisci123!",
    })
    assert giris.status_code == 200
    token = giris.get_json()["token"]
    yanit = client.get(
        "/api/bagisci-panel/ozet", headers={"Authorization": f"Bearer {token}"}
    )
    assert yanit.status_code == 200
    veri = yanit.get_json()["veri"]
    assert veri["profil"]["ad"] == "Adem"
    assert veri["profil"]["toplam_puan"] >= 100
    assert veri["profil"]["unvan"] in {"Bronz", "Gümüş", "Altın", "Platin"}
    assert veri["bagislar"]


def test_bagisci_on_degerlendirmesi_dovmeyi_uygunluga_yansitir(client, admin_headers):
    giris = client.post("/api/bagisci-auth/giris", json={
        "kullanici_adi": "adem", "sifre": "Bagisci123!",
    })
    token = giris.get_json()["token"]
    dovme_tarihi = (date.today() - timedelta(days=30)).isoformat()
    yanit = client.post(
        "/api/bagisci-panel/on-degerlendirme",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "dovme_piercing_mi": True,
            "dovme_tarihi": dovme_tarihi,
            "ates_enfeksiyon_mi": False,
            "antibiyotik_ilac_mi": False,
            "ameliyat_transfuzyon_mi": False,
            "hamilelik_emzirme_mi": False,
            "onay": True,
        },
    )
    assert yanit.status_code == 201
    assert yanit.get_json()["veri"]["inceleme_gerekli"] is True

    ozet = client.get(
        "/api/bagisci-panel/ozet", headers={"Authorization": f"Bearer {token}"}
    ).get_json()["veri"]
    assert ozet["on_degerlendirme"]["dovme_piercing_mi"] == 1
    assert ozet["uygunluk"]["uygun_mu"] is False
    assert any("Dövme" in neden or "ön değerlendirme" in neden for neden in ozet["uygunluk"]["nedenler"])

    bagiscilar = client.get("/api/bagiscilar", headers=admin_headers).get_json()["veri"]
    adem = next(bagisci for bagisci in bagiscilar if bagisci["ad"] == "Adem")
    assert adem["on_degerlendirme"]["inceleme_gerekli"] is True


def test_on_degerlendirme_onay_olmadan_kaydedilmez(client):
    giris = client.post("/api/bagisci-auth/giris", json={
        "kullanici_adi": "adem", "sifre": "Bagisci123!",
    })
    token = giris.get_json()["token"]
    yanit = client.post(
        "/api/bagisci-panel/on-degerlendirme",
        headers={"Authorization": f"Bearer {token}"},
        json={"dovme_piercing_mi": False, "onay": False},
    )
    assert yanit.status_code == 400
    assert "onaylamalısınız" in yanit.get_json()["mesaj"]


def test_oncelikli_cagri_bildirim_izinli_ve_uygun_adaylari_siralar(client, admin_headers):
    yanit = client.get(
        "/api/acil-cagri-adaylari?kan_grubu=0%20Rh%2B", headers=admin_headers
    )
    assert yanit.status_code == 200
    adaylar = yanit.get_json()["veri"]
    assert len(adaylar) >= 3
    assert all(aday["grup_adi"] == "0 Rh+" for aday in adaylar)
    assert all(aday["uygunluk"]["uygun_mu"] for aday in adaylar)
    assert any(aday["eposta"] == "burcujungk00k97@gmail.com" for aday in adaylar)
    assert [aday["sira"] for aday in adaylar] == list(range(1, len(adaylar) + 1))


def test_kritik_stok_bagisi_150_puan_kazandirir(client, admin_headers):
    gruplar = client.get("/api/kan-gruplari", headers=admin_headers).get_json()["veri"]
    kritik_grup = next(grup for grup in gruplar if grup["grup_adi"] == "B Rh-")
    yeni = client.post("/api/bagiscilar", headers=admin_headers, json={
        "ad": "Puan", "soyad": "Testi", "cinsiyet": "Erkek", "birim": "Acil",
        "telefon": "05557776655", "kan_grubu_id": kritik_grup["id"],
    }).get_json()["veri"]
    yanit = client.post("/api/bagislar", headers=admin_headers, json={
        "bagisci_id": yeni["id"], "bilesen_turu": "Tam Kan", "adet": 1,
    })
    assert yanit.status_code == 201
    assert "+150 puan" in yanit.get_json()["mesaj"]
    bagiscilar = client.get("/api/bagiscilar", headers=admin_headers).get_json()["veri"]
    puan_testi = next(b for b in bagiscilar if b["id"] == yeni["id"])
    assert puan_testi["toplam_puan"] == 150
    assert puan_testi["unvan"] == "Bronz"


def test_acil_cagri_kaydi_eposta_secmeden_olusturulur(client, admin_headers):
    yanit = client.post("/api/acil-cagrilar", headers=admin_headers, json={
        "kan_grubu_adi": "0 Rh+", "aciklama": "Acil servis test çağrısı", "limit": 5,
    })
    assert yanit.status_code == 201
    veri = yanit.get_json()["veri"]
    assert veri["cagri_id"] > 0
    assert veri["eposta_ozeti"] is None
    assert "çağrı kaydı oluşturuldu" in veri["mesaj"].lower()


def test_acil_cagri_epostalari_gonderilir_ve_kaydedilir(
    client, admin_headers, monkeypatch
):
    gonderilenler = []
    monkeypatch.setattr(bildirim, "smtp_ayar_durumu", lambda: {
        "yapilandirildi": True,
        "sunucu": "smtp.test",
        "port": 587,
    })
    monkeypatch.setattr(
        bildirim,
        "eposta_gonder",
        lambda alici, konu, icerik: (
            gonderilenler.append((alici, konu, icerik)) is None,
            "E-posta başarıyla gönderildi.",
        ),
    )

    yanit = client.post("/api/acil-cagrilar", headers=admin_headers, json={
        "kan_grubu_adi": "0 Rh+",
        "aciklama": "Acil servis için kan ihtiyacı",
        "limit": 5,
        "eposta_gonder": True,
    })
    assert yanit.status_code == 201
    ozet = yanit.get_json()["veri"]["eposta_ozeti"]
    assert ozet["gonderildi"] == len(gonderilenler) > 0
    assert ozet["basarisiz"] == 0

    gecmis = client.get(
        "/api/bildirim/eposta-gonderimleri", headers=admin_headers
    ).get_json()["veri"]
    assert len(gecmis) == len(gonderilenler)
    assert all(kayit["durum"] == "GÖNDERİLDİ" for kayit in gecmis)


def test_smtp_ayari_olmadan_gercek_gonderim_reddedilir(
    client, admin_headers, monkeypatch
):
    monkeypatch.setattr(bildirim, "smtp_ayar_durumu", lambda: {
        "yapilandirildi": False,
        "sunucu": "smtp.gmail.com",
        "port": 587,
    })
    yanit = client.post("/api/acil-cagrilar", headers=admin_headers, json={
        "kan_grubu_adi": "0 Rh+",
        "aciklama": "Acil servis için kan ihtiyacı",
        "limit": 5,
        "eposta_gonder": True,
    })
    assert yanit.status_code == 400
    assert "SMTP ayarları eksik" in yanit.get_json()["mesaj"]


def test_ornek_eposta_adresi_smtpye_gonderilmez(monkeypatch):
    monkeypatch.setattr(bildirim, "_smtp_ayarlari", lambda: {
        "yapilandirildi": True,
        "sunucu": "smtp.test",
        "port": 587,
        "gonderen": "gonderen@test.local",
        "sifre": "gizli",
    })

    basarili, mesaj = bildirim.eposta_gonder(
        "ornek@example.test", "Deneme", "Deneme içeriği"
    )

    assert basarili is False
    assert "örnek e-posta adresi" in mesaj


def test_teknik_smtp_ifadesi_bagisci_epostasinda_gorunmez():
    konu, icerik = bildirim.acil_kan_ihtiyaci_bildirimi_olustur(
        "A Rh+", "SMTP bağlantı doğrulama testi"
    )

    assert konu == "Acil kan ihtiyacı: A Rh+"
    assert "SMTP" not in icerik
    assert "doğrulama" not in icerik
    assert "testi" not in icerik
    assert "İhtiyaç bilgisi: Acil servis için uygun bağışçı çağrısı" in icerik
