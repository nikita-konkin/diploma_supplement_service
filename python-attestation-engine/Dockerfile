FROM python:3.12-bookworm AS app

WORKDIR /app

# Liberation fonts stand in for Times New Roman in charts and reports;
# LibreOffice Writer without the GUI turns the DOCX reports into PDF (reports/pdf_export.py)
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gosu \
    fonts-liberation \
    libreoffice-writer-nogui \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY reports/ ./reports/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# reports/ holds the command-line modules (make_report, ritm_fetch, ...) imported by name
ENV PYTHONPATH=/app:/app/reports \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# One worker: sessions and jobs live in this process's memory
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]

# The image is built only when the tests pass (B-20).
FROM app AS test
COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
RUN python -m pytest -q -p no:cacheprovider && touch /tests-passed

FROM app
COPY --from=test /tests-passed /tests-passed
