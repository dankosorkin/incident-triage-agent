from eval.grade_sql import (
    extract_fact,
    fact_present_in,
    identifiers_in,
    numbers_in,
)


def test_extract_fact_strips_fact_prefix():
    assert extract_fact("Fact: 10 incidents.") == "10 incidents"


def test_extract_fact_strips_guidance_section():
    text = "Fact: Alice Chen resolved 3 P1 incidents. Guidance must include bounded caches."
    assert extract_fact(text) == "Alice Chen resolved 3 P1 incidents"


def test_extract_fact_plain_sql_answer_unchanged():
    assert extract_fact("search-api, 18 incidents") == "search-api, 18 incidents"


def test_numbers_in_extracts_all_numbers():
    assert numbers_in("Alice Chen resolved 3 P1 incidents") == [3.0, 1.0]


def test_numbers_in_no_numbers():
    assert numbers_in("no digits here") == []


def test_identifiers_in_extracts_service_and_person_names():
    fact = "recommendation-engine and Jordan Lee tie with 2 incidents"
    identifiers = identifiers_in(fact)
    assert "recommendation-engine" in identifiers
    assert "Jordan Lee" in identifiers


def test_identifiers_in_no_identifiers():
    assert identifiers_in("10") == set()


def test_fact_present_in_true_when_number_and_identifier_present():
    fact = "payments-api, 2 incidents"
    target = '{"arguments": {"query": "... WHERE service=\'payments-api\'"}, "result": [{"p1_count": 2}]}'
    present, missing = fact_present_in(fact, target)
    assert present is True
    assert missing == []


def test_fact_present_in_false_when_number_missing():
    fact = "10 incidents"
    target = '{"result": [{"count": 8}]}'
    present, missing = fact_present_in(fact, target)
    assert present is False
    assert "number 10.0" in missing


def test_fact_present_in_false_when_identifier_missing():
    fact = "Alice Chen resolved incidents"
    target = '{"result": [{"resolved_by": "Marcus Webb"}]}'
    present, missing = fact_present_in(fact, target)
    assert present is False
    assert any("Alice Chen" in m for m in missing)


def test_fact_present_in_respects_float_tolerance():
    fact = "4.28 hours"
    target = '{"result": [{"avg_hours": 4.2800001}]}'
    present, _ = fact_present_in(fact, target)
    assert present is True
