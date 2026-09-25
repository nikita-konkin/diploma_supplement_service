"""Reading uploaded Excel workbooks in both the .xlsx and the old .xls format."""

import io

import pandas as pd

XLSX_SIGNATURE = b'PK\x03\x04'
XLS_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


class WorkbookError(ValueError):
    """The upload cannot be read as a workbook; the message is for the user."""


def open_workbook(content: bytes, title: str) -> pd.ExcelFile:
    """
    Open an uploaded workbook, choosing the reader by the file signature.

    Args:
        content: Uploaded bytes
        title: What the file is, for the error message ("сводная таблица")
    """
    if content.startswith(XLSX_SIGNATURE):
        engine = 'openpyxl'
    elif content.startswith(XLS_SIGNATURE):
        engine = 'xlrd'
    else:
        raise WorkbookError(
            f'{title}: файл не является книгой Excel (.xlsx или .xls). '
            'Откройте его в Excel и сохраните заново.'
        )
    try:
        return pd.ExcelFile(io.BytesIO(content), engine=engine)
    except Exception as error:
        raise WorkbookError(
            f'{title}: не удалось открыть книгу Excel ({error}). '
            'Откройте её в Excel и сохраните заново.'
        ) from error
