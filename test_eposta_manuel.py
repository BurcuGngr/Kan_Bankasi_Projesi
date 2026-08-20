"""
Bu, pytest testi DEĞİL - gerçekten bir e-posta gönderip göndermediğini
görmek için elle çalıştırdığın, tek seferlik bir doğrulama script'i.

Kullanmadan önce:
1. .env dosyasını proje kökünde oluştur (.env.example'ı kopyalayıp doldur)
2. Gmail kullanıyorsan normal şifreni DEĞİL, "Uygulama Şifresi" kullan:
   https://myaccount.google.com/apppasswords
   (Bunun çalışması için Google hesabında 2 Adımlı Doğrulama açık olmalı)

Çalıştırma:
    python test_eposta_manuel.py
"""
import bildirim

if __name__ == '__main__':
    alici = input("Test e-postasının gönderileceği adres (kendi mailini yaz): ").strip()

    konu, icerik = bildirim.acil_kan_ihtiyaci_bildirimi_olustur("0 Rh-", hastane_adi="Test Hastanesi")

    print("\nGönderiliyor...")
    basarili, mesaj = bildirim.eposta_gonder(alici, konu, icerik)

    if basarili:
        print(f"✅ {mesaj}")
        print(f"'{alici}' adresini kontrol et (spam klasörüne de bak).")
    else:
        print(f"❌ {mesaj}")
        print("\nOlası sebepler:")
        print("- .env dosyası yok ya da SMTP_KULLANICI/SMTP_SIFRE eksik")
        print("- Gmail normal şifresi kullanılmış (Uygulama Şifresi gerekli)")
        print("- 2 Adımlı Doğrulama kapalı (Uygulama Şifresi için zorunlu)")