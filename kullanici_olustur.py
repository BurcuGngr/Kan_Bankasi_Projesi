"""
İlk admin kullanıcısını (ya da yeni bir personel hesabını) oluşturmak için
komut satırından çalıştırılır. Neden self-servis kayıt YOK: bir hastane
sisteminde herkesin kendine hesap açabilmesi güvenlik açığıdır - hesaplar
IT/yönetici tarafından açılmalı.

Kullanım:
    python kullanici_olustur.py
"""
import getpass
import auth

if __name__ == '__main__':
    print("=== Yeni API Kullanıcısı Oluştur ===")
    kullanici_adi = input("Kullanıcı adı: ").strip()
    sifre = getpass.getpass("Şifre (yazarken görünmez): ")
    sifre_tekrar = getpass.getpass("Şifre (tekrar): ")

    if sifre != sifre_tekrar:
        print("❌ Şifreler eşleşmiyor.")
        exit(1)

    if len(sifre) < 6:
        print("❌ Şifre en az 6 karakter olmalı.")
        exit(1)

    rol = input("Rol (admin/personel) [personel]: ").strip() or "personel"
    if rol not in ('admin', 'personel'):
        print("❌ Rol sadece 'admin' veya 'personel' olabilir.")
        exit(1)

    basarili, mesaj = auth.kullanici_olustur(kullanici_adi, sifre, rol)
    if basarili:
        print(f"✅ {mesaj} ({kullanici_adi}, rol: {rol})")
    else:
        print(f"❌ {mesaj}")