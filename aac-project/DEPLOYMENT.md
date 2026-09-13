# DEPLOYMENT (Backend CLI-first)

Panduan deployment untuk mode backend-only (tanpa ketergantungan frontend).

## Komponen runtime

- `backend` (FastAPI)
- `worker` (Celery worker)
- `beat` (Celery scheduler)
- `redis`
- `postgres` (atau MySQL external)
- `flower` (opsional monitoring queue)

## Opsi A — Docker Compose (disarankan)

1) Siapkan environment:

```bash
cd /opt/aac-project
cp backend/.env.example backend/.env
```

2) Isi nilai penting di `.env`:
- `DATABASE_URL`
- `REDIS_URL`
- `REDIS_CELERY_BROKER`
- `REDIS_CELERY_BACKEND`
- `FERNET_KEY`
- `JWT_SECRET_KEY`
- `LDAP_ENABLED=false` (jika tidak pakai LDAP)

3) Jalankan stack:

```bash
docker compose up -d postgres redis backend worker beat flower
```

4) Inisialisasi DB:

```bash
docker compose exec backend python -m app.cli init-db
```

5) Verifikasi service:

```bash
docker compose ps
curl http://localhost:8000/health
```

## Opsi B — Proses lokal (tanpa Docker)

```bash
cd backend
python -m pip install -r requirements.txt
python -m app.cli init-db
python -m celery -A app.workers.celery_app worker --loglevel=info -Q normal,low --pool=solo
```

(opsional terminal lain)

```bash
python -m celery -A app.workers.celery_app beat --loglevel=info
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Health checks

- API: `GET /health`
- Readiness: `GET /health/ready`
- Flower: `http://localhost:5555`

## Operasional

- Skalakan worker sesuai beban queue.
- Pantau error dari log worker + Flower.
- Simpan secret hanya di `.env` (jangan commit).

## Hardening minimum production

- Ganti semua credential default DB/Redis/JWT.
- Batasi akses port DB/Redis dari internet publik.
- Gunakan TLS via reverse proxy di depan FastAPI.
- Aktifkan alert untuk kegagalan task beruntun.
