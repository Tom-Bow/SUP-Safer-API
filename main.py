import httpx
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from rule_base import assess_risk_from_values

# ---------- CONFIG ---------- #

MAX_AGE_MINUTES = 15  # Freshness validation window (to ensure data isnt stale)
MAX_FALLBACK_AGE_MINUTES = 30 # Provides a conservative data fallback window
CACHE_TTL_SECONDS = 600  # Cache data lifetime (to ensure API's are being hit repeatadly)

logging.basicConfig(level=logging.INFO)

# ---------- APP ---------- #
description = """
SUP Safer API provides risk classifications for stand-up paddleboarding conditions.

## Risk Classification

You can:

- **Generate a risk classification from live environmental data** using `/risk/from-weather`.

- **Generate a risk classification from manual inputs** using `/risk`.

## Data Sources

The API retrieves environmental data from external weather and marine providers.
Multiple providers are used to improve reliability through fallback mechanisms.

## System Endpoints

- `/` — View basic API information.

- `/ping` — Check if the API is running.

## Notes

- This system is a research prototype. Do not replace professional judgement with the output of this data source.
"""

app = FastAPI(
    title="SUP Safer API",
    description=description,
    contact={
        "name": "Thomas Bowden",
        "email": "962971@swansea.ac.uk"
    },
    version="1.0.0"
)

# React Interaction (API CALL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- UTIL ---------- #

def is_fresh(ts:datetime) -> bool:
    return (datetime.now(timezone.utc) - ts).total_seconds() < MAX_AGE_MINUTES * 60

def is_fallback_valid(ts:datetime) -> bool:
    return (datetime.now(timezone.utc) - ts).total_seconds() < MAX_FALLBACK_AGE_MINUTES * 60    

def ms_to_knots(ms: float) -> float:
    return ms * 1.94384

def kmh_to_knots(kmh: float) -> float:
    return kmh * 0.539957

def convert_wind_dir(dir: float) -> float:
    return (dir + 180) % 360

# ---------- CACHE DATA ---------- #

cache = {}
last_known_good = None

def cache_key(lat:float,lon:float) -> str:
    return f"{lat}:{lon}"

def get_cache(lat:float,lon:float):
    key = cache_key(lat,lon)
    if key in cache:
        data, ts = cache[key]
        if datetime.now(timezone.utc) - ts < timedelta(seconds=CACHE_TTL_SECONDS):
            return data
    return None

def set_cache(lat:float,lon:float,data):
    cache[cache_key(lat,lon)] = (data, datetime.now(timezone.utc))


# ---------- ENVRIONMENTAL DATA PROVIDERS ---------- #

async def provider_open_meteo(lat:float,lon:float):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            weather_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=wind_speed_10m,wind_direction_10m"
                "&wind_speed_unit=mph"
            )
            marine_url = (
                "https://marine-api.open-meteo.com/v1/marine"
                f"?latitude={lat}&longitude={lon}"
                "&current=wind_wave_height,ocean_current_velocity,sea_surface_temperature"
                "&minutely_15=sea_level_height_msl&forecast_minutely_15=96"
            )

            weather_res = await client.get(weather_url)
            weather_res.raise_for_status()

            await asyncio.sleep(0.2) # Delay to reduce concurrency errors
            
            marine_res = await client.get(marine_url)
            marine_res.raise_for_status()

            weather = weather_res.json()
            marine = marine_res.json()
            
            logging.info(f"Weather: {weather}")
            logging.info(f"Marine: {marine}")
            

            return {
                "requested_at": datetime.now(timezone.utc),
                "wind": weather["current"]["wind_speed_10m"],
                "wind_dir": convert_wind_dir(weather["current"]["wind_direction_10m"]),
                "wave": marine["current"]["wind_wave_height"],
                "tide_flow": kmh_to_knots(marine["current"]["ocean_current_velocity"]),
                "water_temp": marine["current"]["sea_surface_temperature"],
                "source": "open-meteo"
            }
    except httpx.HTTPStatusError as e:
        logging.error(f"Open-Meteo HTTP error: {e.response.status_code} - {e.response.text}")
        raise
                  
    except Exception as e:
        logging.error(f"Open-Meteo failed: {e}")
        raise
    
    
async def provider_backup(lat:float,lon:float):
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
            "wind": current["windSpeed"]["sg"],
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


# UKHO Tidal Timings
UKHO_API_KEY = "2e3dff448b674cac905400a72d9bdd9d"
BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"
TIDAL_STATION = "0509"  # Swansea

async def get_next_tide(station_id=TIDAL_STATION, forecast_days=2):
    headers = {
        "Ocp-Apim-Subscription-Key": UKHO_API_KEY,
        "Accept": "application/json"
    }
    url = f"{BASE_URL}/Stations/{station_id}/TidalEvents"
    params = {"duration": forecast_days}
    
    # Get tidal events for the station
    async with httpx.AsyncClient(timeout=8) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        events = resp.json()

    if not events:
        return {"tide_state": None, "next_tide": None}

    now = datetime.now(timezone.utc)

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
        return {
            **cached, 
            "fresh": is_fresh(cached["requested_at"]), 
            "cached": True
            }
    
    for provider in PROVIDERS:
        try:
            data = await provider(lat,lon)
            
            if is_fresh(data["requested_at"]):
                set_cache(lat,lon,data)
                last_known_good = data
                return {
                    **data, 
                    "fresh": True, 
                    "cached": False,
                    "fallback": False
                    }
            
        except Exception as e:
            logging.warning(f"{provider.__name__} failed: {e}")
            
    if last_known_good and is_fallback_valid(last_known_good["requested_at"]):
        return {
            **last_known_good,
            "fresh": False,
            "cached": False,
            "fallback": True
        }
        
    raise Exception("All providers failed and no recent fallback available!")


# ---------- ROUTES ---------- #
            
@app.get(
    "/",
    summary="Health check",
    description="Returns a simple response to confirm the API is running.",
    tags=["System"]
)
def health():
    return {"status": "ok"}


@app.get(
    "/risk",
    summary="Get risk classification from manual environmental input values",
    description="Returns a risk classification from the condition attribute inputs supplied. This endpoint bypasses external data sources",
    responses={
        200: {"description": "Risk classification successfully generated"},
        400: {"description": "Invalid input values"},
        500: {"description": "Risk calculation failed due to unexpected server error"}
    },
    tags=["Risk Classification"]
)
def calculate_risk(
    wind: float,
    wind_dir: float,
    wave: float,
    tide_flow: float
):
    try:
     return assess_risk_from_values(wind, wave, tide_flow, wind_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception(f"Risk calculation failed: {e}")
        raise HTTPException(status_code=500, detail="Risk calculation failed")


@app.get(
    "/risk/from-weather",
    summary="Get risk classification from live environmental data sources",
    description="Retrieves current environmental conditions for specified latitude-longitude and returns a risk classification",
    responses={
        200: {"description": "Risk classification successfully generated"},
        400: {"description": "Invalid latitude and/or longitude provided"},
        400: {"description": "Unable to retrieve environmental data from external sources"},
        500: {"description": "Risk calculation failed due to unexpected server error"}
    },
    tags=["Risk Classification"]
)
async def risk_from_weather(lat: float, lon: float):
    try:
        conditions = await get_conditions(lat, lon)
    except Exception as e:
        logging.exception("Failed to retrieve environmental conditions")
        raise HTTPException(status_code=503, detail=f"Environmental data unavailable: {e}")
    
    try:
        risk = assess_risk_from_values(
            conditions["wind"],
            conditions["wave"],
            conditions["tide_flow"],
            conditions["wind_dir"]
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logging.exception("Risk calculation failed")
        raise HTTPException(status_code=500, detail="Risk calculation failed")
    # Tide data is optional
    try:
        tide_info = await get_next_tide()
    except Exception as e:
        logging.warning(f"Tide fetch failed: {e}")
        tide_info= {
            "tide_state": None,
            "next_tide": None
        }

    # Return risk + metadata
    return {
        "risk": risk["risk"],
        "component_risk": risk["components"],
        
        "source": conditions.get("source"),
        "fresh": conditions.get("fresh", False),
        "cached": conditions.get("cached", False),
        "fallback": conditions.get("fallback", False),
        # original input values
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
        }
    }
  
# Routes hits concurrent API limits     
# @app.get("/compare")
# async def compare(lat: float, lon: float):

#     tasks = [provider(lat, lon) for provider in PROVIDERS]
#     results = await asyncio.gather(*tasks, return_exceptions=True)
#     output = {}

#     for provider, result in zip(PROVIDERS, results):
#         name = provider.__name__
#         if isinstance(result, Exception):
#             output[name] = {"error": str(result)}
#         else:
#             output[name] = result

#     return output


@app.get(
    "/ping",
    summary="External source health check",
    description="Returns a simple response to confirm the API is running and that primary data source is reachable",
    tags=["System"]    
)
async def ping_external_api():
    """
    Check if Open-Meteo (Weather and Marine) is reachable.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            w = await client.get(
                "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0"
            )
            m = await client.get(
                "https://marine-api.open-meteo.com/v1/marine?latitude=0&longitude=0"
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

