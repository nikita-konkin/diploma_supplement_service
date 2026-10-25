# python-attestation-engine

Отчёты об аттестации групп кафедры ИТРС по данным портала РИТМ. Отдельный компонент сайта:
страница `/attestation` со своим входом, через шлюз `java-api` (`TkAttestation`).

- `app/main.py` — маршруты `/attestation/...`: вход, страница, задачи, скачивание файлов.
- `app/security.py` — хеш пароля сайта, сеансы, ограничение входов, хранилище пароля РИТМ (AES-256-GCM).
- `app/jobs.py` — фоновые задачи: выгрузка идёт минутами, страница опрашивает состояние; файлы удаляются по таймеру.
- `app/static/` — страницы без встроенных скриптов (CSP `script-src 'self'`).
- `reports/` — модули отчёта, те же, что запускаются из командной строки (`make_report.py --att 1`).
  Это копия рабочей папки анализа: правки вносятся там и переносятся сюда целиком.
- `tools/hash_password.py` — хеш для `ATTESTATION_PASSWORD_HASH`.

Локальный запуск без Docker:

```sh
python -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
PYTHONPATH=.:reports ATTESTATION_COOKIE_SECURE=0 ATTESTATION_DATA_DIR=./data \
  ATTESTATION_PASSWORD_HASH='...' .venv/bin/uvicorn app.main:app --port 8002
```

Тесты не обращаются к порталу и не используют реальные данные: `tests/synthetic.py` пишет
выдуманные выгрузки в формате РИТМ.
