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
