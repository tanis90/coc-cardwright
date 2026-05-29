import copy
import json
from pathlib import Path

import pytest

from coc_generator.engine import calc_pro_points, get_skill_init, validate
from coc_generator.renderer import render


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def error_codes(data: dict) -> set[str]:
    return {error.code for error in validate(data).errors}


def test_occupation_points_sum_formula_groups_and_pick_best_option():
    data = load_example("valid_detective.json")

    assert calc_pro_points("私家侦探", data["attributes"]) == 260


def test_mother_tongue_specializations_start_from_edu():
    data = load_example("valid_detective.json")

    assert get_skill_init("母语", data["attributes"]) == 70
    assert get_skill_init("母语(汉语)", data["attributes"]) == 70


def test_validation_rejects_negative_skill_points():
    data = load_example("valid_detective.json")
    data["skill_allocations"]["pro"]["侦查"] = -1
    data["skill_allocations"]["interest"]["潜行"] = -1

    assert "SKILL_POINTS_NEGATIVE" in error_codes(data)


def test_validation_rejects_fractional_values():
    data = load_example("valid_detective.json")
    data["attributes"]["str"] = 50.5
    data["attributes"]["con"] = 49.5
    data["skill_allocations"]["interest"]["潜行"] = 30.5
    data["luck"] = 60.5
    data["credit_rating"] = 25.5

    codes = error_codes(data)
    assert "ATTR_NOT_INTEGER" in codes
    assert "SKILL_POINTS_NOT_INTEGER" in codes
    assert "LUCK_NOT_INTEGER" in codes
    assert "CREDIT_RATING_NOT_INTEGER" in codes


def test_existing_examples_remain_valid():
    for name in ["valid_detective.json", "doctor.json", "archaeologist.json"]:
        data = load_example(name)
        result = validate(copy.deepcopy(data))
        assert result.valid, name


def test_credit_rating_counts_as_occupation_points():
    data = load_example("valid_detective.json")

    result = validate(data)

    assert result.derived["pro_points_total"] == 260
    assert result.derived["pro_points_used"] == 165
    assert result.derived["pro_points_remaining"] == 95


def test_open_ended_occupation_skill_accepts_concrete_specialization():
    data = load_example("valid_detective.json")
    data["basic"]["job"] = "技工"
    data["skill_allocations"]["pro"] = {"技艺(木工)": 40}
    data["credit_rating"] = 20

    result = validate(data)

    assert result.valid
    assert get_skill_init("技艺(木工)", data["attributes"]) == 5


def test_render_style_is_written_to_html_root():
    data = load_example("valid_detective.json")

    assert 'data-style="color"' in render(data)
    assert 'data-style="mono"' in render(data, style="mono")


def test_render_rejects_unknown_style():
    data = load_example("valid_detective.json")

    with pytest.raises(ValueError):
        render(data, style="sepia")
