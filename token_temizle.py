"""
Süresi dolmuş api_oturumlari kayıtlarını temizler. auth.giris_yap() zaten
her başarılı girişte otomatik olarak bunu tetikliyor, ama düşük trafikli
dönemlerde (az giriş olduğunda) tablo bir süre şişebilir.

Bu script'i günde bir kez çalışacak şekilde zamanlanmış bir görev (Windows
Görev Zamanlayıcısı / cron) olarak ayarlamak, tabloyu her zaman küçük tutar.

Kullanım:
    python token_temizle.py
"""
import auth

if __name__ == '__main__':
    silinen_sayisi = auth.suresi_dolmus_tokenlari_temizle()
    print(f"✅ {silinen_sayisi} adet süresi dolmuş oturum kaydı silindi.")