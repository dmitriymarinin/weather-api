import os
import json
from functools import lru_cache
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel
from redis import Redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


load_dotenv()


class WeatherResponse(BaseModel):
    city: str
    country: Optional[str] = None
    temperature_c: float
    conditions: str
    humidity: Optional[float] = None
    wind_kph: Optional[float] = None
    source: str


@lru_cache
def get_settings():
    return {
        "visualcrossing_api_key": os.getenv("VISUALCROSSING_API_KEY", ""),
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "cache_ttl_seconds": int(os.getenv("CACHE_TTL_SECONDS", "43200")),
    }


def get_redis(settings=Depends(get_settings)) -> Redis:
    return Redis.from_url(settings["redis_url"], decode_responses=True)


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Weather API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/weather", response_model=WeatherResponse)
@limiter.limit("10/minute")
def get_weather(
    request: Request,
    city: str = Query(..., description="City name or city code"),
    country: Optional[str] = Query(None, description="Optional country code, e.g. RU, US"),
    redis: Redis = Depends(get_redis),
    settings=Depends(get_settings),
):
    if not settings["visualcrossing_api_key"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Weather API key is not configured",
        )

    cache_key_parts = [city.strip().lower()]
    if country:
        cache_key_parts.append(country.strip().lower())
    cache_key = "weather:" + ":".join(cache_key_parts)

    cached = redis.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            data["source"] = "cache"
            return WeatherResponse(**data)
        except Exception:
            redis.delete(cache_key)

    location = city if not country else f"{city},{country}"
    url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    params = {
        "unitGroup": "metric",
        "key": settings["visualcrossing_api_key"],
        "contentType": "json",
    }

    try:
        resp = requests.get(f"{url}/{location}", params=params, timeout=10)
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach external weather service",
        )

    if resp.status_code == 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid city or country code",
        )
    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weather service authentication failed",
        )
    if not resp.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Weather service error: {resp.status_code}",
        )

    payload = resp.json()
    current = payload.get("currentConditions") or {}

    result = {
        "city": payload.get("address", city),
        "country": country,
        "temperature_c": float(current.get("temp")),
        "conditions": current.get("conditions", "Unknown"),
        "humidity": float(current.get("humidity")) if current.get("humidity") is not None else None,
        "wind_kph": float(current.get("windspeed")) if current.get("windspeed") is not None else None,
        "source": "live",
    }

    to_cache = {k: v for k, v in result.items() if k != "source"}
    try:
        redis.setex(cache_key, settings["cache_ttl_seconds"], json.dumps(to_cache))
    except Exception:
        pass

    return WeatherResponse(**result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


