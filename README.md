# Paddleboard Risk API

A backend service that retrieves real-time environmental conditions and classifies paddleboarding risk using a rule-based model.

## Overview

This API aggregates weather and marine data to generate a simplified risk classification (LOW → VERY HIGH) for paddleboarding conditions.

### It is designed for:

novice paddlers
quick decision-making
usability-focused research (not for real-world safety reliance)
⚙️ Architecture
Data Flow

Request → Cache Check → Data Providers → Risk Engine → Response

Client Request
/risk/from-weather?lat=...&lon=...
Cache Layer
Prevents unnecessary API calls using TTL-based freshness
Data Providers
Primary: Open-Meteo
Fallback: Stormglass
Risk Engine
Rule-based classification using environmental thresholds
Response
Returns risk level and contributing factors
🌐 Endpoints
GET /risk/from-weather

Fetch environmental data and compute risk.

Query Parameters:

lat (float)
lon (float)

Example Response:

```
{
  "risk": "low",
  "component_risk": {},
  "source": "open-meteo",
  "fresh": true,
  "cached": false,
  "fallback": false,
  "input": {
  "wind": 9.6,
  "wind_dir": 338,
  "wave": 0.3,
  "tide_flow": 0.43,
  "requested_at": "2026-04-14T21:57:09Z"
  },
  "tides": {
    "tide_state": "Rising",
    "next_tide": {
      "type": "High",
      "time": "2026-04-15T02:30:00Z",
      "height": 6.2
    },
    "water_temp": 10.5
  }
}
```

`POST /risk`

Manually calculate risk from provided inputs.

`GET /compare`

Compare all data providers (debug/testing only).

`GET /ping`

Basic API health check.

📡 Data Providers
Open-Meteo (Primary)

Provides:

Wind speed and direction
Wave height
Ocean current
Sea surface temperature

⚠️ Concurrency Limitation:

Maximum 1 concurrent request per IP
Requests must be executed sequentially (not in parallel)
Stormglass (Fallback)

Used if Open-Meteo fails.

🧠 Risk Classification Model

A rule-based scoring system using environmental inputs.

Inputs:

Wind speed
Wind direction
Wave height
Tidal current

Output Levels:

LOW
MEDIUM
HIGH
VERY HIGH

Example:

{
"wind_mph": 9.6,
"wave_m": 0.3,
"tide_flow_knots": 0.43,
"risk": "low"
}

⚡ Caching Strategy
In-memory cache keyed by location
Coordinates rounded to improve cache reuse

Example:
cache_key = f"{round(lat, 3)}:{round(lon, 3)}"

Configuration:
CACHE_TTL_SECONDS = 300
MAX_AGE_MINUTES = 15

🔁 Fallback Logic

If all providers fail:

Returns last known valid dataset

{
"fallback": true,
"fresh": false
}

⚠️ Limitations
Designed for research purposes only
Not suitable for real-world safety decisions

Does not account for:

user skill level
equipment quality
sudden environmental changes
📚 Research Context

Risk Classification Web Application for Paddleboarding – Usability Study

Focus:

simplifying environmental data
supporting beginner decision-making
evaluating usability (not safety accuracy)
🛠️ Tech Stack
FastAPI
httpx (async HTTP client)
Python 3

External APIs:

Open-Meteo
Stormglass
UKHO Tidal API
🔧 Future Improvements
Integrate tide state into risk scoring
Add cold water risk factor
User-specific risk calibration
Persistent caching (e.g. Redis)
Internal rate limiting protection
👨‍💻 Author

Thomas Bowden
Swansea University – Computer Science

📌 Notes

To comply with Open-Meteo’s concurrency constraints, external API requests are executed sequentially to prevent rate limiting and ensure reliability.
