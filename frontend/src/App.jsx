import { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5050/api';
const BILESENLER = ['Tam Kan', 'Eritrosit', 'Trombosit'];

function tarihYaz(tarih) {
  if (!tarih) return 'Kayıt yok';
  const ham = String(tarih).slice(0, 10);
  const [yil, ay, gun] = ham.split('-');
  return yil && ay && gun ? `${gun}.${ay}.${yil}` : tarih;
}

function durumSinifi(durum) {
  return String(durum || '').toLowerCase()
    .replaceAll('ı', 'i').replaceAll('ü', 'u').replaceAll('ö', 'o')
    .replaceAll('ş', 's').replaceAll('ç', 'c').replaceAll('ğ', 'g')
    .replaceAll(' ', '-');
}

function gercekEpostaMi(eposta) {
  if (!eposta || !eposta.includes('@')) return false;
  const alan = eposta.split('@').pop().toLocaleLowerCase('tr-TR');
  return !['example.com', 'example.net', 'example.org', 'example.test'].includes(alan);
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('kb_token'));
  const [oturum, setOturum] = useState(() => {
    try { return JSON.parse(localStorage.getItem('kb_oturum')) || null; } catch { return null; }
  });
  const [aktifSayfa, setAktifSayfa] = useState('genel');
  const [girisTipi, setGirisTipi] = useState('yonetici');
  const [bagisciToken, setBagisciToken] = useState(localStorage.getItem('kb_bagisci_token'));
  const [bagisciOturum, setBagisciOturum] = useState(() => {
    try { return JSON.parse(localStorage.getItem('kb_bagisci_oturum')) || null; } catch { return null; }
  });
  const [yukleniyor, setYukleniyor] = useState(false);
  const [hata, setHata] = useState('');
  const [bildirim, setBildirim] = useState(null);

  const [ozet, setOzet] = useState({});
  const [stoklar, setStoklar] = useState([]);
  const [bagiscilar, setBagiscilar] = useState([]);
  const [envanter, setEnvanter] = useState([]);
  const [kurallar, setKurallar] = useState({ bagis_araliklari: [], saglik_kurallari: [], urun_kurallari: [] });
  const [islemler, setIslemler] = useState([]);
  const [kanGruplari, setKanGruplari] = useState([]);
  const [acilAdaylar, setAcilAdaylar] = useState([]);
  const [epostaGonderimleri, setEpostaGonderimleri] = useState([]);
  const [acilForm, setAcilForm] = useState({
    kan_grubu_adi: '0 Rh+', aciklama: 'Acil servis için öncelikli bağışçı listesi', limit: 10,
  });

  const [girisForm, setGirisForm] = useState({ kullanici_adi: '', sifre: '' });
  const [kayitModu, setKayitModu] = useState(false);
  const [kayitKanGruplari, setKayitKanGruplari] = useState([]);
  const [kayitMesaji, setKayitMesaji] = useState('');
  const [kayitForm, setKayitForm] = useState({
    ad: '', soyad: '', cinsiyet: 'Erkek', birim: '', telefon: '', eposta: '',
    kan_grubu_id: '', kullanici_adi: '', sifre: '',
  });
  const [arama, setArama] = useState('');
  const [seciliBagisciId, setSeciliBagisciId] = useState(null);
  const [bagisForm, setBagisForm] = useState({ bilesen_turu: 'Tam Kan', adet: 1 });
  const [yeniBagisciAcik, setYeniBagisciAcik] = useState(false);
  const [yeniBagisci, setYeniBagisci] = useState({
    ad: '', soyad: '', cinsiyet: 'Erkek', birim: '', telefon: '', eposta: '',
    kan_grubu_id: '', bildirim_izni: true, gece_aranir_mi: false,
  });
  const [envanterFiltre, setEnvanterFiltre] = useState({ kan_grubu: '', bilesen: '', durum: 'AKTİF' });
  const [cikisForm, setCikisForm] = useState({
    kan_grubu_adi: 'A Rh+', bilesen_turu: 'Eritrosit', adet: 1, talep_eden_birim: '',
  });

  const seciliBagisci = bagiscilar.find((item) => item.id === seciliBagisciId) || null;

  const istek = async (yol, secenekler = {}) => {
    const yanit = await fetch(`${API}${yol}`, {
      ...secenekler,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(secenekler.headers || {}),
      },
    });
    const veri = await yanit.json().catch(() => ({ mesaj: 'Sunucudan okunamayan yanıt alındı.' }));
    if (yanit.status === 401 && token) oturumuKapat(false);
    if (!yanit.ok) throw new Error(veri.mesaj || 'İşlem tamamlanamadı.');
    return veri;
  };

  const verileriYenile = async () => {
    if (!token) return;
    setYukleniyor(true);
    setHata('');
    try {
      const [ozetY, stokY, bagisciY, envanterY, kuralY, islemY, grupY, gonderimY] = await Promise.all([
        istek('/ozet'), istek('/stoklar'), istek('/bagiscilar'), istek('/envanter'),
        istek('/kurallar'), istek('/islemler'), istek('/kan-gruplari'),
        oturum?.rol === 'admin' ? istek('/bildirim/eposta-gonderimleri?limit=30') : Promise.resolve({ veri: [] }),
      ]);
      setOzet(ozetY.veri);
      setStoklar(stokY.veri);
      setBagiscilar(bagisciY.veri);
      setEnvanter(envanterY.veri);
      setKurallar(kuralY.veri);
      setIslemler(islemY.veri);
      setKanGruplari(grupY.veri);
      setEpostaGonderimleri(gonderimY.veri);
      if (!seciliBagisciId && bagisciY.veri.length) setSeciliBagisciId(bagisciY.veri[0].id);
      if (!yeniBagisci.kan_grubu_id && grupY.veri.length) {
        setYeniBagisci((onceki) => ({ ...onceki, kan_grubu_id: String(grupY.veri[0].id) }));
      }
    } catch (err) {
      setHata(err.message);
    } finally {
      setYukleniyor(false);
    }
  };

  useEffect(() => { verileriYenile(); }, [token]);

  const girisYap = async (event) => {
    event.preventDefault();
    setHata('');
    setYukleniyor(true);
    try {
      const girisYolu = girisTipi === 'bagisci' ? '/bagisci-auth/giris' : '/auth/giris';
      const veri = await fetch(`${API}${girisYolu}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(girisForm),
      }).then(async (yanit) => {
        const govde = await yanit.json();
        if (!yanit.ok) throw new Error(govde.mesaj || 'Giriş başarısız.');
        return govde;
      });
      if (girisTipi === 'bagisci') {
        localStorage.removeItem('kb_token');
        localStorage.removeItem('kb_oturum');
        localStorage.setItem('kb_bagisci_token', veri.token);
        localStorage.setItem('kb_bagisci_oturum', JSON.stringify(veri.kullanici));
        setToken(null);
        setOturum(null);
        setBagisciToken(veri.token);
        setBagisciOturum(veri.kullanici);
      } else {
        localStorage.removeItem('kb_bagisci_token');
        localStorage.removeItem('kb_bagisci_oturum');
        localStorage.setItem('kb_token', veri.token);
        localStorage.setItem('kb_oturum', JSON.stringify(veri.kullanici));
        setBagisciToken(null);
        setBagisciOturum(null);
        setToken(veri.token);
        setOturum(veri.kullanici);
      }
    } catch (err) {
      setHata(err.message);
    } finally {
      setYukleniyor(false);
    }
  };

  const kayitFormunuAc = async () => {
    setHata('');
    setKayitMesaji('');
    setKayitModu(true);
    if (kayitKanGruplari.length) return;
    try {
      const yanit = await fetch(`${API}/genel/kan-gruplari`);
      const govde = await yanit.json();
      if (!yanit.ok) throw new Error(govde.mesaj || 'Kan grupları alınamadı.');
      setKayitKanGruplari(govde.veri);
      setKayitForm((onceki) => ({
        ...onceki, kan_grubu_id: onceki.kan_grubu_id || String(govde.veri[0]?.id || ''),
      }));
    } catch (err) { setHata(err.message); }
  };

  const bagisciKaydiOlustur = async (event) => {
    event.preventDefault();
    setHata('');
    setKayitMesaji('');
    setYukleniyor(true);
    try {
      const yanit = await fetch(`${API}/bagisci-auth/kayit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(kayitForm),
      });
      const govde = await yanit.json();
      if (!yanit.ok) throw new Error(govde.mesaj || 'Kayıt oluşturulamadı.');
      setGirisForm({ kullanici_adi: govde.veri.kullanici_adi, sifre: '' });
      setKayitMesaji(`${govde.veri.bagisci_no} numaralı kaydınız oluşturuldu. Şimdi giriş yapabilirsiniz.`);
      setKayitModu(false);
      setKayitForm({
        ad: '', soyad: '', cinsiyet: 'Erkek', birim: '', telefon: '', eposta: '',
        kan_grubu_id: String(kayitKanGruplari[0]?.id || ''), kullanici_adi: '', sifre: '',
      });
    } catch (err) { setHata(err.message); } finally { setYukleniyor(false); }
  };

  const bagisciOturumuKapat = async () => {
    if (bagisciToken) {
      try {
        await fetch(`${API}/bagisci-auth/cikis`, {
          method: 'POST', headers: { Authorization: `Bearer ${bagisciToken}` },
        });
      } catch { /* Yerel oturum her durumda kapanır. */ }
    }
    localStorage.removeItem('kb_bagisci_token');
    localStorage.removeItem('kb_bagisci_oturum');
    setBagisciToken(null);
    setBagisciOturum(null);
    setGirisTipi('bagisci');
    setGirisForm({ kullanici_adi: '', sifre: '' });
  };

  const oturumuKapat = async (sunucuyaBildir = true) => {
    if (sunucuyaBildir && token) {
      try { await istek('/auth/cikis', { method: 'POST' }); } catch { /* Yerel oturum yine kapanır. */ }
    }
    localStorage.removeItem('kb_token');
    localStorage.removeItem('kb_oturum');
    setToken(null);
    setOturum(null);
  };

  const mesajGoster = (tip, mesaj) => {
    setBildirim({ tip, mesaj });
    window.setTimeout(() => setBildirim(null), 5000);
  };

  const bagisKaydet = async (event) => {
    event.preventDefault();
    if (!seciliBagisci) return;
    try {
      const sonuc = await istek('/bagislar', {
        method: 'POST',
        body: JSON.stringify({ bagisci_id: seciliBagisci.id, ...bagisForm }),
      });
      mesajGoster('basari', sonuc.mesaj);
      await verileriYenile();
    } catch (err) { mesajGoster('hata', err.message); }
  };

  const bagisciOlustur = async (event) => {
    event.preventDefault();
    try {
      const sonuc = await istek('/bagiscilar', {
        method: 'POST', body: JSON.stringify({ ...yeniBagisci, kan_grubu_id: Number(yeniBagisci.kan_grubu_id) }),
      });
      mesajGoster('basari', `${sonuc.veri.bagisci_no} otomatik oluşturuldu.`);
      setYeniBagisci({
        ad: '', soyad: '', cinsiyet: 'Erkek', birim: '', telefon: '', eposta: '',
        kan_grubu_id: String(kanGruplari[0]?.id || ''), bildirim_izni: true, gece_aranir_mi: false,
      });
      setYeniBagisciAcik(false);
      await verileriYenile();
      setSeciliBagisciId(sonuc.veri.id);
    } catch (err) { mesajGoster('hata', err.message); }
  };

  const stoktanCik = async (event) => {
    event.preventDefault();
    try {
      const sonuc = await istek('/cikislar', {
        method: 'POST', body: JSON.stringify(cikisForm),
      });
      mesajGoster('basari', sonuc.mesaj);
      setCikisForm((onceki) => ({ ...onceki, adet: 1, talep_eden_birim: '' }));
      await verileriYenile();
    } catch (err) { mesajGoster('hata', err.message); }
  };

  const acilAdaylariGetir = async ({ sessiz = false } = {}) => {
    try {
      const sonuc = await istek(`/acil-cagri-adaylari?kan_grubu=${encodeURIComponent(acilForm.kan_grubu_adi)}&limit=${acilForm.limit}`);
      setAcilAdaylar(sonuc.veri);
      if (!sessiz) mesajGoster('basari', `${sonuc.veri.length} uygun ve bildirim izinli bağışçı sıralandı.`);
    } catch (err) { mesajGoster('hata', err.message); }
  };

  useEffect(() => {
    if (token && aktifSayfa === 'acil') acilAdaylariGetir({ sessiz: true });
  }, [token, aktifSayfa, acilForm.kan_grubu_adi, acilForm.limit]);

  const acilCagriOlustur = async (event) => {
    event.preventDefault();
    const epostaGonder = event.nativeEvent.submitter?.dataset?.eposta === 'true';
    try {
      const sonuc = await istek('/acil-cagrilar', {
        method: 'POST', body: JSON.stringify({ ...acilForm, eposta_gonder: epostaGonder }),
      });
      setAcilAdaylar(sonuc.veri.adaylar);
      mesajGoster('basari', sonuc.mesaj);
      await verileriYenile();
    } catch (err) { mesajGoster('hata', err.message); }
  };

  const filtreliBagiscilar = useMemo(() => {
    const aranan = arama.toLocaleLowerCase('tr-TR').trim();
    if (!aranan) return bagiscilar;
    return bagiscilar.filter((b) => [b.bagisci_no, b.ad, b.soyad, b.grup_adi, b.telefon]
      .some((deger) => String(deger || '').toLocaleLowerCase('tr-TR').includes(aranan)));
  }, [arama, bagiscilar]);

  const filtreliEnvanter = useMemo(() => envanter.filter((item) =>
    (!envanterFiltre.kan_grubu || item.grup_adi === envanterFiltre.kan_grubu)
    && (!envanterFiltre.bilesen || item.bilesen_turu === envanterFiltre.bilesen)
    && (!envanterFiltre.durum || item.durum === envanterFiltre.durum)
  ), [envanter, envanterFiltre]);

  const grupluEnvanter = useMemo(() => {
    const gruplar = new Map();
    filtreliEnvanter.forEach((item) => {
      const anahtar = [
        item.bagisci_no, item.grup_adi, item.bilesen_turu, item.bagis_tarihi,
        item.son_kullanma_tarihi, item.saklama_konumu, item.durum,
      ].join('|');
      if (!gruplar.has(anahtar)) {
        gruplar.set(anahtar, { ...item, grup_anahtari: anahtar, unite_kodlari: [], unite_sayisi: 0 });
      }
      const grup = gruplar.get(anahtar);
      grup.unite_kodlari.push(item.unite_kodu);
      grup.unite_sayisi += 1;
    });
    return [...gruplar.values()];
  }, [filtreliEnvanter]);

  if (bagisciToken) {
    return <BagisciPanel token={bagisciToken} oturum={bagisciOturum} cikis={bagisciOturumuKapat} />;
  }

  if (!token) {
    return (
      <main className="giris-sayfasi">
        <section className="giris-tanitim">
          <div className="marka-isareti">KB</div>
          <h1>Kan Bankası<br />Dijital Platformu</h1>
        </section>
        <section className={`giris-karti ${kayitModu ? 'kayit-modu' : ''}`}>
          <div className="giris-sekme">
            <button type="button" className={girisTipi === 'yonetici' ? 'aktif' : ''} onClick={() => { setGirisTipi('yonetici'); setKayitModu(false); setGirisForm({ kullanici_adi: '', sifre: '' }); setKayitMesaji(''); setHata(''); }}>Yönetici girişi</button>
            <button type="button" className={girisTipi === 'bagisci' ? 'aktif' : ''} onClick={() => { setGirisTipi('bagisci'); setKayitModu(false); setGirisForm({ kullanici_adi: '', sifre: '' }); setKayitMesaji(''); setHata(''); }}>Bağışçı girişi</button>
          </div>
          <div>
            <p className="ust-etiket">{kayitModu ? 'Yeni hesap' : girisTipi === 'bagisci' ? 'Kişisel erişim' : 'Yetkili erişimi'}</p>
            <h2>{kayitModu ? 'Bağışçı kaydı' : girisTipi === 'bagisci' ? 'Bağışçı paneli' : 'Yönetici paneli'}</h2>
            <p className="soluk">{kayitModu ? 'Kimlik numaranızı sistem üretir; bilgileriniz mevcut kayıtlarla çakışmaya karşı kontrol edilir.' : girisTipi === 'bagisci' ? 'Yalnızca kendi bağış, puan ve uygunluk bilgilerinizi görürsünüz.' : 'Stok, bağışçı, acil çağrı ve denetim işlemlerini yönetin.'}</p>
          </div>
          {hata && <div className="uyari hata">{hata}</div>}
          {kayitMesaji && <div className="uyari basari">{kayitMesaji}</div>}
          {kayitModu ? (
            <form onSubmit={bagisciKaydiOlustur} className="kayit-grid">
              <label>Ad<input value={kayitForm.ad} onChange={(e) => setKayitForm({ ...kayitForm, ad: e.target.value })} required /></label>
              <label>Soyad<input value={kayitForm.soyad} onChange={(e) => setKayitForm({ ...kayitForm, soyad: e.target.value })} required /></label>
              <label>Cinsiyet<select value={kayitForm.cinsiyet} onChange={(e) => setKayitForm({ ...kayitForm, cinsiyet: e.target.value })}><option>Erkek</option><option>Kadın</option></select></label>
              <label>Kan grubu<select value={kayitForm.kan_grubu_id} onChange={(e) => setKayitForm({ ...kayitForm, kan_grubu_id: e.target.value })} required><option value="">Seçin</option>{kayitKanGruplari.map((grup) => <option key={grup.id} value={grup.id}>{grup.grup_adi}</option>)}</select></label>
              <label>Birim / hastane<input value={kayitForm.birim} onChange={(e) => setKayitForm({ ...kayitForm, birim: e.target.value })} required /></label>
              <label>Telefon<input type="tel" value={kayitForm.telefon} onChange={(e) => setKayitForm({ ...kayitForm, telefon: e.target.value })} required /></label>
              <label className="tam">E-posta<input type="email" value={kayitForm.eposta} onChange={(e) => setKayitForm({ ...kayitForm, eposta: e.target.value })} required /></label>
              <label>Kullanıcı adı<input minLength="3" value={kayitForm.kullanici_adi} onChange={(e) => setKayitForm({ ...kayitForm, kullanici_adi: e.target.value })} required /></label>
              <label>Şifre<input type="password" minLength="8" value={kayitForm.sifre} onChange={(e) => setKayitForm({ ...kayitForm, sifre: e.target.value })} required /></label>
              <button type="button" className="buton sade" onClick={() => { setKayitModu(false); setHata(''); }}>Girişe dön</button>
              <button className="buton birincil" disabled={yukleniyor}>{yukleniyor ? 'Kaydediliyor…' : 'Kaydımı oluştur'}</button>
            </form>
          ) : (
            <form onSubmit={girisYap} className="form-dikey">
              <label>Kullanıcı adı<input value={girisForm.kullanici_adi} onChange={(e) => setGirisForm({ ...girisForm, kullanici_adi: e.target.value })} required /></label>
              <label>Şifre<input type="password" value={girisForm.sifre} onChange={(e) => setGirisForm({ ...girisForm, sifre: e.target.value })} required /></label>
              <button className="buton birincil" disabled={yukleniyor}>{yukleniyor ? 'Bağlanıyor…' : `${girisTipi === 'bagisci' ? 'Bağışçı' : 'Yönetici'} panelini aç`}</button>
              {girisTipi === 'bagisci' && <button type="button" className="buton sade kayit-gecis" onClick={kayitFormunuAc}>İlk kez kullanıyorum — yeni bağışçı kaydı</button>}
            </form>
          )}
        </section>
      </main>
    );
  }

  const sayfaBasliklari = {
    genel: ['Genel Bakış', 'Stok, uygunluk ve risk göstergelerinin güncel özeti'],
    bagiscilar: ['Bağışçı Yönetimi', 'Kimlik karışıklığını önleyen kayıt ve uygunluk akışı'],
    envanter: ['Ünite Envanteri', 'Her kan ünitesinin kaynağı, ürünü, süresi ve konumu'],
    acil: ['Puanlama ve Acil Çağrı', 'Teşvik puanları, öncelikli bağışçı sırası ve e-posta bildirimleri'],
    kurallar: ['Kurallar ve Denetim', 'Uygulanan karar parametreleri ve işlem geçmişi'],
  };

  return (
    <div className="uygulama">
      <aside className="yan-menu">
        <div className="marka"><span className="marka-isareti kucuk">KB</span><div><strong>Kan Bankası</strong><small>Yönetici Paneli</small></div></div>
        <nav>
          {[
            ['genel', '⌂', 'Genel Bakış'], ['bagiscilar', '♙', 'Bağışçılar'],
            ['envanter', '▦', 'Ünite Envanteri'], ['acil', '⚑', 'Puan ve Acil Çağrı'],
            ['kurallar', '✓', 'Kurallar ve Denetim'],
          ].map(([kod, ikon, etiket]) => (
            <button key={kod} className={aktifSayfa === kod ? 'aktif' : ''} onClick={() => setAktifSayfa(kod)}>
              <span>{ikon}</span>{etiket}
            </button>
          ))}
        </nav>
        <div className="menu-alt">
          <div className="kullanici-karti"><span>{oturum?.kullanici_adi?.slice(0, 1).toUpperCase()}</span><div><strong>{oturum?.kullanici_adi}</strong><small>{oturum?.rol_etiketi || 'Yönetici'}</small></div></div>
          <button className="metin-buton" onClick={() => oturumuKapat()}>Güvenli çıkış</button>
        </div>
      </aside>

      <main className="icerik">
        <header className="sayfa-ust">
          <div><p className="ust-etiket">Akıllı Hastane Kan Bankası</p><h1>{sayfaBasliklari[aktifSayfa][0]}</h1><p>{sayfaBasliklari[aktifSayfa][1]}</p></div>
          <div className="sistem-durumu"><i /> Sistem çevrimiçi <span>{new Date().toLocaleDateString('tr-TR')}</span></div>
        </header>

        {bildirim && <div className={`toast ${bildirim.tip}`}>{bildirim.mesaj}</div>}
        {hata && <div className="uyari hata">{hata}</div>}
        {yukleniyor && <div className="yukleniyor">Veriler güncelleniyor…</div>}

        {aktifSayfa === 'genel' && (
          <>
            <section className="metrik-grid">
              <Metrik etiket="Aktif stok" deger={ozet.toplam_aktif_unite ?? '—'} birim="ünite" renk="lacivert" />
              <Metrik etiket="Kritik grup" deger={ozet.kritik_kan_grubu ?? '—'} birim="kan grubu" renk="kirmizi" />
              <Metrik etiket="7 günde dolacak" deger={ozet.yedi_gunde_dolacak ?? '—'} birim="ünite" renk="turuncu" />
              <Metrik etiket="Bağışa uygun" deger={ozet.uygun_bagisci ?? '—'} birim={`/${ozet.toplam_bagisci ?? '—'} bağışçı`} renk="yesil" />
            </section>
            <section className="bolum-basligi"><div><h2>Anlık kan stok durumu</h2><p>Aktif ve süresi geçmemiş üniteler kan grubuna göre hesaplanır.</p></div><span className="yenileme">Canlı veritabanı</span></section>
            <section className="stok-grid">
              {stoklar.map((stok) => (
                <article className={`stok-karti ${durumSinifi(stok.durum)}`} key={stok.id}>
                  <div className="stok-ust"><span className="kan-grubu">{stok.grup_adi}</span><Durum durum={stok.durum} /></div>
                  <div className="stok-sayi"><strong>{stok.unite_sayisi}</strong><span>aktif ünite</span></div>
                  <div className="seviye"><i style={{ width: `${Math.min(100, (stok.unite_sayisi / Math.max(stok.kritik_esik * 4, 1)) * 100)}%` }} /></div>
                  <div className="stok-alt"><span>Kritik eşik <b>{stok.kritik_esik}</b></span><span>{stok.bagisci_sayisi} bağışçı</span><span>{stok.yedi_gunde_dolacak} yakın SKT</span></div>
                </article>
              ))}
            </section>
            <section className="iki-kolon bilgi-seridi">
              <article className="panel vurgu-panel"><p className="ust-etiket">Bağışçı kayıt yönetimi</p><h3>Kayıtlar merkezi olarak eşleştirilir</h3><p>Her bağışçıya benzersiz bir <b>KB-YYYY-XXXX</b> kayıt numarası atanır. Bağış sırasında kişi seçildiğinde kimlik ve kan grubu bilgileri mevcut kayıttan alınır.</p><button className="buton ikincil" onClick={() => setAktifSayfa('bagiscilar')}>Bağışçı kayıtlarını aç</button></article>
              <article className="panel"><p className="ust-etiket">İzlenebilirlik</p><h3>Her ünite kendi koduyla takipte</h3><p>Bağışçı, ürün türü, bağış tarihi, son kullanma tarihi, kalan gün ve saklama konumu aynı satırda görünür.</p><button className="buton ikincil" onClick={() => setAktifSayfa('envanter')}>Envanteri aç</button></article>
            </section>
          </>
        )}

        {aktifSayfa === 'bagiscilar' && (
          <>
            <section className="araç-cubugu panel">
              <div className="arama"><span>⌕</span><input placeholder="Bağışçı no, ad, telefon veya kan grubu ara" value={arama} onChange={(e) => setArama(e.target.value)} /></div>
              {oturum?.rol === 'admin' && <button className="buton birincil" onClick={() => setYeniBagisciAcik(!yeniBagisciAcik)}>+ Yeni bağışçı</button>}
            </section>
            {yeniBagisciAcik && (
              <form className="panel form-grid yeni-kayit" onSubmit={bagisciOlustur}>
                <div className="tam"><p className="ust-etiket">Otomatik numaralı kayıt</p><h3>Yeni bağışçı</h3><p className="soluk">Kullanıcı ID alanı yoktur; numarayı sistem üretir.</p></div>
                <label>Ad<input value={yeniBagisci.ad} onChange={(e) => setYeniBagisci({ ...yeniBagisci, ad: e.target.value })} required /></label>
                <label>Soyad<input value={yeniBagisci.soyad} onChange={(e) => setYeniBagisci({ ...yeniBagisci, soyad: e.target.value })} required /></label>
                <label>Cinsiyet<select value={yeniBagisci.cinsiyet} onChange={(e) => setYeniBagisci({ ...yeniBagisci, cinsiyet: e.target.value })}><option>Erkek</option><option>Kadın</option></select></label>
                <label>Kan grubu<select value={yeniBagisci.kan_grubu_id} onChange={(e) => setYeniBagisci({ ...yeniBagisci, kan_grubu_id: e.target.value })}>{kanGruplari.map((g) => <option key={g.id} value={g.id}>{g.grup_adi}</option>)}</select></label>
                <label>Birim<input value={yeniBagisci.birim} onChange={(e) => setYeniBagisci({ ...yeniBagisci, birim: e.target.value })} required /></label>
                <label>Telefon<input value={yeniBagisci.telefon} onChange={(e) => setYeniBagisci({ ...yeniBagisci, telefon: e.target.value })} required /></label>
                <label className="tam">E-posta<input type="email" value={yeniBagisci.eposta} onChange={(e) => setYeniBagisci({ ...yeniBagisci, eposta: e.target.value })} /></label>
                <div className="tam form-aksiyon"><button type="button" className="buton sade" onClick={() => setYeniBagisciAcik(false)}>Vazgeç</button><button className="buton birincil">Kaydı oluştur</button></div>
              </form>
            )}
            <section className="bagisci-yerlesim">
              <div className="panel tablo-panel">
                <div className="panel-basligi"><div><h3>Bağışçı kayıtları</h3><p>{filtreliBagiscilar.length} sonuç</p></div><span className="aciklama-etiketi">ID otomatik</span></div>
                <div className="tablo-kapsayici"><table><thead><tr><th>Bağışçı</th><th>Kan</th><th>Puan / Unvan</th><th>Cinsiyet</th><th>Son bağış</th><th>Uygunluk</th><th>Aktif ünite</th></tr></thead>
                  <tbody>{filtreliBagiscilar.map((b) => (
                    <tr key={b.id} onClick={() => setSeciliBagisciId(b.id)} className={b.id === seciliBagisciId ? 'secili' : ''}>
                      <td><strong>{b.ad} {b.soyad}</strong><small>{b.bagisci_no}</small></td><td><span className="kan-rozet">{b.grup_adi}</span></td><td><strong>{b.toplam_puan} puan</strong><small>{b.unvan}</small></td><td>{b.cinsiyet}</td><td>{tarihYaz(b.son_bagis_tarihi)}</td><td><Durum durum={b.uygunluk.durum} /></td><td>{b.aktif_unite_sayisi}</td>
                    </tr>
                  ))}</tbody></table></div>
              </div>
              <aside className="panel bagisci-detay">
                {seciliBagisci ? <>
                  <div className="profil-baslik"><div className="avatar">{seciliBagisci.ad[0]}{seciliBagisci.soyad[0]}</div><div><p className="ust-etiket">{seciliBagisci.bagisci_no}</p><h3>{seciliBagisci.ad} {seciliBagisci.soyad}</h3><span>{seciliBagisci.birim}</span></div><span className="kan-rozet buyuk">{seciliBagisci.grup_adi}</span></div>
                  <div className="detay-grid"><div><span>Cinsiyet</span><b>{seciliBagisci.cinsiyet}</b></div><div><span>Bağış aralığı</span><b>{seciliBagisci.uygunluk.bagis_araligi_gun} gün</b></div><div><span>Son bağış</span><b>{tarihYaz(seciliBagisci.son_bagis_tarihi)}</b></div><div><span>En erken tarih</span><b>{tarihYaz(seciliBagisci.uygunluk.sonraki_uygun_tarih)}</b></div><div><span>Toplam puan</span><b>{seciliBagisci.toplam_puan} puan</b></div><div><span>Bağışçı unvanı</span><b>{seciliBagisci.unvan}</b></div></div>
                  <div className={`uygunluk-kutusu ${seciliBagisci.uygunluk.uygun_mu ? 'uygun' : 'engel'}`}><div><Durum durum={seciliBagisci.uygunluk.durum} /><b>{seciliBagisci.uygunluk.mesaj}</b></div>{seciliBagisci.uygunluk.nedenler.map((n) => <p key={n}>• {n}</p>)}</div>
                  <div className={`on-degerlendirme-ozet ${seciliBagisci.on_degerlendirme?.inceleme_gerekli ? 'inceleme' : ''}`}>
                    <b>Bağışçı ön değerlendirmesi</b>
                    {seciliBagisci.on_degerlendirme ? <>
                      <small>Son form: {seciliBagisci.on_degerlendirme.kayit_tarihi}</small>
                      <span>{seciliBagisci.on_degerlendirme.inceleme_gerekli ? 'Hekim incelemesi gereken yanıt var.' : 'Bildirilen ek risk yanıtı yok.'}</span>
                    </> : <span>Henüz sağlık ön değerlendirme formu doldurulmadı.</span>}
                    <small>Dövme ve sağlık yanıtları bağış uygunluğunu etkiler; ürünün raf ömrü bileşen türüne göre hesaplanır.</small>
                  </div>
                  <form className="form-dikey bagis-formu" onSubmit={bagisKaydet}>
                    <h4>Yeni bağış kaydı</h4>
                    <label>Bağışçı numarası<input value={seciliBagisci.bagisci_no} readOnly /></label>
                    <label>Kan grubu<input value={`${seciliBagisci.grup_adi} — profilden otomatik`} readOnly /></label>
                    <div className="form-iki"><label>Bileşen<select value={bagisForm.bilesen_turu} onChange={(e) => setBagisForm({ ...bagisForm, bilesen_turu: e.target.value })}>{BILESENLER.map((b) => <option key={b}>{b}</option>)}</select></label><label>Ünite<input type="number" min="1" max="5" value={bagisForm.adet} onChange={(e) => setBagisForm({ ...bagisForm, adet: Number(e.target.value) })} /></label></div>
                    <button className="buton birincil" disabled={!seciliBagisci.uygunluk.uygun_mu}>{seciliBagisci.uygunluk.uygun_mu ? 'Bağışı kaydet' : 'Uygunluk sağlanmadan kayıt yapılamaz'}</button>
                  </form>
                </> : <p>Detay için bir bağışçı seçin.</p>}
              </aside>
            </section>
          </>
        )}

        {aktifSayfa === 'envanter' && (
          <>
            <section className="iki-kolon envanter-ust">
              <form className="panel form-grid cikis-formu" onSubmit={stoktanCik}>
                <div className="tam"><p className="ust-etiket">FIFO stok çıkışı</p><h3>Hastaneye kan çıkışı</h3><p className="soluk">Süresi en yakın uygun üniteler sistem tarafından seçilir.</p></div>
                <label>Kan grubu<select value={cikisForm.kan_grubu_adi} onChange={(e) => setCikisForm({ ...cikisForm, kan_grubu_adi: e.target.value })}>{kanGruplari.map((g) => <option key={g.id}>{g.grup_adi}</option>)}</select></label>
                <label>Bileşen<select value={cikisForm.bilesen_turu} onChange={(e) => setCikisForm({ ...cikisForm, bilesen_turu: e.target.value })}>{BILESENLER.map((b) => <option key={b}>{b}</option>)}</select></label>
                <label>Ünite<input type="number" min="1" value={cikisForm.adet} onChange={(e) => setCikisForm({ ...cikisForm, adet: Number(e.target.value) })} required /></label>
                <label>Talep eden birim<input value={cikisForm.talep_eden_birim} onChange={(e) => setCikisForm({ ...cikisForm, talep_eden_birim: e.target.value })} placeholder="Örn. Acil Servis" required /></label>
                <button className="buton birincil tam">FIFO çıkışını onayla</button>
              </form>
              <article className="panel envanter-aciklama"><p className="ust-etiket">Ünite izlenebilirliği</p><h3>Bağış kaynağı ve ürün hareketleri birlikte izlenir</h3><ul><li>Her torbada tekil ünite kodu bulunur.</li><li>Bağışçı numarası ve adı görünür.</li><li>Kan grubu ile bileşen ayrı tutulur.</li><li>Bağış ve son kullanma tarihi izlenir.</li><li>Kullanım, karantina ve süre dolumu durumları ayrılır.</li></ul></article>
            </section>
            <section className="panel tablo-panel">
              <div className="panel-basligi filtre-basligi"><div><h3>Bağış ve bileşen bazlı stok envanteri</h3><p>{grupluEnvanter.length} satırda {filtreliEnvanter.length} tekil ünite gösteriliyor</p></div><div className="filtreler">
                <select value={envanterFiltre.kan_grubu} onChange={(e) => setEnvanterFiltre({ ...envanterFiltre, kan_grubu: e.target.value })}><option value="">Tüm kan grupları</option>{kanGruplari.map((g) => <option key={g.id}>{g.grup_adi}</option>)}</select>
                <select value={envanterFiltre.bilesen} onChange={(e) => setEnvanterFiltre({ ...envanterFiltre, bilesen: e.target.value })}><option value="">Tüm bileşenler</option>{BILESENLER.map((b) => <option key={b}>{b}</option>)}</select>
                <select value={envanterFiltre.durum} onChange={(e) => setEnvanterFiltre({ ...envanterFiltre, durum: e.target.value })}><option value="">Tüm durumlar</option><option>AKTİF</option><option>KULLANILDI</option><option>SÜRESİ DOLDU</option><option>KARANTİNA</option></select>
              </div></div>
              <div className="tablo-kapsayici"><table><thead><tr><th>Üniteler</th><th>Bağışçı</th><th>Kan</th><th>Bileşen</th><th>Bağış tarihi</th><th>Son kullanma</th><th>Kalan</th><th>Konum</th><th>Durum</th></tr></thead><tbody>
                {grupluEnvanter.map((u) => <tr key={u.grup_anahtari}><td><strong>{u.unite_sayisi} ünite</strong><small className="mono unite-kodlari">{u.unite_kodlari.join(' · ')}</small></td><td><strong>{u.bagisci}</strong><small>{u.bagisci_no}</small></td><td><span className="kan-rozet">{u.grup_adi}</span></td><td>{u.bilesen_turu}</td><td>{tarihYaz(u.bagis_tarihi)}</td><td>{tarihYaz(u.son_kullanma_tarihi)}</td><td className={u.kalan_gun <= 7 && u.durum === 'AKTİF' ? 'yakin-skt' : ''}>{u.durum === 'AKTİF' ? `${u.kalan_gun} gün` : '—'}</td><td>{u.saklama_konumu}</td><td><Durum durum={u.durum} /></td></tr>)}
              </tbody></table></div>
            </section>
          </>
        )}

        {aktifSayfa === 'acil' && (
          <>
            <section className="puan-kural-seridi">
              <article className="panel puan-karti"><span>Standart bağış</span><strong>+100</strong><small>puan</small></article>
              <article className="panel puan-karti bonus"><span>Kritik stok bonusu</span><strong>+50</strong><small>ek puan</small></article>
              <article className="panel unvan-karti"><span>Bronz</span><b>0–200</b></article>
              <article className="panel unvan-karti gumus"><span>Gümüş</span><b>201–500</b></article>
              <article className="panel unvan-karti altin"><span>Altın</span><b>501–1000</b></article>
              <article className="panel unvan-karti platin"><span>Platin</span><b>1001+</b></article>
            </section>
            <section className="iki-kolon acil-ust">
              <form className="panel form-grid" onSubmit={acilCagriOlustur}>
                <div className="tam"><p className="ust-etiket">Öncelikli Acil Çağrı</p><h3>Akıllı bağışçı sıralaması</h3><p className="soluk">Yalnızca bildirim izni açık, aynı kan grubundaki ve bağışa uygun kişiler; son bağıştan geçen süreye göre SQL ile sıralanır.</p></div>
                <label>Kan grubu<select value={acilForm.kan_grubu_adi} onChange={(e) => setAcilForm({ ...acilForm, kan_grubu_adi: e.target.value })}>{kanGruplari.map((g) => <option key={g.id}>{g.grup_adi}</option>)}</select></label>
                <label>Aday sınırı<input type="number" min="1" max="100" value={acilForm.limit} onChange={(e) => setAcilForm({ ...acilForm, limit: Number(e.target.value) })} /></label>
                <label className="tam">Çağrı açıklaması<input value={acilForm.aciklama} onChange={(e) => setAcilForm({ ...acilForm, aciklama: e.target.value })} required /></label>
                <div className="tam form-aksiyon"><button type="button" className="buton ikincil" onClick={() => acilAdaylariGetir()}>Listeyi yenile</button><button className="buton sade" data-eposta="false">Çağrıyı kaydet</button><button className="buton birincil eposta-gonder-buton" data-eposta="true">Kaydet ve e-posta gönder</button></div>
              </form>
              <article className="panel acil-aciklama"><p className="ust-etiket">Bildirim iş akışı</p><h3>Uygun bağışçılara öncelikli çağrı</h3><ol><li>Kan grubu eşleştirilir.</li><li>Bildirim izni kapalı kişiler elenir.</li><li>90/120 gün ve sağlık engelleri kontrol edilir.</li><li>En uzun süredir bağış yapmayan kişi öne alınır.</li><li>Kırmızı düğmeyle çağrı kaydedilir ve uygun adaylara e-posta gönderilir.</li></ol></article>
            </section>
            <section className="panel tablo-panel">
              <div className="panel-basligi"><div><h3>Öncelikli bağışçı listesi</h3><p>{acilAdaylar.length ? `${acilAdaylar.length} uygun aday` : 'Kan grubu seçip listeyi oluşturun'}</p></div><span className="aciklama-etiketi">SQL akıllı sıra</span></div>
              <div className="tablo-kapsayici"><table><thead><tr><th>Sıra</th><th>Bağışçı</th><th>Kan</th><th>Son bağış</th><th>Geçen süre</th><th>Puan / Unvan</th><th>İletişim</th><th>Uygunluk</th></tr></thead><tbody>
                {acilAdaylar.map((aday) => <tr key={aday.id}><td><strong className="sira-rozet">{aday.sira}</strong></td><td><strong>{aday.ad} {aday.soyad}</strong><small>{aday.bagisci_no}</small></td><td><span className="kan-rozet">{aday.grup_adi}</span></td><td>{tarihYaz(aday.son_bagis_tarihi)}</td><td>{aday.son_bagistan_gecen_gun ?? 'İlk bağış'}{aday.son_bagistan_gecen_gun != null && ' gün'}</td><td><strong>{aday.toplam_puan} puan</strong><small>{aday.unvan}</small></td><td>{aday.telefon}<small>{gercekEpostaMi(aday.eposta) ? aday.eposta : 'Gerçek e-posta tanımlı değil'}</small></td><td><Durum durum="UYGUN" /></td></tr>)}
              </tbody></table></div>
            </section>
            <section className="panel tablo-panel denetim">
              <div className="panel-basligi"><div><h3>E-posta gönderim geçmişi</h3><p>Başarılı ve başarısız SMTP işlemleri</p></div><span className="aciklama-etiketi">Kayıtlı bildirim</span></div>
              <div className="tablo-kapsayici"><table><thead><tr><th>Zaman</th><th>Bağışçı</th><th>Kan</th><th>Alıcı</th><th>Durum</th><th>Açıklama</th></tr></thead><tbody>
                {epostaGonderimleri.length ? epostaGonderimleri.map((kayit) => <tr key={kayit.id}><td className="mono">{kayit.gonderim_tarihi}</td><td><strong>{kayit.bagisci}</strong><small>{kayit.bagisci_no}</small></td><td><span className="kan-rozet">{kayit.grup_adi}</span></td><td>{kayit.alici_eposta}</td><td><Durum durum={kayit.durum} /></td><td>{kayit.hata_mesaji || 'İleti SMTP sunucusuna teslim edildi.'}</td></tr>) : <tr><td colSpan="6" className="bos-satir">Henüz e-posta gönderim kaydı yok.</td></tr>}
              </tbody></table></div>
            </section>
          </>
        )}

        {aktifSayfa === 'kurallar' && (
          <>
            <div className="uyari bilgi"><strong>Tıbbi kapsam sınırı:</strong> {kurallar.tibbi_uyari}</div>
            <section className="uc-kolon kural-kartlari">
              <article className="panel"><p className="ust-etiket">Tam kan aralığı</p><h3>Cinsiyete göre bekleme</h3>{kurallar.bagis_araliklari.map((k) => <div className="kural-satiri" key={k.cinsiyet}><span>{k.cinsiyet}</span><b>{k.gun} gün</b></div>)}</article>
              <article className="panel"><p className="ust-etiket">Geçici ve kalıcı engeller</p><h3>Sağlık uygunluğu</h3>{kurallar.saglik_kurallari.map((k) => <div className="kural-blok" key={k.kural}><b>{k.kural}</b><span>{k.bekleme}</span><small>{k.sistemdeki_uygulama}</small></div>)}</article>
              <article className="panel"><p className="ust-etiket">Son kullanma hesabı</p><h3>Ürün bekleme süreleri</h3>{kurallar.urun_kurallari.map((k) => <div className="kural-satiri" key={k.urun}><span>{k.urun}</span><b>{k.raf_omru_gun} gün</b></div>)}</article>
              <article className="panel"><p className="ust-etiket">Bağışçı teşviki</p><h3>Puanlama ve unvanlar</h3><div className="kural-satiri"><span>Standart bağış</span><b>+{kurallar.puan_kurallari?.standart_bagis || 100}</b></div><div className="kural-satiri"><span>Kritik stok bonusu</span><b>+{kurallar.puan_kurallari?.kritik_stok_bonusu || 50}</b></div>{kurallar.puan_kurallari?.unvanlar?.map((u) => <div className="kural-satiri" key={u}><span>{u}</span></div>)}</article>
            </section>
            <section className="panel tablo-panel denetim">
              <div className="panel-basligi"><div><h3>İşlem geçmişi</h3><p>Canlı sistem işlemleri ve staj raporunda belgelenen geliştirme kayıtları.</p></div><span className="aciklama-etiketi">Denetim izi</span></div>
              <div className="tablo-kapsayici"><table><thead><tr><th>Zaman</th><th>Kaynak</th><th>Kullanıcı</th><th>İşlem</th><th>Açıklama</th><th>IP</th></tr></thead><tbody>{islemler.map((islem) => <tr key={islem.id}><td className="mono">{islem.tarih}</td><td><span className="aciklama-etiketi">{islem.kaynak}</span></td><td>{islem.kullanici_adi}</td><td><Durum durum={islem.islem_turu} /></td><td>{islem.detay}</td><td className="mono">{islem.ip_adresi || '—'}</td></tr>)}</tbody></table></div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function BagisciPanel({ token, oturum, cikis }) {
  const [veri, setVeri] = useState(null);
  const [hata, setHata] = useState('');
  const [yukleniyor, setYukleniyor] = useState(true);
  const [onFormMesaji, setOnFormMesaji] = useState('');
  const [onForm, setOnForm] = useState({
    dovme_piercing_mi: false, dovme_tarihi: '', ates_enfeksiyon_mi: false,
    antibiyotik_ilac_mi: false, ameliyat_transfuzyon_mi: false,
    hamilelik_emzirme_mi: false, aciklama: '', onay: false,
  });

  const yenile = async () => {
    setYukleniyor(true);
    setHata('');
    try {
      const yanit = await fetch(`${API}/bagisci-panel/ozet`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const govde = await yanit.json();
      if (!yanit.ok) throw new Error(govde.mesaj || 'Bağışçı bilgileri alınamadı.');
      setVeri(govde.veri);
    } catch (err) { setHata(err.message); } finally { setYukleniyor(false); }
  };

  useEffect(() => { yenile(); }, [token]);

  const bildirimDegistir = async () => {
    if (!veri) return;
    try {
      const yeniIzin = !Boolean(veri.profil.bildirim_izni);
      const yanit = await fetch(`${API}/bagisci-panel/bildirim-izni`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ bildirim_izni: yeniIzin }),
      });
      if (!yanit.ok) throw new Error('Bildirim tercihi güncellenemedi.');
      await yenile();
    } catch (err) { setHata(err.message); }
  };

  const onDegerlendirmeKaydet = async (event) => {
    event.preventDefault();
    setHata('');
    setOnFormMesaji('');
    try {
      const yanit = await fetch(`${API}/bagisci-panel/on-degerlendirme`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(onForm),
      });
      const govde = await yanit.json();
      if (!yanit.ok) throw new Error(govde.mesaj || 'Ön değerlendirme kaydedilemedi.');
      setOnFormMesaji(govde.mesaj);
      setOnForm({
        dovme_piercing_mi: false, dovme_tarihi: '', ates_enfeksiyon_mi: false,
        antibiyotik_ilac_mi: false, ameliyat_transfuzyon_mi: false,
        hamilelik_emzirme_mi: false, aciklama: '', onay: false,
      });
      await yenile();
    } catch (err) { setHata(err.message); }
  };

  if (yukleniyor && !veri) return <main className="bagisci-yukleme">Bağışçı paneli hazırlanıyor…</main>;
  if (hata && !veri) return <main className="bagisci-yukleme"><div className="uyari hata">{hata}</div><button className="buton sade" onClick={cikis}>Giriş ekranına dön</button></main>;
  const profil = veri.profil;
  const uygunluk = veri.uygunluk;
  const ilerleme = Math.min(100, (profil.toplam_puan / Math.max(profil.sonraki_unvan.hedef, 1)) * 100);

  return (
    <div className="bagisci-sayfasi">
      <header className="bagisci-ustbar">
        <div className="marka"><span className="marka-isareti kucuk">KB</span><div><strong>Kan Bankası</strong><small>Bağışçı Paneli</small></div></div>
        <div className="bagisci-ust-kullanici"><div><strong>{oturum?.ad_soyad || `${profil.ad} ${profil.soyad}`}</strong><small>{profil.bagisci_no}</small></div><button className="buton sade" onClick={cikis}>Güvenli çıkış</button></div>
      </header>
      <main className="bagisci-icerik">
        <section className="bagisci-hero">
          <div><p className="ust-etiket">Hoş geldiniz</p><h1>{profil.ad} {profil.soyad}</h1><p>Kendi uygunluk, bağış geçmişi, puan ve çağrı bilgilerinizi güvenli biçimde görüntülüyorsunuz.</p></div>
          <div className="bagisci-kimlik"><span className="kan-rozet buyuk">{profil.grup_adi}</span><b>{profil.unvan} Bağışçı</b><small>{profil.toplam_puan} toplam puan</small></div>
        </section>

        {hata && <div className="uyari hata">{hata}</div>}
        <section className="metrik-grid bagisci-metrikler">
          <Metrik etiket="Toplam puan" deger={profil.toplam_puan} birim="puan" renk="lacivert" />
          <Metrik etiket="Unvan" deger={profil.unvan} birim="bağışçı" renk="turuncu" />
          <Metrik etiket="Bağış durumu" deger={uygunluk.durum} birim={uygunluk.kalan_gun ? `${uygunluk.kalan_gun} gün` : 'bugün'} renk={uygunluk.uygun_mu ? 'yesil' : 'kirmizi'} />
          <Metrik etiket="Bağış sayısı" deger={veri.bagislar.length} birim="kayıt" renk="yesil" />
        </section>

        <section className="iki-kolon bagisci-ana-grid">
          <article className={`panel uygunluk-buyuk ${uygunluk.uygun_mu ? 'uygun' : 'bekleme'}`}>
            <p className="ust-etiket">Uygunluk durumum</p><div className="uygunluk-baslik"><Durum durum={uygunluk.durum} /><h2>{uygunluk.uygun_mu ? 'Bağış için yeniden değerlendirilebilirsiniz' : `${uygunluk.kalan_gun ?? '—'} gün bekleme`}</h2></div>
            <p>{uygunluk.mesaj}</p>
            <div className="detay-grid"><div><span>Son bağış</span><b>{tarihYaz(uygunluk.son_bagis_tarihi)}</b></div><div><span>En erken tarih</span><b>{tarihYaz(uygunluk.sonraki_uygun_tarih)}</b></div><div><span>Cinsiyet kuralı</span><b>{uygunluk.bagis_araligi_gun} gün</b></div><div><span>Kan grubu</span><b>{profil.grup_adi}</b></div></div>
            {uygunluk.nedenler.map((neden) => <div className="neden-satiri" key={neden}>• {neden}</div>)}
            <small className="tibbi-not">{veri.tibbi_uyari}</small>
          </article>
          <article className="panel puan-durumu">
            <p className="ust-etiket">Bağışçı puanlama</p><div className="puan-buyuk"><strong>{profil.toplam_puan}</strong><span>{profil.unvan}</span></div>
            <div className="puan-ilerleme"><i style={{ width: `${ilerleme}%` }} /></div>
            <p>{profil.sonraki_unvan.kalan > 0 ? `${profil.sonraki_unvan.unvan} unvanına ${profil.sonraki_unvan.kalan} puan kaldı.` : 'En yüksek unvana ulaştınız.'}</p>
            <div className="puan-kazan"><span>Her standart bağış <b>+100</b></span><span>Kritik stok grubu <b>+50 bonus</b></span></div>
            <button className={`bildirim-anahtari ${profil.bildirim_izni ? 'acik' : ''}`} onClick={bildirimDegistir}><i /><span><b>Acil çağrı bildirimleri</b><small>{profil.bildirim_izni ? 'Açık — uygun çağrılarda listelenirsiniz' : 'Kapalı — çağrı listesine alınmazsınız'}</small></span></button>
          </article>
        </section>

        <section className="panel on-degerlendirme-paneli">
          <div className="panel-basligi">
            <div><p className="ust-etiket">Bağış öncesi kontrol</p><h3>Sağlık ön değerlendirme formu</h3><p>Dürüst yanıtlarınız yönetici ekranındaki uygunluk kontrolüne yansır.</p></div>
            <span className="aciklama-etiketi">Hekim onayı gerekir</span>
          </div>
          <div className="uyari bilgi"><strong>Önemli:</strong> Dövme ve sağlık yanıtları bağışa uygunluğu etkiler. Kanın depoda kalma süresi ise bağışçı yanıtlarına göre değil; Tam Kan, Eritrosit veya Trombosit bileşenine göre hesaplanır.</div>
          {veri.on_degerlendirme && <div className={`son-form ${veri.on_degerlendirme.inceleme_gerekli ? 'inceleme' : ''}`}><b>Son form: {veri.on_degerlendirme.kayit_tarihi}</b><span>{veri.on_degerlendirme.inceleme_gerekli ? 'Hekim incelemesi gereken yanıt bulunuyor.' : 'Bildirilen ek risk yanıtı yok.'}</span></div>}
          {onFormMesaji && <div className="uyari basari">{onFormMesaji}</div>}
          <form className="on-degerlendirme-grid" onSubmit={onDegerlendirmeKaydet}>
            <label>Son 12 ay içinde dövme veya piercing yaptırdınız mı?
              <select value={onForm.dovme_piercing_mi ? 'evet' : 'hayir'} onChange={(e) => setOnForm({ ...onForm, dovme_piercing_mi: e.target.value === 'evet', dovme_tarihi: e.target.value === 'evet' ? onForm.dovme_tarihi : '' })}><option value="hayir">Hayır</option><option value="evet">Evet</option></select>
            </label>
            {onForm.dovme_piercing_mi && <label>Dövme / piercing tarihi<input type="date" value={onForm.dovme_tarihi} onChange={(e) => setOnForm({ ...onForm, dovme_tarihi: e.target.value })} required /></label>}
            <label>Şu anda ateş veya enfeksiyon belirtiniz var mı?
              <select value={onForm.ates_enfeksiyon_mi ? 'evet' : 'hayir'} onChange={(e) => setOnForm({ ...onForm, ates_enfeksiyon_mi: e.target.value === 'evet' })}><option value="hayir">Hayır</option><option value="evet">Evet</option></select>
            </label>
            <label>Antibiyotik veya düzenli ilaç kullanıyor musunuz?
              <select value={onForm.antibiyotik_ilac_mi ? 'evet' : 'hayir'} onChange={(e) => setOnForm({ ...onForm, antibiyotik_ilac_mi: e.target.value === 'evet' })}><option value="hayir">Hayır</option><option value="evet">Evet</option></select>
            </label>
            <label>Son dönemde ameliyat veya kan nakli geçirdiniz mi?
              <select value={onForm.ameliyat_transfuzyon_mi ? 'evet' : 'hayir'} onChange={(e) => setOnForm({ ...onForm, ameliyat_transfuzyon_mi: e.target.value === 'evet' })}><option value="hayir">Hayır</option><option value="evet">Evet</option></select>
            </label>
            {profil.cinsiyet === 'Kadın' && <label>Hamilelik veya emzirme durumunuz var mı?
              <select value={onForm.hamilelik_emzirme_mi ? 'evet' : 'hayir'} onChange={(e) => setOnForm({ ...onForm, hamilelik_emzirme_mi: e.target.value === 'evet' })}><option value="hayir">Hayır</option><option value="evet">Evet</option></select>
            </label>}
            <label className="tam">Eklemek istediğiniz sağlık açıklaması<input value={onForm.aciklama} onChange={(e) => setOnForm({ ...onForm, aciklama: e.target.value })} placeholder="Varsa kısa açıklama" /></label>
            <label className="tam onay-satiri"><input type="checkbox" checked={onForm.onay} onChange={(e) => setOnForm({ ...onForm, onay: e.target.checked })} /><span>Bilgilerin doğru olduğunu ve kesin kararın muayene ile hekim tarafından verileceğini onaylıyorum.</span></label>
            <button className="buton birincil tam" disabled={!onForm.onay}>Ön değerlendirmeyi kaydet</button>
          </form>
        </section>

        <section className="iki-kolon bagisci-alt-grid">
          <article className="panel tablo-panel">
            <div className="panel-basligi"><div><h3>Bağış geçmişim</h3><p>Yalnızca size ait kayıtlar</p></div><span className="aciklama-etiketi">Kişisel veri</span></div>
            <div className="tablo-kapsayici"><table><thead><tr><th>Tarih</th><th>Bileşen</th><th>Ünite</th><th>Kazanılan puan</th></tr></thead><tbody>{veri.bagislar.map((b) => <tr key={b.id}><td>{tarihYaz(b.bagis_tarihi)}</td><td>{b.bilesen_turu}</td><td>{b.unite_sayisi}</td><td><strong>+{b.kazanilan_puan}</strong></td></tr>)}</tbody></table></div>
          </article>
          <article className="panel">
            <div className="panel-basligi dar"><div><h3>Acil kan çağrıları</h3><p>Sizin kan grubunuza ait aktif duyurular</p></div></div>
            <div className="cagri-listesi">{veri.acil_cagrilar.length ? veri.acil_cagrilar.map((c) => <div className="cagri-karti" key={c.id}><span className="kan-rozet">{c.grup_adi}</span><div><b>{c.aciklama}</b><small>{tarihYaz(c.olusturma_tarihi)}</small></div></div>) : <p className="soluk">Şu anda kan grubunuza ait aktif çağrı yok.</p>}</div>
          </article>
        </section>
      </main>
    </div>
  );
}

function Metrik({ etiket, deger, birim, renk }) {
  return <article className={`metrik ${renk}`}><span>{etiket}</span><div><strong>{deger}</strong><small>{birim}</small></div></article>;
}

function Durum({ durum }) {
  return <span className={`durum ${durumSinifi(durum)}`}>{durum}</span>;
}

export default App;
