import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from app.xml_generator import DataValidationError, DiplomaXMLGenerator


def generator(**overrides) -> DiplomaXMLGenerator:
    config = {
        "edu_term": "4 года",
        "qualification": "бакалавр",
        "edu_form": "очная",
        "direction": "09.03.02 ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ",
        "profile": "Интеллектуальные информационные системы и технологии",
        "edu_progr_vol": 240,
        "edu_progr_vol_contact": "3180 ак.час",
        "pract_total_z_e": 12,
        "gia_z_e": 9,
        "gek_chairman": "Председатель",
        "state_exam_credits": 6,
    }
    config.update(overrides)
    return DiplomaXMLGenerator(config)


def student(**overrides) -> dict:
    row = {
        "ФИО": "Иванов Иван Иванович",
        "ДатаРожд": pd.Timestamp("2001-02-03"),
        "НаименованиеДокПредОбр": "Аттестат о среднем общем образовании",
        "ГодДокПредОбр": 2019,
        "ТемаВКР": "Тема",
        "НомерПротоколаГэк": 3,
        "ДатаРешенияГэк": pd.Timestamp("2026-06-24"),
        "ОценкаВКР": 5,
    }
    row.update(overrides)
    return row


def students(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows) or [student()])


def disciplines(columns=None, index=None) -> pd.DataFrame:
    return pd.DataFrame(
        columns or {"Иванов И. И.": [5]},
        index=index or ["Математика_дисциплина_3"],
    )


def problems_of(call) -> str:
    with pytest.raises(DataValidationError) as failure:
        call()
    return str(failure.value)


def test_cannot_put_time_into_birth_date():
    birth_date = ET.fromstring(
        generator().generate_xml(
            disciplines(),
            students(student(ДатаРожд=pd.Timestamp("2001-02-03 14:25:59"))),
        )
    ).findtext(".//ДатаРожд")
    assert birth_date == "2001-02-03", "ДатаРожд contains a time component"


def test_cannot_accept_invalid_birth_date():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(), students(student(ДатаРожд="not-a-date"))
        )
    )
    assert "ДатаРожд: не удалось распознать дату" in message, (
        "Invalid ДатаРожд was accepted"
    )


def test_cannot_accept_birth_date_typed_as_number():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(), students(student(ДатаРожд=36925))
        )
    )
    assert "дата записана числом" in message, (
        "An Excel serial number was silently read as a 1970 timestamp"
    )


def test_cannot_drop_student_missing_from_pivot():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(),
            students(student(), student(ФИО="Петров Пётр Петрович")),
        )
    )
    assert "Петров Пётр Петрович (строка 3 файла сведений): нет колонки" in message, (
        "A student without grades was silently left out of the XML"
    )


def test_cannot_give_namesake_grades_of_another_student():
    xml = generator().generate_xml(
        disciplines({"Петров А. И.": [5], "Петров Б. В.": [3]}),
        students(student(ФИО="Петров Борис Викторович")),
    )
    grade = ET.fromstring(xml).findtext(".//Дисциплина/Оценка")
    assert grade == "3", "A student received the grades of a namesake"


def test_cannot_pick_one_of_two_columns_for_surname_only_match():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines({"Петров": [5], "Петров А.": [3]}),
            students(student(ФИО="Петров Алексей Иванович")),
        )
    )
    assert "подходит несколько колонок" in message, (
        "An ambiguous pivot column was chosen silently"
    )


def test_cannot_miss_student_when_pivot_writes_yo_as_ye():
    xml = generator().generate_xml(
        disciplines({"Ежиков А. Б.": [4]}),
        students(student(ФИО="Ёжиков Алексей Борисович")),
    )
    surname = ET.fromstring(xml).findtext(".//Фамилия")
    assert surname == "Ёжиков", "Ё/Е spelling difference dropped the student"


def test_cannot_accept_latin_letter_inside_russian_surname():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines({"Ёжиков А. Б.": [4]}),
            students(student(ФИО="Ëжиков Алексей Борисович")),
        )
    )
    assert "смешаны латинские и русские буквы" in message, (
        "A Latin Ë in a surname would be printed on the diploma"
    )


def test_cannot_write_nan_for_missing_patronymic():
    xml = generator().generate_xml(
        disciplines({"Ли В.": [5]}),
        students(student(ФИО="Ли Вэй")),
    )
    patronymic = ET.fromstring(xml).findtext(".//Отчество")
    assert patronymic == "", "A missing patronymic was written as text"


def test_cannot_accept_empty_protocol_number():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(), students(student(НомерПротоколаГэк=float("nan")))
        )
    )
    assert "не заполнено поле НомерПротоколаГэк" in message, (
        "An empty ГЭК protocol number reached the XML"
    )


def test_cannot_accept_three_digit_year_of_previous_document():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(), students(student(ГодДокПредОбр=209))
        )
    )
    assert "ГодДокПредОбр должен быть годом из четырёх цифр" in message, (
        "A three-digit year of the previous document was accepted"
    )


def test_cannot_write_protocol_number_as_float():
    xml = generator().generate_xml(
        disciplines(), students(student(НомерПротоколаГэк=3.0))
    )
    number = ET.fromstring(xml).findtext(".//НомерПротоколаГэк")
    assert number == "3", "The protocol number kept a float suffix"


def test_cannot_skip_question_mark_instead_of_grade():
    message = problems_of(
        lambda: generator().generate_xml(disciplines({"Иванов И. И.": ["?"]}), students())
    )
    assert "«Математика» — недопустимая оценка «?»" in message, (
        "A discipline marked with '?' was silently left out"
    )


def test_cannot_accept_grade_code_outside_cyberdiploma_scale():
    message = problems_of(
        lambda: generator().generate_xml(disciplines({"Иванов И. И.": [8]}), students())
    )
    assert "недопустимая оценка «8»" in message, (
        "Grade code 8 is not a CyberDiploma grade but was accepted"
    )


def test_cannot_reject_not_done_placeholder_grade():
    xml = generator().generate_xml(disciplines({"Иванов И. И.": [7]}), students())
    grade = ET.fromstring(xml).findtext(".//Дисциплина/Оценка")
    assert grade == "7", "Placeholder grade 7 («не выполнял») was rejected"


def test_cannot_drop_graded_row_without_type_suffix():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(
                {"Иванов И. И.": [5, 4]},
                ["Математика_дисциплина_3", "Физические основы электротехники"],
            ),
            students(),
        )
    )
    assert "«Физические основы электротехники» содержит оценки" in message, (
        "A graded discipline without a type suffix was silently dropped"
    )


def test_cannot_treat_gia_rows_as_broken_disciplines():
    xml = generator().generate_xml(
        disciplines(
            {"Иванов И. И.": [5, 7, 4]},
            [
                "Математика_дисциплина_3",
                "Выполнение и защита выпускной квалификационной работы",
                "Подготовка к сдаче и сдача государственного экзамена",
            ],
        ),
        students(),
    )
    count = len(ET.fromstring(xml).findall(".//Дисциплина"))
    assert count == 1, "ГИА rows of the pivot template became disciplines"


def test_cannot_print_profile_in_place_of_direction():
    xml = generator().generate_xml(disciplines(), students())
    name = ET.fromstring(xml).findtext(".//НаименованиеСпец")
    assert name == "ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ", (
        "The supplement shows something other than the direction name"
    )


def test_cannot_lose_profile_in_extra_information():
    xml = generator().generate_xml(disciplines(), students())
    extra = [e.text for e in ET.fromstring(xml).iter("ДопСвед")]
    assert (
        'Направленность (профиль) образовательной программы: '
        '"Интеллектуальные информационные системы и технологии"'
    ) in extra, "The profile is missing from the extra information"


def test_cannot_accept_profile_equal_to_direction_name():
    message = problems_of(
        lambda: generator(
            direction="09.03.02 Интеллектуальные информационные системы и технологии"
        )
    )
    assert "Профиль совпадает с наименованием направления" in message, (
        "The profile was accepted as the direction name"
    )


def test_cannot_accept_direction_without_code():
    message = problems_of(
        lambda: generator(direction="ИНФОРМАЦИОННЫЕ СИСТЕМЫ И ТЕХНОЛОГИИ")
    )
    assert "нужен код вида 09.03.02" in message, (
        "A direction without its code was accepted"
    )


def test_cannot_accept_master_direction_for_bachelor():
    message = problems_of(
        lambda: generator(
            direction="11.04.02 ИНФОКОММУНИКАЦИОННЫЕ ТЕХНОЛОГИИ И СИСТЕМЫ СВЯЗИ",
            profile="Интеллектуальные телекоммуникационные системы и сети",
        )
    )
    assert "относится к уровню «магистр»" in message, (
        "A master's direction code was accepted for a bachelor"
    )


def test_cannot_report_only_the_first_problem():
    message = problems_of(
        lambda: generator().generate_xml(
            disciplines(),
            students(student(ГодДокПредОбр=209, НомерПротоколаГэк=None)),
        )
    )
    assert message.startswith("Найдено ошибок в исходных данных: 2"), (
        "Problems were not reported together"
    )


def test_cannot_reject_year_placeholder():
    xml = generator().generate_xml(disciplines(), students(student(ГодДокПредОбр=1111)))
    year = ET.fromstring(xml).findtext(".//ГодДокПредОбр")
    assert year == "1111", "The agreed placeholder year 1111 was rejected"


def state_exam_pivot(grade) -> pd.DataFrame:
    return disciplines(
        {"Иванов И. И.": [5, 7, grade]},
        [
            "Математика_дисциплина_3",
            "Выполнение и защита выпускной квалификационной работы",
            "Подготовка к сдаче и сдача государственного экзамена",
        ],
    )


def test_cannot_lose_state_exam_grade():
    xml = generator().generate_xml(state_exam_pivot(4), students())
    exams = {
        e.findtext("Наименование"): e.findtext("Оценка")
        for e in ET.fromstring(xml).iter("Госэкзамен")
    }
    assert exams.get("Государственный экзамен") == "4", (
        "The state exam grade from the pivot did not reach the XML"
    )


def test_cannot_put_state_exam_after_thesis():
    xml = generator().generate_xml(state_exam_pivot(4), students())
    first = ET.fromstring(xml).find(".//Госэкзамен").findtext("Наименование")
    assert first == "Государственный экзамен", (
        "The state exam is not listed before the thesis"
    )


def test_cannot_accept_question_mark_for_state_exam():
    message = problems_of(
        lambda: generator().generate_xml(state_exam_pivot("?"), students())
    )
    assert "«Государственный экзамен» — недопустимая оценка «?»" in message, (
        "A '?' state exam grade was silently dropped"
    )


def test_cannot_add_state_exam_when_row_is_empty():
    xml = generator().generate_xml(state_exam_pivot(None), students())
    count = len(ET.fromstring(xml).findall(".//Госэкзамен"))
    assert count == 1, "An empty state exam row produced a state exam entry"
