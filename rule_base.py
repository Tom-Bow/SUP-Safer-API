# ---------- IMPORTS ----------
from enum import Enum, auto
from itertools import product
import pandas as pd
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# ---------- ENUM DEFINITIONS ----------
class Wind(Enum):
    LOW = auto()
    MODERATE = auto()
    HIGH = auto()
    VERY_HIGH = auto()

class Wave(Enum):
    CALM = auto()
    CHOPPY = auto()
    ROUGH = auto()
    VERY_ROUGH = auto()

class Tide(Enum):
    SLACK = auto()
    WEAK = auto()
    MODERATE = auto()
    STRONG = auto()

class Direction(Enum):
    ONSHORE = auto()
    CROSS_SHORE = auto()
    OFFSHORE = auto()

class Risk(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    VERY_HIGH = auto()
    
# ---------- INPUT MEMBERSHIP FUNCTIONS ---------- #

# WIND SPEED (MPH)
# Range: 0-30 MPH (0-26 knots)
wind = ctrl.Antecedent(np.arange(0, 31, 1), 'wind')

# WIND DIRECTION (Degrees)
# Range: 0-361° (full compass)
# Swansea Bay Geography:
#   - Onshore (safe): 275-360° & 0-30° (W winds push toward shore)
#   - Offshore (hazard): 60-220° (E winds drift paddler to sea)
#   - Cross-shore (moderate): 30-60° & 220-275° (N-S vectors)
wind_dir = ctrl.Antecedent(np.arange(0, 361, 1), 'wind_dir')

# WAVE HEIGHT (Meters)
# Range: 0-2.5m
wave = ctrl.Antecedent(np.arange(0, 2.5, 0.1), 'wave')

# TIDAL FLOW (Knots)
# Extended Range: 0-4.5 knots (was 0-3.1 knots)
# Rationale: Swansea Bay hyper-tidal; spring tides reach 4+ knots
tide_flow = ctrl.Antecedent(np.arange(0, 4.5, 0.1), 'tide_flow')

def define_memberships():
    """
    Define fuzzy membership functions for all input and output variables.
    All thresholds grounded in academic research and Paddle UK guidelines.
    """
    
    # ========================================================================
    # WIND SPEED MEMBERSHIP FUNCTIONS (MPH)
    # ========================================================================
    # Paddle UK Beaufort Scale Thresholds (converted to MPH):
    #   Force 3 (7-10 knots):    8-11.5 MPH     → 'low'
    #   Force 4 (11-16 knots):   12.7-18.4 MPH  → 'moderate' to 'high'
    #   Force 5 (17-21 knots):   19.6-24.2 MPH  → 'high' to 'very_high'
    #   Force 6+ (>21 knots):    >24.2 MPH      → 'very_high'
    # 
    # Key Threshold (MEAN): 13 knots (14.97 MPH) - Force 4 = Paddle UK recommendation to AVOID
    
    wind['LOW'] = fuzz.trapmf(
        wind.universe, 
        [0, 0, 8, 11]  # Peak: 0-8 MPH, fade out at 11 MPH (9.5 knots)
    )
    
    wind['MODERATE'] = fuzz.trapmf(
        wind.universe, 
        [10, 12, 16, 18]  # Rising at 10, peaks 12-16 (10.4-13.9 knots), fades at 18 (15.6 knots)
    )
    
    wind['HIGH'] = fuzz.trapmf(
        wind.universe, 
        [17, 19, 23, 25]  # Rising at 17 (14.7 knots), peaks 19-23, fades at 25 (21.7 knots)
    )
    
    wind['VERY_HIGH'] = fuzz.trapmf(
        wind.universe, 
        [24, 26, 30, 30]  # Rising at 24 (20.8 knots), peaks from 26 onward (>22.5 knots)
    )
    
    # ========================================================================
    # WIND DIRECTION MEMBERSHIP FUNCTIONS (Degrees)
    # ========================================================================
    # Swansea Bay has complex wind dynamics due to bathymetry
    # Critical hazard: Offshore winds drift paddlers ~1 mile/30min at 18 MPH
    # Reference: §2.3.1 "drift at ~3% of wind velocity", §2.2 "avoid offshore completely"
    
    wind_dir['ONSHORE'] = onshore_mf(wind_dir.universe)
    # Membership: Strong at 0°, 90°, 280° (W→E winds pushing toward shore)
    # Peak confidence: 275-360° and 0-30°
    
    wind_dir['OFFSHORE'] = offshore_mf(wind_dir.universe)
    # Membership: Strong at 60-220° (E→W winds dragging to sea)
    # Captures SW offshore (50-100°) and NE offshore (190-220°)
    # CRITICAL HAZARD: Primary cause of rescue incidents
    
    wind_dir['CROSS_SHORE'] = cross_mf(wind_dir.universe)
    # Membership: Strong at 30-60° and 220-275° (N-S vectors)
    # Creates unpredictable drift patterns
    
    # ========================================================================
    # WAVE HEIGHT MEMBERSHIP FUNCTIONS (Meters)
    # ========================================================================
    # Research: 0.5m = threshold for problematic conditions
    # Injury rates increase 82% in wave environments vs flat water
    # Reference: §2.3.2 "injury rates 16.1% flat water → 29.4% wave"
    
    wave['CALM'] = fuzz.trimf(
        wave.universe, 
        [0, 0, 0.4]  # 0-0.4m (safest for all experience levels)
    )
    
    wave['CHOPPY'] = fuzz.trimf(
        wave.universe, 
        [0.3, 0.65, 1.0]  # 0.3-1.0m (manageable but watch for drift)
    )
    
    wave['ROUGH'] = fuzz.trapmf(
        wave.universe, 
        [0.8, 1.1, 1.4, 1.6]  # 0.8-1.6m (caution zone, injury risk increases)
    )
    
    wave['VERY_ROUGH'] = fuzz.trapmf(
        wave.universe, 
        [1.4, 1.5, 2.5, 2.5]  # >1.4m (dangerous, avoid)
    )
    
    # ========================================================================
    # TIDAL FLOW MEMBERSHIP FUNCTIONS (Knots)
    # ========================================================================
    # Swansea Bay tidal characteristics:
    #   - Hyper-tidal: 8.5m mean tidal height (highest in UK, 2nd worldwide)
    #   - Slack tide: ~1 hour window at mean tidal height (minimal lateral flow)
    #   - Spring tide: Can reach 4-4.5+ knots in Severn Estuary
    #   - Neap tide: Typically 0.5-1.5 knots
    # Reference: §2.3.2 Figure 2, §1.1 "Severn Estuary bathymetry"
    
    tide_flow['SLACK'] = fuzz.trimf(
        tide_flow.universe, 
        [0, 0.1, 0.55]  # 0-0.5 kt (true slack tide window)
    )
    # Narrow definition to capture minimal flow period only
    
    tide_flow['WEAK'] = fuzz.trimf(
        tide_flow.universe, 
        [0.45, 0.6, 1.1]  # 0.45-1.0 kt (manageable even for beginners)
    )
    
    tide_flow['MODERATE'] = fuzz.trimf(
        tide_flow.universe, 
        [0.8, 1.6, 2.3]  # 0.8-2.3 kt (typical Swansea neap-spring range)
    )
    
    tide_flow['STRONG'] = fuzz.trapmf(
        tide_flow.universe, 
        [2.0, 2.5, 4.5, 4.5]  # >2.0 kt (spring tide danger, difficult to paddle)
    )
    # Extended upper bound to 4.5 knots for extreme spring tides
    

def onshore_mf(universe):
    """
    Onshore membership function: W to E winds (275-30°)
    
    These winds push paddlers toward the shore, making them the SAFEST direction.
    Peak confidence at W (270°), N-W (315°), and N (0°/360°).
    
    Geometry:
    - mf1: 275-360° (SW to N quadrant)
    - mf2: 0-30° (N to NE quadrant, wraps around)
    """
    mf1 = fuzz.trapmf(universe, [275, 300, 360, 360])
    mf2 = fuzz.trapmf(universe, [0, 0, 20, 30])
    return np.fmax(mf1, mf2)


def offshore_mf(universe):
    """
    Offshore membership function: E to W winds (60-220°)
    
    These winds DRIFT paddlers away from shore toward open ocean.
    Research: ~1 mile drift per 30 minutes at 18 MPH offshore winds
    This is the PRIMARY hazard requiring complete avoidance per Paddle UK.
    
    Peak confidence at E (90°) and S (180°).
    
    Geometry: Single continuous range 60-220° (SE to S to SW quadrants)
    """
    return fuzz.trapmf(universe, [55, 70, 210, 225])


def cross_mf(universe):
    """
    Cross-shore membership function: N-S vector winds (30-60° and 220-275°)
    
    These winds create unpredictable drift patterns perpendicular to shore.
    More hazardous than onshore but less than offshore.
    Can combine with wave action to create chaotic water conditions.
    
    Geometry:
    - mf1: 30-60° (NE quadrant)
    - mf2: 220-275° (SW quadrant)
    """
    mf1 = fuzz.trapmf(universe, [25, 35, 60, 70])
    mf2 = fuzz.trapmf(universe, [210, 220, 275, 285])
    return np.fmax(mf1, mf2)

# ---------- ARGMAX DISCRETISATION LAYER ---------- #

def discretise(value, variable, enum_class):
    # if value < variable.universe[0] or value > variable.universe[-1]:
    #     raise ValueError(
    #         f"Value {value} outside universe for {variable.label}: "
    #         f"{variable.universe[0]} to {variable.universe[-1]}"
    #     )
    
    memberships = {
        name: fuzz.interp_membership(
            variable.universe,
            variable[name].mf,
            value
        )
        for name in variable.terms
    }
    
    best = max(memberships, key=memberships.get)
    
    return enum_class[best]


def assess_risk_from_values(wind_v,wave_v,tide_v,dir_v):
    if any(v is None for v in [wind_v,wave_v,tide_v,dir_v]):
        raise ValueError("All inputs must be provided")
    
    if wind_v < 0 or wave_v < 0 or tide_v < 0:
        raise ValueError("Wind, wave and tide values must be non-negative")
    
    if not(0 <= dir_v <= 360):
        raise ValueError("Wind direction must be between 0 and 360 degrees")
    
    define_memberships()
    
    w = discretise(wind_v, wind, Wind)
    wa = discretise(wave_v, wave, Wave)
    t = discretise(tide_v, tide_flow, Tide)
    d = discretise(dir_v, wind_dir, Direction)
    return compute_risk(w,wa,t,d)


# ---------- SEVERITY MAPPINGS ----------
wind_sev = {Wind.LOW:0, Wind.MODERATE:1, Wind.HIGH:2, Wind.VERY_HIGH:3}
wave_sev = {Wave.CALM:0, Wave.CHOPPY:1, Wave.ROUGH:2, Wave.VERY_ROUGH:3}
tide_sev = {Tide.SLACK:0, Tide.WEAK:1, Tide.MODERATE:2, Tide.STRONG:3}
dir_sev = {Direction.ONSHORE:0, Direction.CROSS_SHORE:1, Direction.OFFSHORE:3}


# ---------- DETERMINISTIC RULE BASE ----------
def compute_risk(wind, wave, tide, direction):
    ws = wind_sev[wind]
    wa = wave_sev[wave]
    ts = tide_sev[tide]
    ds = dir_sev[direction]
    
    max_sev = max(ws, wa, ts, ds)
    
    if max_sev == 0:
        risk = Risk.LOW
    elif max_sev == 1:
        risk = Risk.MEDIUM
    elif max_sev == 2:
        risk = Risk.HIGH
    else:
        risk = Risk.VERY_HIGH
        
    return {
         "risk": risk.name,
        "components": {
            "wind": ws,
            "wave": wa,
            "tide": ts,
            "direction": ds
        },
        "max_severity": max_sev
    }
    