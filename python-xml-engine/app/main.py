"""
FastAPI application for XML Diploma Generation Service.
Converts pivot tables to CyberDiploma XML format.
"""

import logging
import time
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, status, Form
from fastapi.responses import Response

from .excel import WorkbookError, open_workbook
from .xml_generator import DataValidationError, DiplomaXMLGenerator
from .logging_config import configure_logging
from urllib.parse import quote
import re

configure_logging("python-xml-engine")
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="XML Diploma Generator Service",
    description="Converts student pivot tables to CyberDiploma XML format",
    version="1.0.0"
)

# No CORS: only the Java gateway calls this service, over the compose network.


@app.middleware("http")
async def log_request(request: Request, call_next):
    """Record every completed HTTP request in the event log."""
    started = time.monotonic()
    response = await call_next(request)
    logger.info(
        "%s %s -> %s in %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        time.monotonic() - started,
    )
    return response


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "XML Diploma Generator",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/generate-xml")
async def generate_xml(
    pivot_table: UploadFile = File(..., description="Pivot table from previous service"),
    student_info: UploadFile = File(..., description="Student information file"),
    # curriculum: UploadFile = File(..., description="Curriculum file (optional)"),
    # curriculum: Optional[UploadFile] = File(None, description="Curriculum file (optional)"),
    
    # Configuration parameters
    edu_term: str = Form(..., description="Education term (e.g., '4 года')"),
    qualification: str = Form(..., description="Qualification (e.g., 'бакалавр')"),
    edu_form: str = Form(..., description="Education form (e.g., 'очная')"),
    direction: Optional[str] = Form(None, description="Direction code and name, e.g. '09.03.02 ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ'"),
    profile: Optional[str] = Form(None, description="Program profile (направленность)"),
    speciality: Optional[str] = Form(None, description="Obsolete: replaced by direction and profile"),
    edu_progr_vol: int = Form(..., description="Program volume in credits"),
    edu_progr_vol_contact: str = Form(..., description="Contact hours (e.g., '3180 ак.час')"),
    pract_total_z_e: int = Form(..., description="Total practice credits"),
    gia_z_e: int = Form(..., description="State exam credits"),
    gek_chairman: str = Form(..., description="GEK chairman name"),
    state_exam_credits: int = Form(6, description="State exam credits (manual)")
):
    """
    Generate XML diploma file from pivot table and student data.
    
    Args:
        pivot_table: Excel pivot table file
        student_info: Excel file with student information
        curriculum: Optional curriculum file (if None, uses manual entry)
        ... configuration parameters
        
    Returns:
        XML file for diploma application
    """
    logger.info("Received XML generation request")
    
    try:
        if direction is None and speciality is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Форма устарела: вместо «Код и название специальности» нужно "
                    "указать направление подготовки и профиль. Обновите страницу "
                    "(Ctrl+F5) и заполните оба поля."
                )
            )

        # Both .xlsx and old .xls workbooks are accepted, by content
        df_disciplines = open_workbook(
            await pivot_table.read(), "Сводная таблица"
        ).parse(0, header=0)
        df_disciplines.dropna(inplace=True, axis=0, how='all')
        if 'Дисциплины' not in df_disciplines.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Сводная таблица: на первом листе нет колонки «Дисциплины». "
                    "Загрузите сводную, построенную на вкладке «Сводная таблица»."
                )
            )
        df_students = open_workbook(
            await student_info.read(), "Сведения о студентах"
        ).parse(0)
        
        # Create configuration
        config = {
            'edu_term': edu_term,
            'qualification': qualification,
            'edu_form': edu_form,
            'direction': direction,
            'profile': profile,
            'edu_progr_vol': edu_progr_vol,
            'edu_progr_vol_contact': edu_progr_vol_contact,
            'pract_total_z_e': pract_total_z_e,
            'gia_z_e': gia_z_e,
            'gek_chairman': gek_chairman,
            'state_exam_credits': state_exam_credits
        }
        
        # Initialize generator
        generator = DiplomaXMLGenerator(config)

        df_disciplines.set_index('Дисциплины', inplace=True)
        
        logger.info("Generating XML")
        
        # Generate XML
        xml_content = generator.generate_xml(df_disciplines, df_students)
        
        # Generate filename
        spec_code = generator.direction_code
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{spec_code}_{qualification}_{edu_form}_{timestamp}.xml"
        
        logger.info(f"Returning XML: {filename}")

        # Create ASCII-safe fallback filename by replacing non-ASCII with '_'
        ascii_filename = re.sub(r"[^\x00-\x7F]", "_", filename)
        if not ascii_filename:
            ascii_filename = "output.xml"

        # RFC5987 encoded filename* for UTF-8 filenames
        quoted_filename = quote(filename)
        content_disp = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quoted_filename}"

        return Response(
            content=xml_content.encode('utf-8'),
            media_type="application/xml",
            headers={
                "Content-Disposition": content_disp
            }
        )
    
    except HTTPException as error:
        logger.warning("XML request rejected: %s", error.detail)
        raise
    
    except DataValidationError as e:
        logger.warning("XML request has %d data problems", len(e.problems))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except WorkbookError as e:
        logger.warning("XML request rejected: unusable input workbook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except ValueError as e:
        logger.warning("XML request rejected: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка в исходных данных: {str(e)}"
        )
    
    except Exception as e:
        logger.exception("Processing error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сформировать XML: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
