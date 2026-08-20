# Akıllı Hastane Kan Bankası ve Acil Müdahale Platformu

Hastane kan bankası stok yönetimi, bağışçı eşleştirme, acil çağrı
önceliklendirme ve bildirim gönderimi için geliştirilmiş bir REST API.

## Özellikler

- **Stok yönetimi:** Kritik stok uyarısı, tüketim hızına göre dinamik
  eşik hesaplama, talep tahmini (hareketli ortalama), son kullanma
  tarihi risk analizi
- **Çapraz kan uyumluluğu:** Tıbbi uyumluluk kurallarına göre alternatif
  kan grubu önerisi
- **Bağışçı yönetimi:** Bağış uygunluk kontrolü (90/120 gün kuralı,
  sağlık engelleri), puan/rozet sistemi, ağırlıklı öncelik skoruyla
  acil çağrı listesi
- **Kimlik doğrulama:** Token tabanlı giriş, rol bazlı erişim
  kısıtlaması (admin/personel), giriş denemesi sınırlaması (rate limiting)
- **İşlem geçmişi (audit trail):** Kim, ne zaman, hangi işlemi yaptı kaydı
- **Bildirim:** Bağışçılara e-posta ile acil kan ihtiyacı bildirimi
- **API dokümantasyonu:** `/docs` adresinde interaktif Swagger arayüzü
- **Test paketi:** pytest ile 29+ otomatik test, GitHub Actions ile
  her push'ta otomatik çalıştırma (CI/CD)

## Teknoloji

Python 3.12+, Flask, SQLite, pytest, GitHub Actions

## Kurulum

```bash
# 1. Bağımlılıkları kur
python -m pip install -r requirements.txt

# 2. Veritabanını oluştur
python veritabani.py

# 3. Örnek/test verisini yükle
python veriler.py

# 4. İlk kullanıcı hesabını (admin) oluştur
python kullanici_olustur.py

# 5. E-posta bildirimi kullanacaksan .env dosyasını hazırla
#    (.env.example'ı kopyalayıp .env adıyla kaydet, gerçek bilgilerini gir)

# 6. Sunucuyu başlat
python app.py
```

Sunucu ayağa kalkınca:
- API: `http://127.0.0.1:5000`
- İnteraktif dokümantasyon: `http://127.0.0.1:5000/docs`

## Testleri çalıştırma

```bash
python -m pytest -v
```

## Kimlik doğrulama nasıl kullanılır

1. `/api/auth/giris` endpoint'ine `kullanici_adi` ve `sifre` göndererek
   giriş yap, dönen `token`'ı kopyala.
2. Diğer tüm endpoint'lerde (`/api/health` ve `/api/auth/giris` hariç)
   `Authorization: Bearer <token>` header'ını gönder.
3. Bazı endpoint'ler (örn. `/api/bagiscilar/uygunluk/<id>`) sadece
   `admin` rolüne açıktır - `personel` rolüyle 403 alırsın.

## Proje yapısı

```
veritabani.py       -> Veritabanı şeması (tabloları oluşturur)
servisler.py         -> Saf iş mantığı (kan bankası kuralları)
auth.py               -> Kimlik doğrulama (giriş, token)
audit.py               -> İşlem geçmişi kaydı
bildirim.py             -> E-posta gönderimi
openapi.py                -> Swagger/OpenAPI şeması
app.py                     -> Flask giriş noktası (HTTP endpoint'leri)
veriler.py                  -> Örnek/test verisi ekleme scripti
kullanici_olustur.py         -> Yeni API kullanıcısı oluşturma scripti
token_temizle.py               -> Süresi dolmuş oturumları temizleme scripti
tests/                           -> pytest testleri
.github/workflows/tests.yml       -> CI/CD (otomatik test çalıştırma)
bilinen_sinirlamalar.md            -> Üretime geçiş için bilinen eksikler
```

## Bilinen sınırlamalar

Prototip/staj aşamasındaki bilinçli tasarım kararları ve üretime geçiş
için yapılması gerekenler `bilinen_sinirlamalar.md` dosyasında.