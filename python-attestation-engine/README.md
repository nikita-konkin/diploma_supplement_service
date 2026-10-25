# python-attestation-engine

Отчёты об аттестации групп кафедры по данным портала РИТМ. Отдельный компонент сайта:
страница `/attestation` через шлюз `java-api` (`TkAttestation`). Вход — учётной записью РИТМ.

- `app/main.py` — маршруты `/attestation/...`: вход, страница, списки факультетов, кафедр и групп, задачи, файлы.
- `app/portal.py` — всё, что сервис спрашивает у портала; в тестах заменяется подделкой.
- `app/security.py` — сеансы (в памяти, с сеансом портала вместо пароля) и ограничение входов.
- `app/presets.py` — запомненные направления групп каждой кафедры (`departments.json` в `ATTESTATION_DATA_DIR`).
- `app/jobs.py` — фоновые задачи: выгрузка идёт минутами, страница опрашивает состояние; файлы удаляются по таймеру.
- `app/static/` — страницы без встроенных скриптов (CSP `script-src 'self'`).
- `reports/` — модули отчёта, те же, что запускаются из командной строки (`make_report.py --att 1`).
  Это копия рабочей папки анализа: правки вносятся там и переносятся сюда целиком.
  Кафедра, факультет и заведующий для шапки берутся из `department.json` в папке аттестации; без него — ИТРС.

Локальный запуск без Docker:

```sh
python -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
PYTHONPATH=.:reports ATTESTATION_COOKIE_SECURE=0 ATTESTATION_DATA_DIR=./data \
  .venv/bin/uvicorn app.main:app --port 8002
```

Тесты не обращаются к порталу и не используют реальные данные: `tests/synthetic.py` пишет
выдуманные выгрузки в формате РИТМ.
