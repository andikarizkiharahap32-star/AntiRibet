# QUICKSTART (CLI-only)

Panduan cepat menjalankan AAC dalam mode backend + CLI.

## 1) Prasyarat

- Python 3.11+
- Redis aktif di `127.0.0.1:6379`
- MySQL 8+ atau PostgreSQL 14+

## 2) Setup backend

```bash
cd "C:/discord gmail/AntiRibet/aac-project/backend"
copy .env.example .env
python -m pip install -r requirements.txt
```

## 3) Konfigurasi minimal `.env`

Wajib isi:
- `DATABASE_URL`
- `REDIS_URL`
- `REDIS_CELERY_BROKER`
- `REDIS_CELERY_BACKEND`
- `FERNET_KEY`

Jika tidak pakai LDAP:
- `LDAP_ENABLED=false`

Contoh lokal MySQL:

```env
DATABASE_URL=mysql://root:@127.0.0.1:3306/aac_db
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_CELERY_BROKER=redis://127.0.0.1:6379/2
REDIS_CELERY_BACKEND=redis://127.0.0.1:6379/3
LDAP_ENABLED=false
```

## 4) Inisialisasi database

```bash
python -m app.cli init-db
```

## 5) Jalankan worker

Terminal 1:

```bash
python -m celery -A app.workers.celery_app worker --loglevel=info -Q normal,low --pool=solo
```

## 6) Jalankan job pertama

Terminal 2:

```bash
python -m app.cli create --platform discord --count 1
python -m app.cli list-jobs
python -m app.cli stats
python -m app.cli status --job-id <JOB_ID>
```

## 7) Ekspor hasil

```bash
python -m app.cli export --platform discord --format csv --output accounts.csv
```

## 8) Validasi cepat

```bash
python -m app.cli --help
python -m app.cli list-jobs
python -m app.cli stats
```

## Docker alternative

Dari root `aac-project/`:

```bash
docker compose up -d postgres redis backend worker beat flower
docker compose ps
```
