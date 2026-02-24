"""
XML Generator for Diploma Application (CyberDiploma format).
Converts pivot tables and student data into XML format.
"""

import io
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


def add_element(parent: ET.Element, tag: str, value) -> ET.Element:
    """Add XML element with text value."""
    el = ET.SubElement(parent, tag)
    el.text = str(value) if pd.notna(value) else ''
    return el


class DiplomaXMLGenerator:
    """Generator for CyberDiploma XML files."""
    
    def __init__(self, config: Dict):
        """
        Initialize generator with configuration.
        
        Args:
            config: Dictionary with parameters like edu_term, qualification, etc.
        """
        self.config = config
        self.validate_config()
    
    def validate_config(self):
        """Validate required configuration parameters."""
        required = [
            'edu_term', 'qualification', 'edu_form', 'speciality',
            'edu_progr_vol', 'edu_progr_vol_contact',
            'pract_total_z_e', 'gia_z_e', 'gek_chairman',
            'state_exam_credits'  # Manual value for state exam
        ]
        
        missing = [k for k in required if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config parameters: {missing}")

    
    def generate_xml(
        self,
        df_disciplines: pd.DataFrame,
        df_students: pd.DataFrame
    ) -> str:
        """
        Generate XML file for diploma application.
        
        Args:
            df_disciplines: DataFrame with disciplines and scores
            df_students: DataFrame with student information
            
        Returns:
            XML string
        """
        root = ET.Element("ФайлОбменаКиберДиплом", Версия="3.5.1")
        students_el = ET.SubElement(root, "Студенты")
        
        # Parse student names
        df_students['Фамилия'] = df_students['ФИО'].str.split(' ').str[0]
        df_students['Имя'] = df_students['ФИО'].str.split(' ').str[1]
        df_students['Отчество'] = df_students['ФИО'].str.split(' ').str[2]
        
        # Handle complex patronymics (e.g., "оглы")
        df_students['Отчество2'] = df_students['ФИО'].str.split(' ').str[3]
        for ind, val in df_students['Отчество2'].items():
            if val == 'углы' or val == 'оглы' or val == 'кызы':
                df_students.loc[ind, 'Отчество'] = (
                    df_students.loc[ind, 'Отчество'] + ' ' + df_students.loc[ind, 'Отчество2']
                )
        
        df_students.drop(columns=['ФИО', 'Отчество2'], inplace=True, errors='ignore')
        
        # Convert dates to strings
        for date_col in ['ДатаРожд', 'ДатаРешенияГэк']:
            if date_col in df_students.columns:
                df_students[date_col] = df_students[date_col].astype(str)
        
        # Process each student
        for _, student_row in df_students.iterrows():
            student_el = ET.SubElement(students_el, "Студент")
            logger.info("1. Parse student: %s", student_row['Фамилия'])
            # Find student's scores
            student_name = student_row['Фамилия']
            disciplines = None
            for col in df_disciplines.columns:
                if col.startswith(student_name):
                    disciplines = df_disciplines[col]
                    break
            
            if disciplines is None:
                logger.warning(f"No scores found for student: {student_name}")
                continue
            
            # Add student info
            for col in ['Фамилия', 'Имя', 'Отчество', 'ДатаРожд',
                       'НаименованиеДокПредОбр', 'ГодДокПредОбр',
                       'ДатаРешенияГэк', 'НомерПротоколаГэк']:
                if col in student_row.index:
                    add_element(student_el, col, str(student_row[col]))
            logger.info("2. Added student info for: %s", student_row['Фамилия'])
            # Add state exams
            exams_el = ET.SubElement(student_el, "Госэкзамены")
            exams_head = ET.SubElement(exams_el, "Заголовок")
            add_element(exams_head, 'ЗачЕд', self.config['gia_z_e'])
            
            # Add thesis exam
            exam_el = ET.SubElement(exams_el, "Госэкзамен")
            add_element(
                exam_el,
                'Наименование',
                f'Выпускная квалификационная работа "{student_row.get("ТемаВКР", "")}"'
            )
            add_element(exam_el, 'Оценка', student_row.get('ОценкаВКР', ''))
            logger.info("3. Added state exam info for: %s", student_row['Фамилия'])
            # Add program volume
            vol_el = ET.SubElement(student_el, 'ОбъемОбрПрограммы')
            add_element(vol_el, 'ЗачЕд', self.config['edu_progr_vol'])
            
            vol_el_hours = ET.SubElement(student_el, 'ОбъемАудиторныхЧасов')
            add_element(vol_el_hours, 'ЧасНед', self.config['edu_progr_vol_contact'])
            logger.info("4. Added program volume info for: %s", student_row['Фамилия'])
            # Add qualification and other info
            add_element(student_el, 'Квалификация', self.config['qualification'])
            add_element(student_el, 'СрокОбучения', self.config['edu_term'])
            add_element(student_el, 'ПредседательГэк', self.config['gek_chairman'])
            add_element(student_el, 'НаименованиеСпец', " ".join(self.config["speciality"].split(" ")[1:]))
            add_element(student_el, 'КодСпец', self.config["speciality"].split(" ")[0])
            logger.info("5. Added qualification and program info for: %s", student_row['Фамилия'])
            # Add extra info
            extra_info_element = ET.SubElement(student_el, "ДополнительныеСведения")
            add_element(
                extra_info_element,
                'ДопСвед',
                f'Наименование (профиль) образовательной программы: "{" ".join(self.config["speciality"].split(" ")[1:])}"'
            )
            add_element(
                extra_info_element,
                'ДопСвед',
                f'Форма обучения: {self.config["edu_form"]}'
            )
            
            # Add disciplines, practices, courseworks, electives
            courseworks_el = ET.SubElement(student_el, "Курсовые")
            practics_el = ET.SubElement(student_el, "Практики")
            practics_head_el = ET.SubElement(practics_el, "Заголовок")
            add_element(practics_head_el, 'ЗачЕд', self.config['pract_total_z_e'])
            
            facults_el = ET.SubElement(student_el, "Факультативы")
            disciplines_el = ET.SubElement(student_el, "Дисциплины")

            logger.info("6. Processing disciplines for: %s", student_row['Фамилия'])
            
            # Process each discipline
            for discipline_full, rate in disciplines.items():
                if pd.isna(rate):
                    continue
                
                try:
                    rate = int(float(rate))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rate for {discipline_full}: {rate}")
                    continue
                
                # Parse discipline info
                parts = discipline_full.split('_')
                if len(parts) < 3:
                    logger.warning(f"Invalid discipline format: {discipline_full}")
                    continue
                
                discipline_name = parts[0]
                discipline_type = parts[1]
                
                try:
                    r_units = int(parts[2])
                except (ValueError, IndexError):
                    logger.warning(f"Invalid credit units in: {discipline_full}")
                    continue
                
                # Add to appropriate section
                if discipline_type == 'дисциплина':
                    discipline_el = ET.SubElement(disciplines_el, "Дисциплина")
                    add_element(discipline_el, 'Наименование', discipline_name)
                    add_element(discipline_el, 'Оценка', rate)
                    add_element(discipline_el, 'ЗачЕд', r_units)
                
                elif discipline_type == 'практика':
                    practic_el = ET.SubElement(practics_el, "Практика")
                    add_element(practic_el, 'Наименование', discipline_name)
                    add_element(practic_el, 'Оценка', rate)
                    add_element(practic_el, 'ЗачЕд', r_units)
                
                elif discipline_type == 'курсовая':
                    coursework_el = ET.SubElement(courseworks_el, "КурсоваяРабота")
                    add_element(coursework_el, 'Наименование', discipline_name)
                    add_element(coursework_el, 'Оценка', rate)
                
                elif discipline_type == 'факультатив':
                    facult_el = ET.SubElement(facults_el, "Факультатив")
                    add_element(facult_el, 'Наименование', discipline_name)
                    add_element(facult_el, 'Оценка', rate)
                    add_element(facult_el, 'ЗачЕд', r_units)
                
                elif discipline_type == 'госэкзамен':
                    exam_el2 = ET.SubElement(exams_el, "Госэкзамен")
                    add_element(exam_el2, 'Наименование', discipline_name)
                    add_element(exam_el2, 'Оценка', rate)
        
        logger.info("Finished processing disciplines for: %s", student_row['Фамилия'])

        # Convert to string
        tree = ET.ElementTree(root)
        import io
        output = io.BytesIO()
        tree.write(output, encoding='utf-8', xml_declaration=True)
        return output.getvalue().decode('utf-8')