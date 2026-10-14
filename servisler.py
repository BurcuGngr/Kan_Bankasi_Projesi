"""Kan bankası iş kuralları ve sorgu katmanı."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import audit
import bildirim
import veritabani


BAGIS_ARALIKLARI = {"Erkek": 90, "Kadın": 120}
STANDART_BAGIS_PUANI = 100
KRITIK_STOK_BONUSU = 50
URUN_KURALLARI = {
    "Tam Kan": {
        "raf_omru_gun": 35,
        "aciklama": "Tam kan ünitesi için sistemde kullanılan süre parametresi.",
    },
    "Eritrosit": {
        "raf_omru_gun": 42,
        "aciklama": "Raporda belirtilen alyuvar süspansiyonu üst süre parametresi.",
    },
    "Trombosit": {
        "raf_omru_gun": 5,
        "aciklama": "Rapordaki 5–7 günlük aralığın sistemde kullanılan alt sınırı.",
    },
}
TIBBI_UYARI = (
    "Bağış uygunluğu; bağışçı sorgulama formu, muayene ve yetkili hekim onayı "
    "tamamlandıktan sonra kesinleşir."
)
STAJ_GELISTIRME_KAYITLARI = [
    {
        "id": "rapor-20260827", "tarih": "2026-08-27 10:30:00",
        "kullanici_adi": "staj raporu", "islem_turu": "E-POSTA TESTİ",
        "detay": (
            "Google 2 Adımlı Doğrulama ve Uygulama Şifresi ile e-posta gönderimi "
            "yapılandırıldı; acil durum e-posta testi raporda doğrulandı."
        ),
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
    {
        "id": "rapor-20260828", "tarih": "2026-08-28 14:20:00",
        "kullanici_adi": "staj raporu", "islem_turu": "ARAYÜZ BAĞLANTISI",
        "detay": "React arayüzü API'ye bağlandı; JWT ve stok görselleri geliştirildi.",
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
    {
        "id": "rapor-20260831", "tarih": "2026-08-31 11:15:00",
        "kullanici_adi": "staj raporu", "islem_turu": "API TESTİ",
        "detay": "Bağış ve stok çıkış servisleri Thunder Client ile test edildi.",
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
    {
        "id": "rapor-20260901", "tarih": "2026-09-01 15:40:00",
        "kullanici_adi": "staj raporu", "islem_turu": "KİMLİK DOĞRULAMA",
        "detay": "JWT tabanlı giriş ve yetkili uç noktalar doğrulandı.",
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
    {
        "id": "rapor-20260903", "tarih": "2026-09-03 13:10:00",
        "kullanici_adi": "staj raporu", "islem_turu": "STOK PANELİ",
        "detay": "Sekiz kan grubu için anlık stok kartları yönetici panelinde gösterildi.",
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
    {
        "id": "rapor-20260904", "tarih": "2026-09-04 16:25:00",
        "kullanici_adi": "staj raporu", "islem_turu": "DENETİM EKRANI",
        "detay": "İşlem kayıtlarının arayüzde görüntülenmesi ve anlık yenilenmesi tamamlandı.",
        "ip_adresi": None, "kaynak": "STAJ RAPORU",
    },
]


def puan_unvani(puan: int) -> str:
    """Raporda tanımlanan puan aralıklarını unvana dönüştürür."""

    if puan >= 1001:
        return "Platin"
    if puan >= 501:
        return "Altın"
    if puan >= 201:
        return "Gümüş"
    return "Bronz"


def sonraki_unvan(puan: int) -> dict:
    if puan < 201:
        return {"unvan": "Gümüş", "hedef": 201, "kalan": 201 - puan}
    if puan < 501:
        return {"unvan": "Altın", "hedef": 501, "kalan": 501 - puan}
    if puan < 1001:
        return {"unvan": "Platin", "hedef": 1001, "kalan": 1001 - puan}
    return {"unvan": "Platin", "hedef": 1001, "kalan": 0}


def _tarih(deger: Any) -> date | None:
    if not deger:
        return None
    if isinstance(deger, date):
        return deger
    return date.fromisoformat(str(deger)[:10])


def _suresi_dolanlari_isaretle(conn, bugun: date | None = None) -> None:
    bugun = bugun or date.today()
    conn.execute(
        """
        UPDATE kan_torbalari
        SET durum = 'SÜRESİ DOLDU'
        WHERE durum = 'AKTİF' AND son_kullanma_tarihi < ?
        """,
        (bugun.isoformat(),),
    )


def _son_on_degerlendirme(conn, bagisci_id: int) -> dict | None:
    satir = conn.execute(
        """
        SELECT id, dovme_piercing_mi, dovme_tarihi, ates_enfeksiyon_mi,
               antibiyotik_ilac_mi, ameliyat_transfuzyon_mi,
               hamilelik_emzirme_mi, aciklama, durum, kayit_tarihi
        FROM bagisci_on_degerlendirmeleri
        WHERE bagisci_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (bagisci_id,),
    ).fetchone()
    if not satir:
        return None
    sonuc = dict(satir)
    yanit_alanlari = (
        "dovme_piercing_mi", "ates_enfeksiyon_mi", "antibiyotik_ilac_mi",
        "ameliyat_transfuzyon_mi", "hamilelik_emzirme_mi",
    )
    sonuc["inceleme_gerekli"] = any(bool(sonuc[alan]) for alan in yanit_alanlari)
    return sonuc


def kan_gruplari_getir() -> list[dict]:
    with veritabani.baglanti_al() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id, grup_adi, kritik_esik FROM kan_gruplari ORDER BY id"
        ).fetchall()]


def bagis_uygunluk_kontrol_et(bagisci_id: int, bugun: date | None = None, conn=None) -> dict:
    """Cinsiyet bazlı bağış aralığını ve aktif sağlık engellerini açıklar."""

    bugun = bugun or date.today()
    sahip = conn is None
    if sahip:
        conn = veritabani.baglanti_al()
    try:
        bagisci = conn.execute(
            """
            SELECT b.*, kg.grup_adi
            FROM bagiscilar b
            JOIN kan_gruplari kg ON kg.id = b.kan_grubu_id
            WHERE b.id = ?
            """,
            (bagisci_id,),
        ).fetchone()
        if not bagisci:
            return {
                "uygun_mu": False,
                "durum": "KAYIT BULUNAMADI",
                "mesaj": "Bağışçı bulunamadı.",
                "nedenler": ["Sistemde bu bağışçıya ait kayıt yok."],
                "sonraki_uygun_tarih": None,
                "kalan_gun": None,
            }

        aralik = BAGIS_ARALIKLARI[bagisci["cinsiyet"]]
        son_bagis = _tarih(bagisci["son_bagis_tarihi"])
        aralik_tarihi = son_bagis + timedelta(days=aralik) if son_bagis else bugun
        sonraki_tarih = aralik_tarihi
        nedenler: list[str] = []
        kalici_engel = False

        if aralik_tarihi > bugun:
            nedenler.append(
                f"{bagisci['cinsiyet']} bağışçı için {aralik} günlük tam kan bağış aralığı dolmadı."
            )

        engel_satirlari = conn.execute(
            """
            SELECT id, tur, aciklama, baslangic_tarihi, bitis_tarihi, kalici_mi
            FROM saglik_engelleri
            WHERE bagisci_id = ? AND aktif_mi = 1
            ORDER BY kalici_mi DESC, bitis_tarihi DESC
            """,
            (bagisci_id,),
        ).fetchall()
        engeller = []
        for engel in engel_satirlari:
            bitis = _tarih(engel["bitis_tarihi"])
            aktif = bool(engel["kalici_mi"]) or bitis is None or bitis >= bugun
            engel_bilgisi = dict(engel)
            engel_bilgisi["aktif"] = aktif
            engeller.append(engel_bilgisi)
            if not aktif:
                continue
            if engel["kalici_mi"]:
                kalici_engel = True
                nedenler.append(f"Kalıcı engel: {engel['aciklama']}")
            else:
                nedenler.append(
                    f"Geçici engel: {engel['aciklama']} ({engel['bitis_tarihi']} tarihine kadar)."
                )
                if bitis and bitis > sonraki_tarih:
                    sonraki_tarih = bitis

        on_degerlendirme = _son_on_degerlendirme(conn, bagisci_id)
        if (
            on_degerlendirme
            and on_degerlendirme["durum"] == "BİLDİRİLDİ"
            and on_degerlendirme["inceleme_gerekli"]
        ):
            nedenler.append(
                "Bağışçı ön değerlendirme formunda hekim incelemesi gerektiren yanıtlar var."
            )

        uygun = not kalici_engel and sonraki_tarih <= bugun and not nedenler
        if uygun:
            mesaj = "Kayıtlı kurallara göre bağışa uygun; hekim onayı gereklidir."
            durum = "UYGUN"
            kalan_gun = 0
        elif kalici_engel:
            mesaj = "Kayıtlı kalıcı sağlık engeli nedeniyle uygun değil."
            durum = "UYGUN DEĞİL"
            kalan_gun = None
            sonraki_tarih = None
        else:
            kalan_gun = max((sonraki_tarih - bugun).days, 0)
            mesaj = f"Geçici bekleme sürüyor; en erken {sonraki_tarih.isoformat()} tarihinde yeniden değerlendirilebilir."
            durum = "BEKLEMEDE"

        return {
            "uygun_mu": uygun,
            "durum": durum,
            "mesaj": mesaj,
            "nedenler": nedenler,
            "son_bagis_tarihi": son_bagis.isoformat() if son_bagis else None,
            "bagis_araligi_gun": aralik,
            "sonraki_uygun_tarih": sonraki_tarih.isoformat() if sonraki_tarih else None,
            "kalan_gun": kalan_gun,
            "engeller": engeller,
            "on_degerlendirme": on_degerlendirme,
            "tibbi_uyari": TIBBI_UYARI,
        }
    finally:
        if sahip:
            conn.close()


def bagiscilari_getir(arama: str = "") -> list[dict]:
    parametre = f"%{arama.strip()}%"
    with veritabani.baglanti_al() as conn:
        satirlar = conn.execute(
            """
            SELECT b.id, b.bagisci_no, b.ad, b.soyad, b.cinsiyet, b.birim,
                   b.telefon, b.eposta, b.bildirim_izni, b.gece_aranir_mi,
                   b.son_bagis_tarihi, kg.id AS kan_grubu_id, kg.grup_adi,
                   (SELECT COUNT(*) FROM kan_torbalari kt
                    WHERE kt.bagisci_id = b.id AND kt.durum = 'AKTİF'
                      AND kt.son_kullanma_tarihi >= date('now')) AS aktif_unite_sayisi,
                   (SELECT COALESCE(SUM(ph.puan), 0) FROM puan_hareketleri ph
                    WHERE ph.bagisci_id = b.id) AS toplam_puan
            FROM bagiscilar b
            JOIN kan_gruplari kg ON kg.id = b.kan_grubu_id
            WHERE (? = '%%' OR b.bagisci_no LIKE ? OR b.ad LIKE ? OR b.soyad LIKE ?
                   OR b.telefon LIKE ? OR kg.grup_adi LIKE ?)
            ORDER BY b.ad, b.soyad
            """,
            (parametre, parametre, parametre, parametre, parametre, parametre),
        ).fetchall()
        sonuc = []
        for satir in satirlar:
            kayit = dict(satir)
            kayit["unvan"] = puan_unvani(kayit["toplam_puan"])
            kayit["on_degerlendirme"] = _son_on_degerlendirme(conn, satir["id"])
            kayit["uygunluk"] = bagis_uygunluk_kontrol_et(satir["id"], conn=conn)
            sonuc.append(kayit)
        return sonuc


def bagisci_on_degerlendirme_kaydet(
    bagisci_id: int, veri: dict, ip_adresi: str | None = None
) -> tuple[bool, dict | str]:
    """Bağışçının sağlık ön değerlendirmesini kaydeder; tıbbi onay yerine geçmez."""

    if veri.get("onay") is not True:
        return False, "Bilgilerin doğru olduğunu onaylamalısınız."

    alanlar = (
        "dovme_piercing_mi", "ates_enfeksiyon_mi", "antibiyotik_ilac_mi",
        "ameliyat_transfuzyon_mi", "hamilelik_emzirme_mi",
    )
    cevaplar = {alan: int(bool(veri.get(alan))) for alan in alanlar}
    dovme_tarihi = None
    if cevaplar["dovme_piercing_mi"]:
        if not veri.get("dovme_tarihi"):
            return False, "Dövme veya piercing tarihini yazmalısınız."
        try:
            dovme_tarihi = date.fromisoformat(str(veri["dovme_tarihi"])[:10])
        except ValueError:
            return False, "Dövme veya piercing tarihi geçerli değil."
        if dovme_tarihi > date.today():
            return False, "Dövme veya piercing tarihi gelecekte olamaz."

    try:
        with veritabani.baglanti_al() as conn:
            if not conn.execute("SELECT 1 FROM bagiscilar WHERE id = ?", (bagisci_id,)).fetchone():
                return False, "Bağışçı kaydı bulunamadı."
            cursor = conn.execute(
                """
                INSERT INTO bagisci_on_degerlendirmeleri
                    (bagisci_id, dovme_piercing_mi, dovme_tarihi,
                     ates_enfeksiyon_mi, antibiyotik_ilac_mi,
                     ameliyat_transfuzyon_mi, hamilelik_emzirme_mi, aciklama)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bagisci_id, cevaplar["dovme_piercing_mi"],
                    dovme_tarihi.isoformat() if dovme_tarihi else None,
                    cevaplar["ates_enfeksiyon_mi"], cevaplar["antibiyotik_ilac_mi"],
                    cevaplar["ameliyat_transfuzyon_mi"],
                    cevaplar["hamilelik_emzirme_mi"],
                    str(veri.get("aciklama") or "").strip() or None,
                ),
            )
            if dovme_tarihi:
                bitis_tarihi = dovme_tarihi + timedelta(days=365)
                if bitis_tarihi >= date.today():
                    mevcut = conn.execute(
                        """
                        SELECT 1 FROM saglik_engelleri
                        WHERE bagisci_id = ? AND tur = 'Dövme/Piercing'
                          AND baslangic_tarihi = ? AND aktif_mi = 1
                        """,
                        (bagisci_id, dovme_tarihi.isoformat()),
                    ).fetchone()
                    if not mevcut:
                        conn.execute(
                            """
                            INSERT INTO saglik_engelleri
                                (bagisci_id, tur, aciklama, baslangic_tarihi,
                                 bitis_tarihi, kalici_mi)
                            VALUES (?, 'Dövme/Piercing',
                                    'Son 12 ay içinde dövme veya piercing bildirimi', ?, ?, 0)
                            """,
                            (bagisci_id, dovme_tarihi.isoformat(), bitis_tarihi.isoformat()),
                        )
            inceleme_sayisi = sum(cevaplar.values())
            audit.kaydet(
                None, "ÖN_DEĞERLENDİRME",
                f"Bağışçı sağlık ön değerlendirme formunu kaydetti; "
                f"{inceleme_sayisi} yanıt hekim incelemesi gerektiriyor.",
                ip_adresi, conn,
            )
        return True, {
            "id": cursor.lastrowid,
            "inceleme_gerekli": bool(inceleme_sayisi),
            "mesaj": (
                "Form kaydedildi; hekim değerlendirmesi gereken yanıtlar var."
                if inceleme_sayisi else "Form kaydedildi; son karar muayene ve hekim onayıyla verilir."
            ),
        }
    except Exception as exc:
        return False, str(exc)


def bagisci_ekle(veri: dict) -> tuple[bool, dict | str]:
    zorunlu = ["ad", "soyad", "cinsiyet", "birim", "telefon", "kan_grubu_id"]
    eksikler = [alan for alan in zorunlu if not veri.get(alan)]
    if eksikler:
        return False, f"Zorunlu alanlar eksik: {', '.join(eksikler)}"
    if veri["cinsiyet"] not in BAGIS_ARALIKLARI:
        return False, "Cinsiyet Kadın veya Erkek olarak seçilmelidir."
    try:
        with veritabani.baglanti_al() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bagiscilar
                    (kan_grubu_id, ad, soyad, cinsiyet, birim, telefon, eposta,
                     bildirim_izni, gece_aranir_mi, son_bagis_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(veri["kan_grubu_id"]), veri["ad"].strip(), veri["soyad"].strip(),
                    veri["cinsiyet"], veri["birim"].strip(), veri["telefon"].strip(),
                    (veri.get("eposta") or "").strip() or None,
                    int(bool(veri.get("bildirim_izni", True))),
                    int(bool(veri.get("gece_aranir_mi", False))),
                    veri.get("son_bagis_tarihi") or None,
                ),
            )
            bagisci_id = cursor.lastrowid
            bagisci_no = f"KB-{date.today().year}-{bagisci_id:04d}"
            conn.execute("UPDATE bagiscilar SET bagisci_no = ? WHERE id = ?", (bagisci_no, bagisci_id))
            audit.kaydet(
                veri.get("api_kullanici_id"), "BAĞIŞÇI_KAYDI",
                f"{bagisci_no} numaralı bağışçı kaydı oluşturuldu.", veri.get("ip_adresi"), conn,
            )
        return True, {"id": bagisci_id, "bagisci_no": bagisci_no}
    except Exception as exc:
        mesaj = "Bu telefon numarasıyla kayıtlı bir bağışçı zaten var." if "UNIQUE" in str(exc) else str(exc)
        return False, mesaj


def saglik_engeli_ekle(bagisci_id: int, veri: dict, api_kullanici_id=None, ip_adresi=None):
    if not veri.get("tur") or not veri.get("aciklama"):
        return False, "Engel türü ve açıklama zorunludur."
    try:
        with veritabani.baglanti_al() as conn:
            conn.execute(
                """
                INSERT INTO saglik_engelleri
                    (bagisci_id, tur, aciklama, baslangic_tarihi, bitis_tarihi, kalici_mi)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bagisci_id, veri["tur"], veri["aciklama"], veri.get("baslangic_tarihi"),
                    veri.get("bitis_tarihi"), int(bool(veri.get("kalici_mi"))),
                ),
            )
            audit.kaydet(
                api_kullanici_id, "SAĞLIK_ENGELİ",
                f"{bagisci_id} numaralı bağışçı için {veri['tur']} kaydı eklendi.", ip_adresi, conn,
            )
        return True, "Sağlık engeli kaydedildi."
    except Exception as exc:
        return False, str(exc)


def stok_durumu_getir() -> list[dict]:
    with veritabani.baglanti_al() as conn:
        _suresi_dolanlari_isaretle(conn)
        satirlar = conn.execute(
            """
            SELECT kg.id, kg.grup_adi, kg.kritik_esik,
                   COUNT(CASE WHEN kt.durum = 'AKTİF' AND kt.son_kullanma_tarihi >= date('now') THEN 1 END)
                       AS unite_sayisi,
                   COUNT(DISTINCT CASE WHEN kt.durum = 'AKTİF' AND kt.son_kullanma_tarihi >= date('now')
                                       THEN kt.bagisci_id END) AS bagisci_sayisi,
                   COUNT(CASE WHEN kt.durum = 'AKTİF' AND kt.son_kullanma_tarihi BETWEEN date('now') AND date('now', '+7 day')
                              THEN 1 END) AS yedi_gunde_dolacak
            FROM kan_gruplari kg
            LEFT JOIN kan_torbalari kt ON kt.kan_grubu_id = kg.id
            GROUP BY kg.id
            ORDER BY kg.id
            """
        ).fetchall()
    sonuc = []
    for satir in satirlar:
        kayit = dict(satir)
        if kayit["unite_sayisi"] <= kayit["kritik_esik"]:
            kayit["durum"] = "KRİTİK"
        elif kayit["unite_sayisi"] <= kayit["kritik_esik"] + 2:
            kayit["durum"] = "RİSKLİ"
        else:
            kayit["durum"] = "YETERLİ"
        sonuc.append(kayit)
    return sonuc


def envanter_getir(kan_grubu: str = "", bilesen_turu: str = "", durum: str = "") -> list[dict]:
    with veritabani.baglanti_al() as conn:
        _suresi_dolanlari_isaretle(conn)
        sorgu = """
            SELECT kt.id, kt.unite_kodu, b.bagisci_no, b.ad || ' ' || b.soyad AS bagisci,
                   kg.grup_adi, kt.bilesen_turu, kt.bagis_tarihi, kt.son_kullanma_tarihi,
                   CAST(julianday(kt.son_kullanma_tarihi) - julianday(date('now')) AS INTEGER) AS kalan_gun,
                   kt.saklama_konumu, kt.durum
            FROM kan_torbalari kt
            JOIN bagiscilar b ON b.id = kt.bagisci_id
            JOIN kan_gruplari kg ON kg.id = kt.kan_grubu_id
            WHERE (? = '' OR kg.grup_adi = ?)
              AND (? = '' OR kt.bilesen_turu = ?)
              AND (? = '' OR kt.durum = ?)
            ORDER BY CASE kt.durum WHEN 'AKTİF' THEN 0 ELSE 1 END,
                     kt.son_kullanma_tarihi, kt.unite_kodu
        """
        satirlar = conn.execute(
            sorgu, (kan_grubu, kan_grubu, bilesen_turu, bilesen_turu, durum, durum)
        ).fetchall()
    return [dict(row) for row in satirlar]


def bagis_kaydet(
    bagisci_id: int,
    bilesen_turu: str = "Tam Kan",
    adet: int = 1,
    api_kullanici_id=None,
    ip_adresi=None,
):
    if bilesen_turu not in URUN_KURALLARI:
        return False, "Geçersiz kan bileşeni."
    if adet < 1 or adet > 5:
        return False, "Ünite sayısı 1 ile 5 arasında olmalıdır."
    with veritabani.baglanti_al() as conn:
        uygunluk = bagis_uygunluk_kontrol_et(bagisci_id, conn=conn)
        if not uygunluk["uygun_mu"]:
            return False, uygunluk["mesaj"]
        bagisci = conn.execute(
            """
            SELECT b.kan_grubu_id, b.bagisci_no, kg.grup_adi, kg.kritik_esik
            FROM bagiscilar b
            JOIN kan_gruplari kg ON kg.id = b.kan_grubu_id
            WHERE b.id = ?
            """,
            (bagisci_id,),
        ).fetchone()
        if not bagisci:
            return False, "Bağışçı bulunamadı."

        bagis_oncesi_stok = conn.execute(
            """
            SELECT COUNT(*) FROM kan_torbalari
            WHERE kan_grubu_id = ? AND durum = 'AKTİF'
              AND son_kullanma_tarihi >= date('now')
            """,
            (bagisci["kan_grubu_id"],),
        ).fetchone()[0]
        kritik_bagis = bagis_oncesi_stok <= bagisci["kritik_esik"]

        bugun = date.today()
        son_kullanma = bugun + timedelta(days=URUN_KURALLARI[bilesen_turu]["raf_omru_gun"])
        cursor = conn.execute(
            """
            INSERT INTO bagislar
                (bagisci_id, kan_grubu_id, bilesen_turu, unite_sayisi, bagis_tarihi, kaydeden_api_kullanici_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (bagisci_id, bagisci["kan_grubu_id"], bilesen_turu, adet, bugun.isoformat(), api_kullanici_id),
        )
        bagis_id = cursor.lastrowid
        for sira in range(1, adet + 1):
            torba = conn.execute(
                """
                INSERT INTO kan_torbalari
                    (bagis_id, bagisci_id, kan_grubu_id, bilesen_turu, bagis_tarihi,
                     son_kullanma_tarihi, saklama_konumu)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bagis_id, bagisci_id, bagisci["kan_grubu_id"], bilesen_turu,
                    bugun.isoformat(), son_kullanma.isoformat(), "Soğuk Oda A" if bilesen_turu != "Trombosit" else "Trombosit Dolabı",
                ),
            )
            unite_kodu = f"KT-{bugun:%Y%m%d}-{torba.lastrowid:05d}-{sira}"
            conn.execute("UPDATE kan_torbalari SET unite_kodu = ? WHERE id = ?", (unite_kodu, torba.lastrowid))
        conn.execute(
            "UPDATE bagiscilar SET son_bagis_tarihi = ? WHERE id = ?",
            (bugun.isoformat(), bagisci_id),
        )
        conn.execute(
            """
            INSERT INTO puan_hareketleri (bagisci_id, bagis_id, puan, neden, tarih)
            VALUES (?, ?, ?, 'Standart kan bağışı', ?)
            """,
            (bagisci_id, bagis_id, STANDART_BAGIS_PUANI, datetime.now().isoformat(timespec="seconds")),
        )
        kazanilan_puan = STANDART_BAGIS_PUANI
        if kritik_bagis:
            conn.execute(
                """
                INSERT INTO puan_hareketleri (bagisci_id, bagis_id, puan, neden, tarih)
                VALUES (?, ?, ?, 'Kritik stok kan grubu bonusu', ?)
                """,
                (bagisci_id, bagis_id, KRITIK_STOK_BONUSU, datetime.now().isoformat(timespec="seconds")),
            )
            kazanilan_puan += KRITIK_STOK_BONUSU
        audit.kaydet(
            api_kullanici_id, "KAN_BAĞIŞI",
            f"{bagisci['bagisci_no']} bağışçısından {adet} ünite {bilesen_turu} kabul edildi; "
            f"{kazanilan_puan} puan tanımlandı.",
            ip_adresi, conn,
        )
    bonus_metni = " Kritik stok nedeniyle +50 bonus eklendi." if kritik_bagis else ""
    return True, (
        f"{adet} ünite kaydedildi; +{kazanilan_puan} puan verildi.{bonus_metni} "
        "Kan grubu bağışçı kaydından otomatik alındı."
    )


def kan_cikis_yap(
    kan_grubu_adi: str,
    bilesen_turu: str,
    adet: int,
    talep_eden_birim: str,
    api_kullanici_id=None,
    ip_adresi=None,
):
    if adet < 1:
        return False, "Adet en az 1 olmalıdır."
    with veritabani.baglanti_al() as conn:
        _suresi_dolanlari_isaretle(conn)
        kan_grubu = conn.execute(
            "SELECT id FROM kan_gruplari WHERE grup_adi = ?", (kan_grubu_adi,)
        ).fetchone()
        if not kan_grubu:
            return False, "Kan grubu bulunamadı."
        torbalar = conn.execute(
            """
            SELECT id, unite_kodu FROM kan_torbalari
            WHERE kan_grubu_id = ? AND bilesen_turu = ? AND durum = 'AKTİF'
              AND son_kullanma_tarihi >= date('now')
            ORDER BY son_kullanma_tarihi, bagis_tarihi, id
            LIMIT ?
            """,
            (kan_grubu["id"], bilesen_turu, adet),
        ).fetchall()
        if len(torbalar) < adet:
            return False, f"Yetersiz stok. Kullanılabilir {len(torbalar)} ünite var, {adet} istendi."
        bugun = date.today().isoformat()
        conn.executemany(
            "UPDATE kan_torbalari SET durum = 'KULLANILDI', kullanilma_tarihi = ? WHERE id = ?",
            [(bugun, torba["id"]) for torba in torbalar],
        )
        conn.execute(
            """
            INSERT INTO kan_cikislari
                (kan_grubu_id, bilesen_turu, adet, talep_eden_birim, kaydeden_api_kullanici_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (kan_grubu["id"], bilesen_turu, adet, talep_eden_birim.strip(), api_kullanici_id),
        )
        kodlar = ", ".join(torba["unite_kodu"] for torba in torbalar)
        audit.kaydet(
            api_kullanici_id, "KAN_ÇIKIŞI",
            f"{talep_eden_birim}: {adet} ünite {kan_grubu_adi} {bilesen_turu}; FIFO kodları: {kodlar}",
            ip_adresi, conn,
        )
    return True, f"{adet} ünite FIFO sırasıyla stoktan düşüldü."


def ozet_getir() -> dict:
    stoklar = stok_durumu_getir()
    bagiscilar = bagiscilari_getir()
    with veritabani.baglanti_al() as conn:
        _suresi_dolanlari_isaretle(conn)
        yedi_gun = conn.execute(
            """
            SELECT COUNT(*) FROM kan_torbalari
            WHERE durum = 'AKTİF' AND son_kullanma_tarihi BETWEEN date('now') AND date('now', '+7 day')
            """
        ).fetchone()[0]
    return {
        "toplam_aktif_unite": sum(item["unite_sayisi"] for item in stoklar),
        "kritik_kan_grubu": sum(1 for item in stoklar if item["durum"] == "KRİTİK"),
        "yedi_gunde_dolacak": yedi_gun,
        "uygun_bagisci": sum(1 for item in bagiscilar if item["uygunluk"]["uygun_mu"]),
        "toplam_bagisci": len(bagiscilar),
    }


def acil_cagri_adaylari_getir(kan_grubu_adi: str, limit: int = 20) -> list[dict]:
    """Bildirim izni açık ve bağışa uygun kişileri SQL sırasıyla getirir.

    Rapordaki mantığa uygun olarak son bağış tarihi en eski olanlar, hiç bağış
    yapmayanlar ve ardından puanı yüksek olanlar öne alınır. Sağlık uygunluğu
    ayrıca açıklanabilir kural motoruyla doğrulanır.
    """

    limit = min(max(int(limit), 1), 100)
    with veritabani.baglanti_al() as conn:
        satirlar = conn.execute(
            """
            SELECT b.id, b.bagisci_no, b.ad, b.soyad, b.telefon, b.eposta,
                   b.cinsiyet, b.son_bagis_tarihi, b.gece_aranir_mi,
                   kg.grup_adi,
                   CAST(julianday(date('now')) - julianday(b.son_bagis_tarihi) AS INTEGER)
                       AS son_bagistan_gecen_gun,
                   (SELECT COALESCE(SUM(ph.puan), 0) FROM puan_hareketleri ph
                    WHERE ph.bagisci_id = b.id) AS toplam_puan
            FROM bagiscilar b
            JOIN kan_gruplari kg ON kg.id = b.kan_grubu_id
            WHERE kg.grup_adi = ? AND b.bildirim_izni = 1
            ORDER BY CASE WHEN b.son_bagis_tarihi IS NULL THEN 0 ELSE 1 END,
                     b.son_bagis_tarihi ASC, toplam_puan DESC, b.id
            """,
            (kan_grubu_adi,),
        ).fetchall()
        sonuc = []
        for satir in satirlar:
            uygunluk = bagis_uygunluk_kontrol_et(satir["id"], conn=conn)
            if not uygunluk["uygun_mu"]:
                continue
            kayit = dict(satir)
            kayit["unvan"] = puan_unvani(kayit["toplam_puan"])
            kayit["uygunluk"] = uygunluk
            kayit["sira"] = len(sonuc) + 1
            sonuc.append(kayit)
            if len(sonuc) >= limit:
                break
        return sonuc


def eposta_ayar_durumu() -> dict:
    """Arayüz için parola içermeyen SMTP durumunu döndürür."""

    return bildirim.smtp_ayar_durumu()


def _acil_cagri_epostalarini_gonder(
    cagri_id: int,
    kan_grubu_adi: str,
    aciklama: str,
    adaylar: list[dict],
    api_kullanici_id=None,
    ip_adresi=None,
) -> dict:
    konu, icerik = bildirim.acil_kan_ihtiyaci_bildirimi_olustur(
        kan_grubu_adi, aciklama
    )
    gonderildi = 0
    basarisiz = 0
    epostasi_yok = 0
    sonuclar = []

    for aday in adaylar:
        alici = (aday.get("eposta") or "").strip()
        if not alici:
            epostasi_yok += 1
            continue
        basarili, mesaj = bildirim.eposta_gonder(alici, konu, icerik)
        gonderildi += int(basarili)
        basarisiz += int(not basarili)
        sonuclar.append({
            "bagisci_id": aday["id"],
            "alici": alici,
            "durum": "GÖNDERİLDİ" if basarili else "BAŞARISIZ",
            "mesaj": mesaj,
        })

    with veritabani.baglanti_al() as conn:
        for sonuc in sonuclar:
            conn.execute(
                """
                INSERT INTO eposta_gonderimleri
                    (acil_cagri_id, bagisci_id, alici_eposta, konu, durum, hata_mesaji)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cagri_id,
                    sonuc["bagisci_id"],
                    sonuc["alici"],
                    konu,
                    sonuc["durum"],
                    None if sonuc["durum"] == "GÖNDERİLDİ" else sonuc["mesaj"],
                ),
            )
        audit.kaydet(
            api_kullanici_id,
            "EPOSTA_BİLDİRİMİ",
            f"{kan_grubu_adi} acil çağrısı: {gonderildi} e-posta gönderildi, "
            f"{basarisiz} başarısız, {epostasi_yok} adreste e-posta yok.",
            ip_adresi,
            conn,
        )

    return {
        "gonderildi": gonderildi,
        "basarisiz": basarisiz,
        "epostasi_yok": epostasi_yok,
        "toplam_aday": len(adaylar),
    }


def acil_cagri_olustur(
    kan_grubu_adi: str,
    aciklama: str,
    limit: int = 20,
    api_kullanici_id=None,
    ip_adresi=None,
    eposta_gonderilsin: bool = False,
):
    if eposta_gonderilsin and not bildirim.smtp_ayar_durumu()["yapilandirildi"]:
        return False, (
            "E-posta gönderimi için SMTP ayarları eksik. Proje kökündeki .env "
            "dosyasını .env.example örneğine göre doldurun."
        )
    adaylar = acil_cagri_adaylari_getir(kan_grubu_adi, limit)
    with veritabani.baglanti_al() as conn:
        grup = conn.execute(
            "SELECT id FROM kan_gruplari WHERE grup_adi = ?", (kan_grubu_adi,)
        ).fetchone()
        if not grup:
            return False, "Kan grubu bulunamadı."
        cursor = conn.execute(
            """
            INSERT INTO acil_cagrilar
                (kan_grubu_id, aciklama, aday_sayisi, olusturan_api_kullanici_id)
            VALUES (?, ?, ?, ?)
            """,
            (grup["id"], aciklama.strip(), len(adaylar), api_kullanici_id),
        )
        audit.kaydet(
            api_kullanici_id,
            "ACİL_ÇAĞRI",
            f"{kan_grubu_adi} için {len(adaylar)} uygun ve bildirim izinli bağışçı sıralandı.",
            ip_adresi,
            conn,
        )
        cagri_id = cursor.lastrowid

    eposta_ozeti = None
    if eposta_gonderilsin:
        eposta_ozeti = _acil_cagri_epostalarini_gonder(
            cagri_id,
            kan_grubu_adi,
            aciklama.strip(),
            adaylar,
            api_kullanici_id,
            ip_adresi,
        )
        mesaj = (
            f"Çağrı kaydedildi; {eposta_ozeti['gonderildi']} e-posta gönderildi, "
            f"{eposta_ozeti['basarisiz']} gönderim başarısız oldu."
        )
    else:
        mesaj = "Öncelikli aday listesi ve acil çağrı kaydı oluşturuldu."

    return True, {
        "cagri_id": cagri_id,
        "kan_grubu": kan_grubu_adi,
        "aciklama": aciklama.strip(),
        "adaylar": adaylar,
        "eposta_ozeti": eposta_ozeti,
        "mesaj": mesaj,
    }


def eposta_gonderimleri_getir(limit: int = 50) -> list[dict]:
    with veritabani.baglanti_al() as conn:
        satirlar = conn.execute(
            """
            SELECT eg.id, eg.alici_eposta, eg.konu, eg.durum, eg.hata_mesaji,
                   eg.gonderim_tarihi, b.bagisci_no, b.ad || ' ' || b.soyad AS bagisci,
                   kg.grup_adi
            FROM eposta_gonderimleri eg
            JOIN bagiscilar b ON b.id = eg.bagisci_id
            JOIN acil_cagrilar ac ON ac.id = eg.acil_cagri_id
            JOIN kan_gruplari kg ON kg.id = ac.kan_grubu_id
            ORDER BY eg.gonderim_tarihi DESC, eg.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(satir) for satir in satirlar]


def bagisci_panel_ozeti(bagisci_id: int) -> dict | None:
    with veritabani.baglanti_al() as conn:
        profil = conn.execute(
            """
            SELECT b.id, b.bagisci_no, b.ad, b.soyad, b.cinsiyet, b.birim,
                   b.telefon, b.eposta, b.bildirim_izni, b.son_bagis_tarihi,
                   kg.grup_adi,
                   (SELECT COALESCE(SUM(ph.puan), 0) FROM puan_hareketleri ph
                    WHERE ph.bagisci_id = b.id) AS toplam_puan
            FROM bagiscilar b
            JOIN kan_gruplari kg ON kg.id = b.kan_grubu_id
            WHERE b.id = ?
            """,
            (bagisci_id,),
        ).fetchone()
        if not profil:
            return None

        bagislar = conn.execute(
            """
            SELECT bg.id, bg.bagis_tarihi, bg.bilesen_turu, bg.unite_sayisi,
                   (SELECT COALESCE(SUM(ph.puan), 0) FROM puan_hareketleri ph
                    WHERE ph.bagis_id = bg.id) AS kazanilan_puan
            FROM bagislar bg
            WHERE bg.bagisci_id = ?
            ORDER BY bg.bagis_tarihi DESC, bg.id DESC
            LIMIT 30
            """,
            (bagisci_id,),
        ).fetchall()
        puan_hareketleri = conn.execute(
            """
            SELECT id, puan, neden, tarih FROM puan_hareketleri
            WHERE bagisci_id = ? ORDER BY tarih DESC, id DESC LIMIT 30
            """,
            (bagisci_id,),
        ).fetchall()
        cagrilar = conn.execute(
            """
            SELECT ac.id, ac.aciklama, ac.olusturma_tarihi, ac.durum, kg.grup_adi
            FROM acil_cagrilar ac
            JOIN kan_gruplari kg ON kg.id = ac.kan_grubu_id
            WHERE kg.grup_adi = ? AND ac.durum = 'HAZIR'
            ORDER BY ac.olusturma_tarihi DESC LIMIT 10
            """,
            (profil["grup_adi"],),
        ).fetchall()

        profil_dict = dict(profil)
        profil_dict["unvan"] = puan_unvani(profil_dict["toplam_puan"])
        profil_dict["sonraki_unvan"] = sonraki_unvan(profil_dict["toplam_puan"])
        return {
            "profil": profil_dict,
            "uygunluk": bagis_uygunluk_kontrol_et(bagisci_id, conn=conn),
            "on_degerlendirme": _son_on_degerlendirme(conn, bagisci_id),
            "bagislar": [dict(row) for row in bagislar],
            "puan_hareketleri": [dict(row) for row in puan_hareketleri],
            "acil_cagrilar": [dict(row) for row in cagrilar],
            "puan_kurallari": {
                "standart_bagis": STANDART_BAGIS_PUANI,
                "kritik_stok_bonusu": KRITIK_STOK_BONUSU,
                "unvanlar": ["Bronz 0–200", "Gümüş 201–500", "Altın 501–1000", "Platin 1001+"],
            },
            "tibbi_uyari": TIBBI_UYARI,
        }


def bagisci_bildirim_izni_guncelle(bagisci_id: int, izin: bool) -> None:
    with veritabani.baglanti_al() as conn:
        conn.execute(
            "UPDATE bagiscilar SET bildirim_izni = ? WHERE id = ?",
            (int(bool(izin)), bagisci_id),
        )


def kurallar_getir() -> dict:
    return {
        "bagis_araliklari": [
            {"cinsiyet": cinsiyet, "gun": gun} for cinsiyet, gun in BAGIS_ARALIKLARI.items()
        ],
        "saglik_kurallari": [
            {
                "kural": "Dövme",
                "bekleme": "12 ay geçici ret",
                "sistemdeki_uygulama": "Başlangıç ve bitiş tarihi sağlık engeli kaydında tutulur.",
            },
            {
                "kural": "Kalıcı sağlık engeli",
                "bekleme": "Süresiz",
                "sistemdeki_uygulama": "Bağış kaydı sunucu tarafında reddedilir.",
            },
        ],
        "urun_kurallari": [
            {"urun": urun, **bilgi} for urun, bilgi in URUN_KURALLARI.items()
        ],
        "puan_kurallari": {
            "standart_bagis": STANDART_BAGIS_PUANI,
            "kritik_stok_bonusu": KRITIK_STOK_BONUSU,
            "unvanlar": ["Bronz 0–200", "Gümüş 201–500", "Altın 501–1000", "Platin 1001+"],
        },
        "tibbi_uyari": TIBBI_UYARI,
    }


def islem_gecmisi_getir(limit: int = 50) -> list[dict]:
    canli_kayitlar = [
        {**kayit, "kaynak": "CANLI SİSTEM"}
        for kayit in audit.gecmis_listele(limit)
    ]
    return sorted(
        [*canli_kayitlar, *STAJ_GELISTIRME_KAYITLARI],
        key=lambda kayit: kayit["tarih"],
        reverse=True,
    )
