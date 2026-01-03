"""
FastAPI application for XML Diploma Generation Service.
Converts pivot tables to CyberDiploma XML format.
"""

import io
import logging
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, status, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from .xml_generator import DiplomaXMLGenerator
from urllib.parse import quote
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="XML Diploma Generator Service",
    description="Converts student pivot tables to CyberDiploma XML format",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    curriculum: UploadFile = File(..., description="Curriculum file (optional)"),
    # curriculum: Optional[UploadFile] = File(None, description="Curriculum file (optional)"),
    
    # Configuration parameters
    edu_term: str = Form(..., description="Education term (e.g., '4 года')"),
    qualification: str = Form(..., description="Qualification (e.g., 'бакалавр')"),
    edu_form: str = Form(..., description="Education form (e.g., 'очная')"),
    speciality: str = Form(..., description="Speciality code and name"),
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
        # Validate file types
        for file, name in [(pivot_table, "pivot_table"), (student_info, "student_info")]:
            if not file.filename.endswith('.xlsx'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{name} must be an Excel file (.xlsx)"
                )
        
        # Read files
        logger.info(f"Reading pivot table: {pivot_table.filename}")
        pivot_bytes = await pivot_table.read()
        
        logger.info(f"Reading student info: {student_info.filename}")
        student_bytes = await student_info.read()
        
        curriculum_bytes = await curriculum.read()
        # curriculum_bytes = None
        # if curriculum:
        #     logger.info(f"Reading curriculum: {curriculum.filename}")
        #     curriculum_bytes = await curriculum.read()
        
        # Parse pivot table
        df_disciplines = pd.read_excel(
            io.BytesIO(pivot_bytes),
            header=0,
            engine='openpyxl'
        )
        df_disciplines.dropna(inplace=True, axis=0, how='all')
        
        # Parse student info
        df_students = pd.read_excel(
            io.BytesIO(student_bytes),
            engine='openpyxl'
        )
        
        # Create configuration
        config = {
            'edu_term': edu_term,
            'qualification': qualification,
            'edu_form': edu_form,
            'speciality': speciality,
            'edu_progr_vol': edu_progr_vol,
            'edu_progr_vol_contact': edu_progr_vol_contact,
            'pract_total_z_e': pract_total_z_e,
            'gia_z_e': gia_z_e,
            'gek_chairman': gek_chairman,
            'state_exam_credits': state_exam_credits
        }
        
        # Initialize generator
        generator = DiplomaXMLGenerator(config)
        
        # Parse curriculum if provided
        df_plan = generator.parse_curriculum(curriculum_bytes)
        
        # Match credits from curriculum
        if not df_plan.empty:
            df_disciplines = generator.match_credits(df_disciplines, df_plan)
        
        # Add postfixes to discipline names
        df_disciplines = generator.add_discipline_postfixes(df_disciplines)
        
        # Fix state exam credits
        df_disciplines = generator.fix_state_exam_credits(df_disciplines)
        
        # Add credits to discipline names
        df_disciplines['Дисциплины'] = (
            df_disciplines['Дисциплины'] + '_' + 
            df_disciplines['зачЕд'].astype(str)
        )
        df_disciplines.drop(columns=['зачЕд'], inplace=True)
        df_disciplines.set_index('Дисциплины', inplace=True)
        
        logger.info("Generating XML")
        
        # Generate XML
        xml_content = generator.generate_xml(df_disciplines, df_students)
        
        # Generate filename
        spec_code = speciality.split(' ')[0]
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
    
    except HTTPException:
        raise
    
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate XML: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)