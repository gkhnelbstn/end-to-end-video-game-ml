# 🛡️ Veri Koruma Rehberi

Bu dokümanda Docker Compose ile çalışırken PostgreSQL verilerinin korunması için önemli bilgiler yer almaktadır.

## 🔍 Sorun Analizi

`docker-compose up --build` komutu çalıştırıldığında bazen PostgreSQL verileri kaybolabilir. Bunun sebepleri:

1. **Volume'ların yeniden oluşturulması**
2. **Container'ların tamamen yeniden build edilmesi**
3. **Database initialization kodunun yanlış çalışması**

## ✅ Güvenli Komutlar

### Veri Koruyarak Güncelleme
```bash
# Sadece değişen servisleri yeniden build et
docker-compose build backend

# Servisleri yeniden başlat (veriler korunur)
docker-compose up -d
```

### Veri Kaybı Riski Olan Komutlar
```bash
# ⚠️ DİKKAT: Bu komut volume'ları da silebilir
docker-compose down -v

# ⚠️ DİKKAT: Bu komut tüm container'ları sıfırdan oluşturur
docker-compose up --build --force-recreate
```

## 🔧 Önerilen Workflow

### 1. Kod Değişikliği Sonrası
```bash
# Backend'i yeniden build et
docker-compose build backend

# Sadece backend'i yeniden başlat
docker-compose up -d backend
```

### 2. Tüm Sistemi Güncelleme
```bash
# Tüm servisleri durdur (volume'lar korunur)
docker-compose down

# Gerekli servisleri build et
docker-compose build

# Tüm servisleri başlat
docker-compose up -d
```

### 3. Acil Durum - Tamamen Temiz Başlangıç
```bash
# ⚠️ UYARI: Bu komut TÜM VERİLERİ SİLER!
docker-compose down -v
docker system prune -a
docker-compose up --build
```

## 📊 Veri Yedekleme

### PostgreSQL Backup
```bash
# Veritabanını yedekle
docker exec game-insight-db pg_dump -U user -d game_insight_db > backup.sql

# Yedekten geri yükle
docker exec -i game-insight-db psql -U user -d game_insight_db < backup.sql
```

### Volume Backup
```bash
# Volume'u yedekle
docker run --rm -v end-to-end-video-game-ml_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data

# Volume'u geri yükle
docker run --rm -v end-to-end-video-game-ml_postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /
```

## 🔍 Veri Durumu Kontrolü

### Mevcut Volume'ları Listele
```bash
docker volume ls | grep postgres
```

### Container'ların Durumunu Kontrol Et
```bash
docker-compose ps
```

### PostgreSQL Bağlantısını Test Et
```bash
docker exec -it game-insight-db psql -U user -d game_insight_db -c "\dt"
```

### Admin Kullanıcılarını Kontrol Et
```bash
docker exec -it game-insight-db psql -U user -d game_insight_db -c "SELECT * FROM admin_users;"
```

## 🚀 Kod Değişiklikleri

### Database Initialization Güvenliği
`src/backend/main.py` dosyasında database initialization'ı güvenli hale getirdik:

```python
def initialize_database():
    """
    Safely initialize database tables and views.
    Only creates tables if they don't exist, preserving existing data.
    """
    try:
        # Create tables only if they don't exist (this is the default behavior)
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database tables initialized successfully.")
    except Exception as e:
        print(f"⚠️ Error initializing database tables: {e}")
```

Bu fonksiyon:
- Sadece mevcut olmayan tabloları oluşturur
- Mevcut verilere dokunmaz
- Hata durumunda bilgi verir

## 📝 Best Practices

1. **Her zaman `docker-compose down` kullanın** (volume'ları korur)
2. **`docker-compose down -v` kullanmaktan kaçının** (volume'ları siler)
3. **Düzenli backup alın**
4. **Sadece gerekli servisleri yeniden build edin**
5. **Volume durumunu düzenli kontrol edin**

## 🆘 Acil Durum Kurtarma

Eğer veriler kaybolmuşsa:

1. **Volume'ları kontrol edin**: `docker volume ls`
2. **Backup'tan geri yükleyin** (varsa)
3. **Admin kullanıcısını yeniden oluşturun**
4. **Test verilerini yeniden import edin**

## 🔗 Faydalı Komutlar

```bash
# Tüm container'ları durdur
docker-compose down

# Sadece backend'i yeniden başlat
docker-compose restart backend

# Container loglarını görüntüle
docker-compose logs backend

# PostgreSQL shell'e bağlan
docker exec -it game-insight-db psql -U user -d game_insight_db

# Volume içeriğini incele
docker run --rm -v end-to-end-video-game-ml_postgres_data:/data ubuntu ls -la /data
```
