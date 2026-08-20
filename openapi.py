"""
API'nin OpenAPI 3.0 şeması. Elle yazılmış bir Python sözlüğü olarak tutuluyor
(harici bir kütüphane - flasgger, flask-smorest vb. - gerektirmiyor), çünkü
bu proje ölçeğinde ekstra bir bağımlılık eklemek gereksiz karmaşıklık olurdu.
app.py bunu /api/openapi.json üzerinden JSON olarak sunar, Swagger UI da
bu JSON'u okuyup interaktif dokümantasyon sayfasını (/docs) oluşturur.
"""

BEARER_GUVENLIK = [{"bearerAuth": []}]

OPENAPI_SEMA = {
    "openapi": "3.0.0",
    "info": {
        "title": "Akıllı Hastane Kan Bankası API",
        "version": "1.0.0",
        "description": "Kan bankası stok yönetimi, bağışçı eşleştirme ve acil çağrı sistemi API'si."
    },
    "servers": [{"url": "http://127.0.0.1:5000"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Giriş sonrası alınan token buraya yazılır (sadece token, 'Bearer' kelimesi olmadan)."
            }
        }
    },
    "paths": {
        "/api/health": {
            "get": {
                "summary": "API'nin ayakta olup olmadığını kontrol eder",
                "responses": {"200": {"description": "API çalışıyor"}}
            }
        },
        "/api/auth/giris": {
            "post": {
                "summary": "Kullanıcı adı/şifre ile giriş yapar, token döner",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kullanici_adi": {"type": "string"},
                            "sifre": {"type": "string"}
                        },
                        "required": ["kullanici_adi", "sifre"]
                    }}}
                },
                "responses": {
                    "200": {"description": "Giriş başarılı, token döner"},
                    "401": {"description": "Kullanıcı adı veya şifre hatalı"}
                }
            }
        },
        "/api/auth/cikis": {
            "post": {
                "summary": "Mevcut token'ı geçersiz kılar",
                "security": BEARER_GUVENLIK,
                "responses": {"200": {"description": "Çıkış başarılı"}}
            }
        },
        "/api/stoklar/kritik": {
            "get": {
                "summary": "Kritik eşiğin altındaki/eşit kan gruplarını listeler",
                "security": BEARER_GUVENLIK,
                "responses": {"200": {"description": "Kritik stok listesi"}}
            }
        },
        "/api/stoklar/dinamik-kritik": {
            "get": {
                "summary": "Tüketim hızına göre hesaplanan dinamik eşiğe göre kritik stokları listeler",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "guvenlik_gun", "in": "query", "schema": {"type": "integer", "default": 5}}
                ],
                "responses": {"200": {"description": "Dinamik kritik stok listesi"}}
            }
        },
        "/api/stoklar/tahmin": {
            "get": {
                "summary": "Tüm kan grupları için stok bitiş tahmini",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "gun_sayisi", "in": "query", "schema": {"type": "integer", "default": 30}}
                ],
                "responses": {"200": {"description": "Tahmin raporu"}}
            }
        },
        "/api/stoklar/tahmin/{kan_grubu_id}": {
            "get": {
                "summary": "Tek bir kan grubu için stok bitiş tahmini",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kan_grubu_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Tahmin"},
                    "404": {"description": "Kan grubu bulunamadı"}
                }
            }
        },
        "/api/stoklar/uyumlu/{kan_grubu_adi}": {
            "get": {
                "summary": "Bir kan grubu için tıbbi olarak uyumlu alternatif stokları listeler",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kan_grubu_adi", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "Uyumlu stok listesi"}}
            }
        },
        "/api/stoklar/skt-risk": {
            "get": {
                "summary": "Son kullanma tarihine göre risk altındaki kan torbalarını listeler",
                "security": BEARER_GUVENLIK,
                "responses": {"200": {"description": "SKT risk raporu"}}
            }
        },
        "/api/stoklar/cikis": {
            "post": {
                "summary": "Stoktan kan çıkışı yapar (hasta kullanımı)",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kan_grubu_id": {"type": "integer"},
                            "adet": {"type": "integer"}
                        },
                        "required": ["kan_grubu_id", "adet"]
                    }}}
                },
                "responses": {
                    "200": {"description": "Çıkış başarılı"},
                    "400": {"description": "Yetersiz stok ya da eksik alan"}
                }
            }
        },
        "/api/bagiscilar/uygun/{kan_grubu_id}": {
            "get": {
                "summary": "Bir kan grubu için bağış yapmaya uygun bağışçıları listeler",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kan_grubu_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "gece", "in": "query", "schema": {"type": "boolean", "default": False}}
                ],
                "responses": {"200": {"description": "Uygun bağışçı listesi"}}
            }
        },
        "/api/bagiscilar/uygunluk/{kullanici_id}": {
            "get": {
                "summary": "[SADECE ADMIN] Bir kullanıcının bağış uygunluğunu (sağlık engeli dahil) kontrol eder",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kullanici_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "gece_cagrisi", "in": "query", "schema": {"type": "boolean", "default": False}}
                ],
                "responses": {
                    "200": {"description": "Uygunluk sonucu"},
                    "403": {"description": "Bu endpoint sadece admin rolüne açık"}
                }
            }
        },
        "/api/bagiscilar/puan/{bagisci_id}": {
            "get": {
                "summary": "Bir bağışçının puan ve rozet bilgisini döner",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "bagisci_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Puan ve rozet"}}
            }
        },
        "/api/bagiscilar/bagis-ekle": {
            "post": {
                "summary": "Yeni bir bağış kaydı ekler, stoğu 1 artırır",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kullanici_id": {"type": "integer"},
                            "kan_grubu_id": {"type": "integer"}
                        },
                        "required": ["kullanici_id", "kan_grubu_id"]
                    }}}
                },
                "responses": {"200": {"description": "Bağış eklendi"}}
            }
        },
        "/api/acil-cagri/{kan_grubu_id}": {
            "get": {
                "summary": "Bir kan grubu için basit acil çağrı listesi (son bağış tarihine göre sıralı)",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kan_grubu_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Acil çağrı listesi"}}
            }
        },
        "/api/acil-cagri/{kan_grubu_id}/agirlikli": {
            "get": {
                "summary": "Ağırlıklı öncelik skoruna göre sıralanmış acil çağrı listesi",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "kan_grubu_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "gece_cagrisi", "in": "query", "schema": {"type": "boolean", "default": False}}
                ],
                "responses": {"200": {"description": "Skorlu acil çağrı listesi"}}
            }
        },
        "/api/bildirim/acil-cagri-gonder": {
            "post": {
                "summary": "Bir bağışçıya acil kan ihtiyacı e-postası gönderir",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kullanici_id": {"type": "integer"},
                            "kan_grubu_adi": {"type": "string"}
                        },
                        "required": ["kullanici_id", "kan_grubu_adi"]
                    }}}
                },
                "responses": {
                    "200": {"description": "E-posta gönderildi"},
                    "400": {"description": "Eksik alan ya da kullanıcının e-postası yok"},
                    "404": {"description": "Kullanıcı bulunamadı"},
                    "500": {"description": "SMTP hatası"}
                }
            }
        },
        "/api/bagiscilar/ekle": {
            "post": {
                "summary": "Yeni bir bağışçı/kullanıcı kaydı oluşturur",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kan_grubu_id": {"type": "integer"},
                            "ad": {"type": "string"},
                            "soyad": {"type": "string"},
                            "cinsiyet": {"type": "string"},
                            "birim": {"type": "string"},
                            "telefon": {"type": "string"},
                            "eposta": {"type": "string"}
                        },
                        "required": ["kan_grubu_id", "ad", "soyad", "cinsiyet", "birim", "telefon"]
                    }}}
                },
                "responses": {
                    "200": {"description": "Bağışçı eklendi"},
                    "400": {"description": "Eksik alan ya da telefon zaten kayıtlı"}
                }
            }
        },
        "/api/stoklar/giris": {
            "post": {
                "summary": "[SADECE ADMIN] Bağış dışı elle stok girişi (transfer, kampanya vb.)",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kan_grubu_id": {"type": "integer"},
                            "adet": {"type": "integer"}
                        },
                        "required": ["kan_grubu_id", "adet"]
                    }}}
                },
                "responses": {
                    "200": {"description": "Stok girişi yapıldı"},
                    "400": {"description": "Eksik/geçersiz alan"},
                    "403": {"description": "Sadece admin"}
                }
            }
        },
        "/api/talepler": {
            "get": {
                "summary": "Aktif kan taleplerini listeler",
                "security": BEARER_GUVENLIK,
                "responses": {"200": {"description": "Aktif talep listesi"}}
            },
            "post": {
                "summary": "Bir birim adına yeni kan talebi oluşturur",
                "security": BEARER_GUVENLIK,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "kan_grubu_id": {"type": "integer"},
                            "talep_eden_birim": {"type": "string"}
                        },
                        "required": ["kan_grubu_id", "talep_eden_birim"]
                    }}}
                },
                "responses": {"200": {"description": "Talep oluşturuldu"}}
            }
        },
        "/api/talepler/{talep_id}/kapat": {
            "post": {
                "summary": "[SADECE ADMIN] Bir talebi 'karşılandı' olarak işaretler",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "talep_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Talep kapatıldı"},
                    "404": {"description": "Talep bulunamadı"}
                }
            }
        },
        "/api/audit/gecmis": {
            "get": {
                "summary": "[SADECE ADMIN] Sistem işlem geçmişini (audit trail) listeler",
                "security": BEARER_GUVENLIK,
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100}},
                    {"name": "kullanici_adi", "in": "query", "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "İşlem geçmişi"},
                    "403": {"description": "Bu endpoint sadece admin rolüne açık"}
                }
            }
        }
    }
}