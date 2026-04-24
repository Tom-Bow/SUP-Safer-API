import pytest
from rule_base import assess_risk_from_values, discretise, wind, wave, wind_dir, tide_flow, Wind, Wave, Direction, Tide


# ------------------------------------------------------------
# Overall risk classification
# ------------------------------------------------------------
# Verifies that representative combinations of environmental
# inputs produce the expected overall risk classification.
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

# Verifies that wave heights outside the supported fuzzy universe
# are rejected rather than incorrectly discretised.
@pytest.mark.parametrize("wave", [2.6, 3.0, 5.0])
def test_wave_above_universe(wave):
    with pytest.raises(ValueError):
        assess_risk_from_values(
            0,
            wave,
            0,
            0
         )
    
# Verifies that physically invalid negative inputs are rejected
# before they enter the classification pipeline. 
@pytest.mark.parametrize(
    "wind,wind_dir,wave,tide_flow",
    [
        (-1, 0.1, 0.1, 0),
        (5, -0.1, 0.1, 0),
        (5, 0.1, -0.1, 0),
        (5, 0.1, 0.1, -1)
    ]
)
def test_negative_inputs(wind, wind_dir, wave, tide_flow):
    with pytest.raises(ValueError):
        assess_risk_from_values(wind,wave,tide_flow,wind_dir)


# ------------------------------------------------------------
# Component severity checks
# ------------------------------------------------------------
# Verifies that wind direction is mapped to the expected severity
# category for representative onshore, cross-shore, and offshore bearings.
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

# Verifies that increasing wind values are discretised into the
# expected ordinal severity levels.
@pytest.mark.parametrize(
    "wind,expected",
    [
        (2.0, 0),
        (12.0, 1),
        (19.0, 2),
        (25.0, 3),
    ]
)
def test_wind_component(wind, expected):
    result = assess_risk_from_values(wind, 0.1, 0.1, 0)
    assert result["components"]["wind"] == expected

# ------------------------------------------------------------
# Output structure and consistency
# ------------------------------------------------------------
# Verifies that the returned result has the expected structure
# required by downstream API and frontend consumers.
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


# Verifies that the reported overall risk remains consistent with
# the maximum component severity used by the decision rule.
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


# Verifies that each component severity is returned as an integer
# within the supported ordinal range 0-3.
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
        
# Verifies a basic monotonicity property: increasing wave severity
# should not reduce the resulting maximum severity.
def test_increasing_wave_does_not_reduce_risk():
    low = assess_risk_from_values(5.0, 0.1, 0.1, 0)
    high = assess_risk_from_values(5.0, 1.5, 0.1, 0)

    assert high["max_severity"] >= low["max_severity"]
    
# ------------------------------------------------------------
# Discretisation behaviour
# ------------------------------------------------------------
# Verifies that representative continuous inputs are discretised
# into the expected enum categories. 
@pytest.mark.parametrize(
    "value,variable,enum_class,expected",
    [
        (2.0, wind, Wind, Wind.LOW),          
        (15.0, wind, Wind, Wind.MODERATE),       
        (25.0, wind, Wind, Wind.VERY_HIGH),   

        (0.1, wave, Wave, Wave.CALM),
        (1.5, wave, Wave, Wave.VERY_ROUGH),
    ]
)
def test_discretise_returns_expected_enum(value, variable, enum_class, expected):
    result = discretise(value, variable, enum_class)
    assert result == expected
    
# Verifies that discretisation returns a member of the correct enum
# rather than a raw string or numeric value.
def test_discretise_returns_enum_member():
    result = discretise(5.0, wind, Wind)
    assert isinstance(result, Wind)