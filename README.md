# Kan Bankası Yönetici Paneli

Flask + SQLite API ve React arayüzünden oluşan kan bankası yönetim sistemidir.
Yönetici paneli; bağışçı kayıtlarını eşleştirir, uygunluk kurallarını uygular,
kan stoklarını tek tek ünite bazında izletir, acil çağrı e-postaları gönderir ve
kritik işlemleri denetim kaydına yazar. Ayrı bağışçı paneli ise kişinin yalnızca
kendi bağış, uygunluk, puan, unvan ve acil çağrı bilgilerini gösterir.

> **Tıbbi süreç:** Bağış uygunluğu; bağışçı sorgulama formu, muayene ve yetkili
> hekim onayı tamamlandıktan sonra kesinleşir. Dövme ve diğer sağlık yanıtları
> bağışçının uygunluğunu etkiler; kanın stokta kalma süresi ise bağışçıya göre
> değil, ürün türüne göre hesaplanır: Tam Kan 35, Eritrosit 42, Trombosit 5 gün.

## Panelde neler var?

- **Genel Bakış:** Sekiz kan grubunun stok, kritik seviye ve son kullanma riski.
- **Bağışçılar:** Otomatik `KB-YIL-SIRA` numarası, benzersiz telefon kontrolü,
  cinsiyete göre 90/120 gün aralığı, dövme ve diğer geçici/kalıcı engeller.
- **Ünite Envanteri:** Aynı bağışçıya ait aynı tarih, bileşen ve konumdaki
  üniteler tek stok satırında gruplanır; tekil ünite kodları kaybolmadan
  birlikte gösterilir.
- **Stok Çıkışı:** En yakın son kullanma tarihli uygun üniteden FIFO çıkış.
- **Bağışçı Puanlama:** Standart bağışa +100, kritik stok grubuna +50 bonus;
  Bronz, Gümüş, Altın ve Platin unvanları.
- **Öncelikli Acil Çağrı:** Bildirim izni açık ve bağışa uygun kişileri son
  bağıştan geçen süreye göre SQL tabanlı sıralama; isteğe bağlı gerçek SMTP
  e-postası ve gönderim geçmişi.
- **Bağışçı Paneli:** Kişisel uygunluk tarihi, puan/unvan, bağış geçmişi,
  bildirim tercihi, aktif çağrılar ve dövme/piercing, enfeksiyon, ilaç,
  ameliyat/kan nakli gibi soruları içeren sağlık ön değerlendirme formu.
- **Yeni Bağışçı Kaydı:** Bağışçı girişindeki kayıt formu, benzersiz kullanıcı
  adı ve telefon kontrolüyle bağışçı numarasını otomatik üretir.
- **Kurallar ve Denetim:** Uygulanan kurallar ile canlı işlemleri ve raporda
  belgelendirilen geliştirme kayıtlarını tek tabloda gösteren işlem geçmişi.
  `CANLI SİSTEM` ve `STAJ RAPORU` kaynak etiketleri kayıt türünü açıkça ayırır.

Kimden ne kadar kan geldiği, **Bağışçılar** ekranındaki toplam bağış bilgisi ve
**Ünite Envanteri** ekranındaki bağışçı–ünite eşleştirmesiyle görülebilir.

## Hızlı kurulum

Gerekenler: Python 3.12+ ve güncel Node.js.

### Windows: tek tıkla başlatma

ZIP'i çıkardıktan sonra proje klasöründeki `WINDOWS_BASLAT.bat` dosyasına
çift tıklayın. İlk çalıştırmada bağımlılıkların kurulması biraz sürebilir. API
ve arayüz iki ayrı komut penceresinde açılır; ardından tarayıcı otomatik olarak
`http://localhost:5173` adresine gider. İki siyah pencereyi kullanım boyunca
açık bırakın.

### 1. API

Proje klasöründe:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python veriler.py
python app.py
```

API `http://127.0.0.1:5050` adresinde çalışır. `python veriler.py`, örnek
veritabanını güvenli biçimde yeniden oluşturur.

### 2. Arayüz

İkinci bir terminalde:

```bash
cd frontend
npm install
npm run dev
```

Tarayıcıda `http://127.0.0.1:5173` adresini açın.

İlk kurulum girişleri:

- Yönetici: `admin` / `Admin123!`
- Bağışçı: `adem` / `Bagisci123!`

## Acil çağrı e-postalarını etkinleştirme

1. Proje kökündeki `.env.example` dosyasını `.env` adıyla kopyalayın.
2. `SMTP_KULLANICI` alanına gönderici e-posta adresini yazın.
3. `SMTP_SIFRE` alanına e-posta sağlayıcısının uygulama şifresini yazın.
4. Uygulamayı yeniden başlatın. **Puan ve Acil Çağrı** ekranındaki kırmızı
   **Kaydet ve e-posta gönder** düğmesi çağrıyı kaydeder ve uygun adaylara
   e-posta gönderir. SMTP bilgileri eksikse sunucu, güvenli biçimde açıklayıcı
   hata döndürür; parola arayüzde gösterilmez.

Gmail hesabında normal hesap şifresi yerine iki adımlı doğrulama sonrasında
oluşturulan Uygulama Şifresi kullanılmalıdır. `.env` dosyası ZIP'e veya kaynak
kontrolüne eklenmez.

Başlangıç verilerindeki `example.test` adresleri yalnızca örnektir ve gerçek posta
kutularına teslim edilmez. Canlı gönderim için **Bağışçılar** ekranından gerçek bir
e-posta adresine sahip bağışçı kaydı oluşturulmalıdır.

## Yeni bağışçı nasıl eklenir?

- Bağışçı kendi hesabını açacaksa giriş ekranında **Bağışçı girişi** seçilir,
  ardından **İlk kez kullanıyorum — yeni bağışçı kaydı** düğmesine basılır.
  Form kaydedildiğinde hem otomatik `KB-YIL-SIRA` numarası hem giriş hesabı oluşur.
- Yetkili personel yalnızca merkezî bağışçı kaydı açacaksa yönetici panelindeki
  **Bağışçılar > + Yeni bağışçı** akışını kullanır. Kimlik numarası hiçbir iki
  akışta da elle yazılmaz.

**İşlem geçmişi** tek tablodur. `STAJ RAPORU` etiketli satırlar raporda
belgelenen geliştirme adımlarını, `CANLI SİSTEM` etiketli satırlar ise
uygulamanın veritabanına işlem anında yazılan denetim kayıtlarını gösterir.

## Test ve üretim derlemesi

API testleri:

```bash
python -m pytest -q
```

Arayüz derlemesi:

```bash
cd frontend
npm run build
```

## Ekran kaydı sırası

1. Giriş ekranı
2. Genel Bakış
3. Bağışçılar: otomatik numara ve bir uygun/bir beklemeli bağışçı örneği
4. Ünite Envanteri: bağışçı, bileşen, son kullanma ve stok çıkışı
5. Puan ve Acil Çağrı: +100/+50, unvanlar ve öncelikli aday sırası
6. Bağışçı girişi: kişinin uygunluğu, puanı, bağış geçmişi ve bildirim tercihi
7. Kurallar ve Denetim: 90/120 gün, dövme bekleme süresi ve audit kaydı

Ayrıntılı konuşma metni ayrıca teslim edilen **Ekran Kaydı ve Mail Rehberi**
belgesindedir.

## Proje yapısı

```text
app.py              Flask API ve endpoint'ler
veritabani.py       SQLite şeması
veriler.py          Tutarlı örnek veri ve demo kullanıcı
servisler.py        Uygunluk, stok ve envanter iş kuralları
bildirim.py         SMTP e-posta şablonu, gönderim ve ayar kontrolü
auth.py             Token tabanlı oturum ve rol kontrolü
audit.py            Denetim kaydı yardımcıları
tests/              Otomatik API/iş kuralı testleri
frontend/           React yönetici paneli
```

Yerel veritabanı `data/kan_bankasi.db` altında çalışma sırasında oluşturulur ve
teslim ZIP'ine dahil edilmez.
