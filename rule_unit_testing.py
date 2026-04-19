import pytest
from rule_base import assess_risk_from_values


# -----------------------------
# Overall risk classification
# -----------------------------
@pytest.mark.parametrize(
    "wind,wind_dir,wave,tide_flow,expected_risk",
    [
        (5.0, 270, 0.1, 0.1, "MEDIUM"),
        (10.0, 270, 0.3, 0.4, "MEDIUM"),
        (14.0, 180, 0.8, 1.0, "VERY_HIGH"),
        (18.0, 90, 1.0, 1.5, "VERY_HIGH"),
        (5.0, 300, 0.1, 0.1, "LOW"),
    ]
)
def test_expected_risk_levels(wind, wind_dir, wave, tide_flow, expected_risk):
    result = assess_risk_from_values(
        wind,
        wave,
        tide_flow,
        wind_dir
    )

    assert result["risk"] == expected_risk

@pytest.mark.parametrize("wave", [2.6, 3.0, 5.0])
def test_wave_above_universe_is_treated_as_very_high(wave):
    result = assess_risk_from_values(
        0,
        wave,
        0,
        0
    )

    assert result["risk"] == "VERY_HIGH"
    assert result["components"]["wave"] == 3

# -----------------------------
# Direction component severity
# -----------------------------
@pytest.mark.parametrize(
    "direction,expected_direction_severity",
    [
        (0, 0),      # onshore
        (20, 0),     # onshore
        (45, 1),     # cross-shore
        (90, 3),     # offshore
        (180, 3),    # offshore
        (250, 1),    # cross-shore
        (300, 0),    # onshore
    ]
)
def test_direction_component(direction, expected_direction_severity):
    result = assess_risk_from_values(
        5.0,   # wind
        0.1,   # wave
        0.1,   # tide
        direction
    )

    assert result["components"]["direction"] == expected_direction_severity


# -----------------------------
# Return structure
# -----------------------------
def test_return_structure():
    result = assess_risk_from_values(
        8.0,
        0.2,
        0.3,
        300
    )

    assert isinstance(result, dict)
    assert "risk" in result
    assert "components" in result
    assert "max_severity" in result

    assert isinstance(result["components"], dict)

    for key in ["wind", "wave", "tide", "direction"]:
        assert key in result["components"]


# -----------------------------
# Max severity matches risk
# -----------------------------
@pytest.mark.parametrize(
    "wind,wind_dir,wave,tide_flow,expected_max_severity,expected_risk",
    [
        (5.0, 300, 0.1, 0.1, 0, "LOW"),
        (5.0, 250, 0.1, 0.1, 1, "MEDIUM"),
        (18.0, 300, 0.8, 0.1, 2, "HIGH"),
        (5.0, 180, 0.1, 0.1, 3, "VERY_HIGH"),
    ]
)
def test_max_severity_and_risk(wind, wind_dir, wave, tide_flow, expected_max_severity, expected_risk):
    result = assess_risk_from_values(
        wind,
        wave,
        tide_flow,
        wind_dir
    )

    assert result["max_severity"] == expected_max_severity
    assert result["risk"] == expected_risk


# -----------------------------
# Component values are integers in valid range
# -----------------------------
def test_component_severities_are_valid():
    result = assess_risk_from_values(
        15.0,
        0.7,
        1.1,
        180
    )

    components = result["components"]

    for value in components.values():
        assert isinstance(value, int)
        assert value in [0, 1, 2, 3]