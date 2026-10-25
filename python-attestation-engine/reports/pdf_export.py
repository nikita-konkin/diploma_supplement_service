"""PDF из готовых DOCX через LibreOffice: картинки сжимаются ровно настолько, чтобы файл не
превышал MAX_BYTES.

Диаграммы подробного отчёта со штриховкой сжимаются плохо (47 страниц и 28 диаграмм — 12 МБ без
сжатия), поэтому качество подбирается по лестнице: от лучшего к худшему, первая ступень, которая
укладывается в предел. Справка без картинок укладывается с первой ступени, за одну конвертацию.
Теги доступности не пишутся: LibreOffice размечает ими каждую ячейку таблицы, и справка с
приложением вырастает с 0,2 до 1,3 МБ.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 2_000_000  # «не больше 2 МБ» при любом способе счёта: и в Windows, и в macOS
# (dpi картинок, качество JPEG); размер файла убывает от ступени к ступени
LADDER = [(200, 85), (150, 80), (150, 70), (150, 60), (140, 60), (120, 70), (120, 60), (100, 60), (90, 50)]
TIMEOUT = 300
MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


class PdfError(RuntimeError):
    pass


@dataclass(frozen=True)
class PdfResult:
    path: Path
    size: int
    dpi: int
    quality: int
    images: bool = True

    @property
    def fits(self) -> bool:
        return self.size <= MAX_BYTES

    def describe(self) -> str:
        size = f"{self.size / 1_000_000:.1f} МБ" if self.size >= 100_000 else f"{self.size // 1000} КБ"
        return f"{self.path.name}: {size.replace('.', ',')}" + (f", картинки {self.dpi} dpi" if self.images else "")


def find_soffice() -> str | None:
    """LibreOffice: SOFFICE из окружения, soffice в PATH или приложение macOS."""
    for candidate in (os.environ.get("SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice")):
        if candidate:
            return candidate
    return MAC_SOFFICE if Path(MAC_SOFFICE).exists() else None


def filter_options(dpi: int, quality: int) -> str:
    return json.dumps({
        "ReduceImageResolution": {"type": "boolean", "value": "true"},
        "MaxImageResolution": {"type": "long", "value": str(dpi)},
        "Quality": {"type": "long", "value": str(quality)},
        "UseLosslessCompression": {"type": "boolean", "value": "false"},
        "UseTaggedPDF": {"type": "boolean", "value": "false"},
    })


def convert(soffice: str, docx: Path, out_dir: Path, profile: Path, dpi: int, quality: int) -> Path:
    """Одна конвертация; свой профиль LibreOffice — чтобы не мешать запущенному офису и соседним задачам."""
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore",
        "--convert-to", f"pdf:writer_pdf_Export:{filter_options(dpi, quality)}",
        "--outdir", str(out_dir), str(docx),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise PdfError(f"LibreOffice не успел за {TIMEOUT} с: {docx.name}") from exc
    pdf = out_dir / f"{docx.stem}.pdf"
    if completed.returncode != 0 or not pdf.exists():
        raise PdfError(f"LibreOffice не собрал PDF из {docx.name}: {(completed.stderr or completed.stdout).strip()[:300]}")
    return pdf


def export_pdf(docx: Path, pdf: Path | None = None, soffice: str | None = None, converter=convert) -> PdfResult:
    """PDF рядом с DOCX (или в pdf) с лучшим качеством картинок, которое укладывается в MAX_BYTES.

    Если не укладывается даже последняя ступень, остаётся самый маленький вариант: fits у результата
    тогда False, и вызывающий решает, что сказать пользователю.
    """
    soffice = soffice or find_soffice()
    if soffice is None:
        raise PdfError("не найден LibreOffice (soffice)")
    pdf = pdf or docx.with_suffix(".pdf")
    with tempfile.TemporaryDirectory(prefix="pdf-export-") as temporary:
        work = Path(temporary)
        profile = work / "profile"
        attempts: dict[int, PdfResult] = {}

        def attempt(step: int) -> PdfResult:
            if step not in attempts:
                dpi, quality = LADDER[step]
                made = converter(soffice, docx, work / str(step), profile, dpi, quality)
                attempts[step] = PdfResult(made, made.stat().st_size, dpi, quality)
            return attempts[step]

        # первая ступень — почти всегда хватает; иначе двоичный поиск первой подходящей
        if attempt(0).fits:
            best = attempts[0]
        else:
            low, high = 1, len(LADDER) - 1
            while low < high:
                middle = (low + high) // 2
                if attempt(middle).fits:
                    high = middle
                else:
                    low = middle + 1
            best = attempt(low)
        shutil.move(str(best.path), pdf)
    return PdfResult(pdf, pdf.stat().st_size, best.dpi, best.quality, images=b"/Subtype/Image" in pdf.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF из DOCX не больше 2 МБ (нужен LibreOffice).")
    parser.add_argument("docx", nargs="+", help="Файлы DOCX")
    args = parser.parse_args()
    for name in args.docx:
        try:
            result = export_pdf(Path(name).resolve())
        except PdfError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1
        print(result.describe() + ("" if result.fits else " — больше 2 МБ даже при самом сильном сжатии"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
