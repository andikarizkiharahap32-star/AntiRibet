# AutoAccount Creator (AAC)

Backend CLI-first automation stack untuk job pembuatan akun Discord/Gmail.

## Ringkasan

Repo ini sekarang difokuskan ke backend + CLI + worker queue:
- FastAPI backend (API + health + docs)
- CLI (`python -m app.cli`)
- Celery worker + beat
- Redis + PostgreSQL/MySQL

Frontend dashboard tidak menjadi dependensi runtime utama.

## Struktur penting

- `backend/` -> source code utama
- `backend/app/cli.py` -> command-line interface
- `docker-compose.yml` -> stack backend-only
- `QUICKSTART.md` -> setup cepat lokal
- `DEPLOYMENT.md` -> deployment production

## Quick start lokal

```bash
cd "C:/discord gmail/AntiRibet/aac-project/backend"
copy .env.example .env
python -m pip install -r requirements.txt
python -m app.cli init-db
```

Jalankan worker (terminal terpisah):

```bash
python -m celery -A app.workers.celery_app worker --loglevel=info -Q normal,low --pool=solo
```

Buat job:

```bash
python -m app.cli create --platform discord --count 1
python -m app.cli list-jobs
python -m app.cli status --job-id <JOB_ID>
```

## CLI commands

```bash
python -m app.cli --help
python -m app.cli init-db
python -m app.cli create --platform discord --count 10
python -m app.cli status --job-id <uuid>
python -m app.cli list-jobs
python -m app.cli stats
python -m app.cli export --platform discord --format csv --output accounts.csv
python -m app.cli cancel --job-id <uuid>
```

## Docker compose (backend-only)

Dari folder `aac-project/`:

```bash
docker compose up -d postgres redis backend worker beat flower
docker compose ps
```

Endpoints:
- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/api/v1/docs`
- Flower: `http://localhost:5555`

## Catatan operasional

- Jika `create` tidak diproses, cek Redis di port `6379` dan worker aktif.
- Jika `init-db` gagal, cek `DATABASE_URL` dan pastikan database sudah dibuat.
- Untuk workflow real, lengkapi credential provider (proxy/captcha/sms) di `.env`.
