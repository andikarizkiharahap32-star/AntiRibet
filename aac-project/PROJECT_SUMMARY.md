# PROJECT SUMMARY

## Status saat ini

Mode aplikasi telah dipusatkan ke **backend CLI-first**.

Komponen aktif:
- FastAPI backend
- CLI (`python -m app.cli`)
- Celery worker + beat
- Redis broker/backend
- Database (MySQL/PostgreSQL)

Komponen yang tidak lagi menjadi runtime utama:
- Frontend dashboard
- Nginx/Grafana/Prometheus sebagai requirement default

## Pekerjaan yang sudah dibereskan

1. Stabilitas CLI dasar
- `init-db` berjalan dan membuat tabel.
- `list-jobs` dan `stats` berjalan normal.
- `create` berhasil membuat job dan enqueue task saat Redis aktif.

2. Perbaikan model/relasi dan inisialisasi
- Registrasi model saat `init-db` sudah dipastikan.
- Relasi model yang diperlukan CLI sudah sinkron.

3. Perbaikan kompatibilitas local MySQL
- Penyesuaian konfigurasi engine untuk menghindari error ping di aiomysql.
- Perbaikan payload job dari CLI agar field provider konsisten.

4. Compose dirapikan ke backend-only
- Service utama: `postgres`, `redis`, `backend`, `worker`, `beat`, `flower`.
- Dependensi frontend dihapus dari stack default.

5. Dokumentasi disederhanakan
- README, QUICKSTART, DEPLOYMENT, PROJECT_SUMMARY diselaraskan ke mode CLI-only.

## Cara verifikasi cepat

```bash
cd backend
python -m app.cli --help
python -m app.cli init-db
python -m app.cli create --platform discord --count 1
python -m app.cli list-jobs
python -m app.cli stats
```

Jika job tidak diproses:
- pastikan Redis aktif di `127.0.0.1:6379`
- pastikan worker Celery berjalan

## Catatan risiko yang masih ada

- Workflow pembuatan akun real sangat tergantung proxy/captcha/sms provider; tanpa kredensial valid, job bisa selesai dengan gagal.
- Pada environment tertentu, masih bisa muncul warning cleanup event loop dari aiomysql saat interpreter exit (non-fatal untuk command CLI yang sukses).
