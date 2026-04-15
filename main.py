import httpx
import asyncio
import logging
import requests
# from pytides.tide import Tide
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from rule_base import assess_risk_from_values

# ---------- CONFIG ---------- #

MAX_AGE_MINUTES = 15  # Freshness validation window (to ensure data isnt stale)
CACHE_TTL_SECONDS = 300  # Cache data lifetime (to ensure API's are being hit repeatadly)

logging.basicConfig(level=logging.INFO)

# ---------- APP ---------- #

app = FastAPI(
    title="Paddleboard Risk API",
    version="1.0.0"
)

# Allow React later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- UTIL ---------- #

def is_fresh(ts):
    return (datetime.now(timezone.utc) - ts).total_seconds() < MAX_AGE_MINUTES * 60

def ms_to_knots(ms: float):
    return ms * 1.94384

def kmh_to_knots(kmh: float):
    return kmh * 0.539957

def convert_wind_dir(dir: float):
    return (dir + 180) % 360

# ---------- CACHE DATA ---------- #

cache = {}
last_known_good = None

def cache_key(lat,lon):
    return f"{lat}:{lon}"

def get_cache(lat,lon):
    key = cache_key(lat,lon)
    if key in cache:
        data, ts = cache[key]
        if datetime.now(timezone.utc) - ts < timedelta(seconds=CACHE_TTL_SECONDS):
            return data
    return None

def set_cache(lat,lon,data):
    cache[cache_key(lat,lon)] = (data, datetime.now(timezone.utc))


# ---------- ENVRIONMENTAL DATA PROVIDERS ---------- #

async def provider_open_meteo(lat,lon):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=mph"
            marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wind_wave_height,ocean_current_velocity,sea_surface_temperature&minutely_15=sea_level_height_msl&forecast_minutely_15=96"

            # weather_res, marine_res = await asyncio.gather(
            #     client.get(weather_url),
            #     client.get(marine_url),
            # )

            weather_res = await client.get(weather_url)
            weather_res.raise_for_status()

            await asyncio.sleep(0.2) # Test for concurrency errors
            
            marine_res = await client.get(marine_url)
            marine_res.raise_for_status()

            weather = weather_res.json()
            marine = marine_res.json()
            
            logging.info(f"Weather: {weather}")
            logging.info(f"Marine: {marine}")
            
            # tide_info = get_next_tide(marine["minutely_15"]["time"], marine["minutely_15"]["sea_level_height_msl"])


            return {
                "requested_at": datetime.now(timezone.utc),
                "wind": weather["current"]["wind_speed_10m"],
                "wind_dir": convert_wind_dir(weather["current"]["wind_direction_10m"]),
                "wave": marine["current"]["wind_wave_height"],
                # "wave": marine["current"]["wave_height"],
                "tide_flow": kmh_to_knots(marine["current"]["ocean_current_velocity"]),
                # "tide_state": tide_info["tide_state"],
                # "next_tide": tide_info["next_tide"],
                "water_temp": marine["current"]["sea_surface_temperature"],
                "source": "open-meteo"
            }
    except httpx.HTTPStatusError as e:
        logging.error(f"Open-Meteo HTTP error: {e.response.status_code} - {e.response.tst}")
                  
    except Exception as e:
        logging.error(f"Open-Meteo failed: {e}")
        raise
    
    
async def provider_backup(lat,lon):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            url = "https://api.stormglass.io/v2/weather/point"
            
            now = datetime.now(timezone.utc)
            later = now + timedelta(hours=1)
            
            params = {
                "lat": lat,
                "lng": lon,
                "params": "windSpeed,windDirection,windWaveHeight,currentSpeed",
                "start": now.isoformat(),
                "end": later.isoformat(),
                "source": "sg"
            }
            headers = {
                "Authorization" : "47bd6094-0ce8-11f1-9ccf-0242ac120004-47bd6120-0ce8-11f1-9ccf-0242ac120004"
            }
            
            res = await client.get(url, params=params, headers=headers)
            res.raise_for_status()
            data = res.json()
            
            if not data["hours"]:
                raise Exception("Stormglass returned no data")
            
            current = data["hours"][0]

            return {
            "requested_at": datetime.now(timezone.utc),
            "wind": current["windSpeed"]["sg"],  # m/s → mph
            "wind_dir": convert_wind_dir(current["windDirection"]["sg"]),
            "wave": current["windWaveHeight"]["sg"],
            "tide_flow": ms_to_knots(current["currentSpeed"]["sg"]),
            "source": "stormglass"
        }
    except Exception as e:
        logging.error(f"Stormglass failed: {e}")
        raise


PROVIDERS = [
    provider_open_meteo,
    provider_backup
]


# def get_next_tide(tide_times, tide_heights):
#     now = datetime.now()
#     tide_state = None
#     next_tide = None
    
#     for i in range(1, len(tide_times)):
#         t = datetime.fromisoformat(tide_times[i])
#         if t > now:
#             tide_state = "Rising" if tide_heights[i] > tide_heights[i-1] else "Falling"
#             break
    
#     for i in range(1, len(tide_heights) - 1):
#         t = datetime.fromisoformat(tide_times[i])
#         if t <= now: continue

#         prev_h = tide_heights[i - 1]
#         curr_h = tide_heights[i]
#         next_h = tide_heights[i + 1]

#         if prev_h < curr_h > next_h:
#             next_tide = {"type": "High", "time": t, "height": curr_h}
#             break

#         if prev_h > curr_h < next_h:
#             next_tide = {"type": "Low", "time": t, "height": curr_h}
#             break
        
#     return {"tide_state": tide_state, "next_tide": next_tide}


UKHO_API_KEY = "2e3dff448b674cac905400a72d9bdd9d"  # replace with your key
BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"
TIDAL_STATION = "0509"  # Swansea

def get_next_tide(station_id=TIDAL_STATION, forecast_days=2):
    headers = {
        "Ocp-Apim-Subscription-Key": UKHO_API_KEY,
        "Accept": "application/json"
    }

    # Get tidal events for the station
    url = f"{BASE_URL}/Stations/{station_id}/TidalEvents"
    params = {"duration": forecast_days}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    events = resp.json()

    if not events:
        return {"tide_state": None, "next_tide": None}

    now = datetime.now(timezone.utc)

    # future_events = []
    # for e in events:
    #     event_time = datetime.fromisoformat(e["DateTime"]).replace(tzinfo=timezone.utc)
    #     now = datetime.now(timezone.utc)
    #     if event_time > now:
    #         future_events.append({
    #             "type": "High" if e["EventType"] == "HighWater" else "Low",  # High Water / Low Water
    #             "time": event_time,
    #             "height": e["Height"]
    #         })

    # if not future_events:
    #     return {"tide_state": None, "next_tide": None}

    # # Determine tide state (Rising/Falling)
    # first_event = future_events[0]
    # tide_state = "Rising" if first_event["type"] == "High Water" else "Falling"

    # return {
    #     "tide_state": tide_state,
    #     "next_tide": first_event
    prev_event = None
    next_event = None

    # Find previous and next tide events relative to now
    for event in events:
        event_time = datetime.fromisoformat(event["DateTime"])
        if event_time.tzinfo is None:
            # Make offset-aware UTC
            event_time = event_time.replace(tzinfo=timezone.utc)

        if event_time <= now:
            prev_event = {"time": event_time, "type": event["EventType"], "height": event["Height"]}
        elif event_time > now and next_event is None:
            next_event = {"time": event_time, "type": event["EventType"], "height": event["Height"]}

    if not prev_event or not next_event:
        # If we can’t find surrounding events, fallback to next tide only
        tide_state = None
        next_tide = next_event
    else:
        tide_state = "Rising" if next_event["height"] > prev_event["height"] else "Falling"
        next_tide = next_event
    
    # Normalize type to "High" or "Low"
    if next_tide:
        next_tide["type"] = "High" if next_tide["type"].lower().startswith("high") else "Low"


    return {
        "tide_state": tide_state,
        "next_tide": next_tide
    }
    

# ---------- CORE FETCH LOGIC ---------- #

async def get_conditions(lat,lon):
    global last_known_good
    
    cached = get_cache(lat,lon)
    if cached:
        return {**cached, "fresh": True, "cached": True}
    
    for provider in PROVIDERS:
        try:
            data = await provider(lat,lon)
            
            if is_fresh(data["requested_at"]):
                set_cache(lat,lon,data)
                last_known_good = data
                return {**data, "fresh": True, "cached": False}
            
        except Exception as e:
            logging.warning(f"{provider.__name__} failed: {e}")
            
    if last_known_good:
        return {
            **last_known_good,
            "fresh": False,
            "fallback": True
        }
        
    raise Exception("All providers failed!")


# ---------- ROUTES ---------- #
            
@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/risk")
def calculate_risk(
    wind: float,
    wind_dir: float,
    wave: float,
    tide_flow: float
):
    return assess_risk_from_values(wind, wind_dir, wave, tide_flow)

@app.get("/risk/from-weather")
async def risk_from_weather(lat: float, lon: float):
    conditions = await get_conditions(lat, lon)
    
    risk = assess_risk_from_values(
        conditions["wind"],
        conditions["wave"],
        conditions["tide_flow"],
        conditions["wind_dir"]
        )
    
    
    tide_info = get_next_tide()

    # Return risk + metadata
    return {
        "risk": risk["risk"],
        "component_risk": risk["components"],
        
        "source": conditions.get("source"),
        "fresh": conditions.get("fresh", False),
        "cached": conditions.get("cached", False),
        "fallback": conditions.get("fallback", False),
        # include original input values
        "input": {
            "wind": conditions.get("wind"),
            "wind_dir": conditions.get("wind_dir"),
            "wave": conditions.get("wave"),
            "tide_flow": conditions.get("tide_flow"),
            "requested_at": conditions.get("requested_at")
        },
        
        "tides": {
            **tide_info,
            "water_temp": conditions.get("water_temp")
        #     {
        #     # "tide_state": conditions.get("tide_state"),
        #     # "next_tide": conditions.get("next_tide"),
        #     # "tide_state": tide_info["tide_state"],
        #     # "next_tide": tide_info["next_tide"],
        #     # "water_temp": conditions.get("water_temp")
        # }
        }
    }
    
@app.get("/compare")
async def compare(lat: float, lon: float):

    tasks = [provider(lat, lon) for provider in PROVIDERS]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}

    for provider, result in zip(PROVIDERS, results):

        name = provider.__name__

        if isinstance(result, Exception):
            output[name] = {"error": str(result)}
        else:
            output[name] = result

    return output


@app.get("/ping")
def ping_external_api():
    """
    Check if Open-Meteo (Weather and Marine) is reachable.
    """
    try:
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0",
            timeout=5
        )
        m = requests.get(
            "https://marine-api.open-meteo.com/v1/marine?latitude=0&longitude=0",
            timeout=5
        )

        return {
            "status": "ok" if w.status_code == 200 and m.status_code == 200 else "warning",
            "open_meteo_weather": (
                "reachable" if w.status_code == 200 else f"status {w.status_code}"
            ),
            "open_meteo_marine": (
                "reachable" if m.status_code == 200 else f"status {m.status_code}"
            )
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


"""
"wind": 7.58,
    "wind_dir": 243.89,
    "wave": 0.63,
    "tide_flow": 0.9330432,
"""
