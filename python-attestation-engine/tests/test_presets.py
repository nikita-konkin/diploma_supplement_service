from app.presets import Preset, Presets


def test_cannot_forget_built_in_department(tmp_path):
    assert Presets(tmp_path).get("ИТРС").codes == ["ИСТ(о)", "ИСТм(о)", "ИТС(о)", "ИТСм(о)"], (
        "ИТРС lost its directions of groups"
    )


def test_cannot_invent_preset_for_unknown_department(tmp_path):
    assert Presets(tmp_path).get("ВМ") is None, "Unknown department got someone else's groups"


def test_cannot_lose_saved_preset(tmp_path):
    Presets(tmp_path).save("ВМ", Preset(faculty="1930", codes=["ПИ(о)"]))
    assert Presets(tmp_path).get("ВМ").codes == ["ПИ(о)"], "Saved directions did not come back"


def test_cannot_drop_other_departments_on_save(tmp_path):
    presets = Presets(tmp_path)
    presets.save("ВМ", Preset(faculty="1930", codes=["ПИ(о)"]))
    presets.save("ФИЗ", Preset(faculty="1930", codes=["ФИЗ(о)"]))
    assert presets.get("ВМ") is not None, "Saving one department erased another"
