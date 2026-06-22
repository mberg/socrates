from app.tutor.visuals import validate_visuals


def test_keeps_valid_drops_invalid_and_unknown():
    raw = [
        {"type": "math", "tex": "\\frac{1}{2}", "display": True},
        {"type": "fraction_bar", "bars": [{"denominator": 4, "shaded": 3}]},
        {"type": "math"},                 # invalid: missing tex
        {"type": "no_such_visual"},       # unknown type
        {"type": "mult_grid", "rows": 3, "cols": 4},
    ]
    out = validate_visuals(raw)
    kinds = [v.type for v in out]
    assert kinds == ["math", "fraction_bar", "mult_grid"]


def test_number_line_jump_dicts_use_from_alias():
    # The frontend NumberLine reads `jump.from`; Pydantic stores it as `from_`
    # internally (Python keyword), so the dicts the API emits MUST use the alias.
    from app.tutor.service import validate_visuals_to_dicts

    dicts = validate_visuals_to_dicts([
        {"type": "number_line", "min": -8, "max": 4,
         "jumps": [{"from": 3, "to": -4, "label": "-7"}]},
    ])
    assert dicts[0]["jumps"][0]["from"] == 3
    assert "from_" not in dicts[0]["jumps"][0]
