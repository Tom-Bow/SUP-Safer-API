# SUP Safer API

A backend service that retrieves real-time environmental conditions and classifies paddleboarding risk using a rule-based model.

This project is part of the dissertation:

**“Development of a Non-Compensatory Risk Classification System for Paddleboarding at Swansea Beach”**

_Repository 1 of 2._
Click [here](https://github.com/Tom-Bow/SUP-Safer-UI) for next repository

## Overview

SUP Safer API aggregates weather and marine data to generate a simplified paddleboarding risk classification, from **LOW** to **VERY HIGH**.

It is designed for:

- Novice paddlers.
- Quick decision-making.
- Usability-focused research, not real-world safety reliance.

## Setup

### Requirements
- Python 3.x / Node.js xx
- Internet connection for external API calls

### Install
- pip install -r requirements.txt
- npm install

### Run
- uvicorn main:app --reload
- npm run dev

### Notes
- The frontend expects the backend to run on ...
- If API keys are required, copy `.env.example` to `.env`
- This project was developed for dissertation submission and is intended for demonstration/research use

## Architecture

### Data flow

```text
Request → Cache Check → Data Providers → Risk Engine → Response
```

### Components

- **Client request**  
  `/risk/from-weather?lat=...&lon=...`

- **Cache layer**  
  Prevents unnecessary API calls using TTL-based freshness.

- **Data providers**  
  Primary: Open-Meteo  
  Fallback: Stormglass

- **Risk engine**  
  Rule-based classification using environmental thresholds.

- **Response**  
  Returns a risk level and contributing factors.

## Endpoints

### `GET /risk/from-weather`

Fetch environmental data and compute risk.

#### Query parameters

- `lat` (`float`)
- `lon` (`float`)

#### Example response

```json
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

### `POST /risk`

Manually calculate risk from provided environmental inputs.

### `GET /compare`

Compare all data providers.  
**Intended for debug and testing only.**

### `GET /ping`

Basic API health check.

## Data Providers

### Open-Meteo (Primary)

Provides:

- Wind speed and direction.
- Wave height.
- Ocean current.
- Sea surface temperature.

#### Concurrency limitation

- Maximum **1 concurrent request per IP**.
- Requests must be executed **sequentially**, not in parallel.

### Stormglass (Fallback)

Used when Open-Meteo fails.

## Risk Classification Model

A rule-based scoring system that classifies paddleboarding risk using environmental inputs.

### Inputs

- Wind speed
- Wind direction
- Wave height
- Tidal current

### Output levels

- **LOW**
- **MEDIUM**
- **HIGH**
- **VERY HIGH**

### Example

```json
{
  "wind_mph": 9.6,
  "wave_m": 0.3,
  "tide_flow_knots": 0.43,
  "risk": "low"
}
```

## Caching Strategy

- In-memory cache keyed by location.
- Coordinates are rounded to improve cache reuse.

### Example

```python
cache_key = f"{lat, 3}:{lon, 3}"
```

### Configuration

```python
CACHE_TTL_SECONDS = 600
MAX_AGE_MINUTES = 15
```

## Fallback Logic

If all providers fail, the API returns the last known valid dataset.

```json
{
  "fallback": true,
  "fresh": false
}
```

## Limitations

This system is designed for research purposes only and is **not suitable for real-world safety decisions**.

It does not account for:

- User skill level.
- Equipment quality.
- Sudden environmental changes.

## Research Context

**Risk Classification Web Application for Paddleboarding – Usability Study**

### Focus

- Simplifying environmental data.
- Supporting beginner decision-making.
- Evaluating usability rather than safety accuracy.

## Tech Stack

- FastAPI
- httpx (async HTTP client)
- Python 3

### External APIs

- Open-Meteo
- Stormglass
- UKHO Tidal API

## Future Improvements

- Integrate tide state into risk scoring.
- Add a cold water risk factor.
- Support user-specific risk calibration.
- Add persistent caching, such as Redis.
- Add internal rate limiting protection.

## Author

**Thomas Bowden**  
Swansea University – Computer Science

## Notes

To comply with Open-Meteo’s concurrency constraints, external API requests are executed sequentially to prevent rate limiting and improve reliability.
