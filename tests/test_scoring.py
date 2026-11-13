from eval.scoring import missing_facts, normalize, percentile


def test_normalize():
    assert normalize("EfficientNet-B2") == normalize("efficientnet b2")
    assert normalize("1,326 J") == "1326 j"
    assert normalize("at—least_once") == "at least once"


def test_all_facts_must_be_present():
    assert missing_facts("Pass rate went from 36% to 67%.", ["36%", "67%"]) == []
    assert missing_facts("Pass rate rose to 67%.", ["36%", "67%"]) == ["36%"]


def test_alternatives_any_one_counts():
    facts = [["DVFS", "clock frequency"]]
    assert missing_facts("It needs clock frequency control.", facts) == []
    assert missing_facts("It needs batch size.", facts) == facts


def test_matching_is_case_insensitive():
    assert missing_facts("uses fastapi and SCIKIT-LEARN", ["FastAPI", "scikit-learn"]) == []


def test_percentile_empty_is_zero():
    assert percentile([], 95) == 0.0
