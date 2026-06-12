import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from app.xml_generator import DiplomaXMLGenerator


def generator() -> DiplomaXMLGenerator:
    return DiplomaXMLGenerator(
        {
            "edu_term": "4 года",
            "qualification": "бакалавр",
            "edu_form": "очная",
            "speciality": "09.03.01 Информатика",
            "edu_progr_vol": 240,
            "edu_progr_vol_contact": "3180 ак.час",
            "pract_total_z_e": 12,
            "gia_z_e": 9,
            "gek_chairman": "Председатель",
            "state_exam_credits": 6,
        }
    )


def disciplines() -> pd.DataFrame:
    return pd.DataFrame(
        {"Иванов": [5]},
        index=["Математика_дисциплина_3"],
    )


def test_cannot_put_time_into_birth_date():
    students = pd.DataFrame(
        {
            "ФИО": ["Иванов Иван Иванович"],
            "ДатаРожд": [pd.Timestamp("2001-02-03 14:25:59")],
        }
    )
    birth_date = ET.fromstring(
        generator().generate_xml(disciplines(), students)
    ).findtext(".//ДатаРожд")
    assert birth_date == "2001-02-03", "ДатаРожд contains a time component"


def test_cannot_accept_invalid_birth_date():
    students = pd.DataFrame(
        {
            "ФИО": ["Иванов Иван Иванович"],
            "ДатаРожд": ["not-a-date"],
        }
    )
    with pytest.raises(ValueError) as failure:
        generator().generate_xml(disciplines(), students)
    assert "ДатаРожд contains an invalid date" in str(
        failure.value
    ), "Invalid ДатаРожд was accepted"
