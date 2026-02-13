import json
import math
import os
import re
from typing import Any

import requests


def load_prompts(prompt_file: str) -> dict:
    with open(prompt_file, "r") as f:
        return json.load(f)


def detect_tool_use_scratch(messages: list[dict]) -> tuple[bool, list[str]]:
    tool_used = False
    tool_names: list[str] = []
    for m in messages:
        if m.get("role") == "tool":
            tool_used = True
            name = m.get("name")
            if name:
                tool_names.append(name)
        if m.get("role") == "assistant":
            if m.get("tool_calls"):
                tool_used = True
                for tc in m.get("tool_calls", []):
                    fn = tc.get("function", {}).get("name")
                    if fn:
                        tool_names.append(fn)
            content = m.get("content") or ""
            if isinstance(content, str) and "tool_name" in content and "tool_arguments" in content:
                tool_used = True
    return tool_used, sorted(set(tool_names))


def detect_tool_use_strands(messages: list[dict]) -> tuple[bool, list[str]]:
    tool_used = False
    tool_names: list[str] = []
    for m in messages:
        for block in m.get("content", []):
            if "toolUse" in block:
                tool_used = True
                tool_names.append(block["toolUse"]["name"])
    return tool_used, sorted(set(tool_names))


def _parse_temperature(final_text: str) -> tuple[float | None, str | None]:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?\s*([CF])", final_text, re.IGNORECASE)
    if not match:
        return None, None
    value = float(match.group(1))
    unit = match.group(2).upper()
    return value, unit


def _to_celsius(value: float, unit: str) -> float:
    if unit == "C":
        return value
    return (value - 32.0) * 5.0 / 9.0


def _parse_lat_lon(final_text: str) -> tuple[float | None, float | None]:
    lat_match = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*([NS])", final_text, re.IGNORECASE)
    lon_match = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*([EW])", final_text, re.IGNORECASE)
    if lat_match and lon_match:
        lat = float(lat_match.group(1)) * (1 if lat_match.group(2).upper() == "N" else -1)
        lon = float(lon_match.group(1)) * (1 if lon_match.group(2).upper() == "E" else -1)
        return lat, lon

    floats = re.findall(r"-?\d+\.\d+", final_text)
    if len(floats) >= 2:
        return float(floats[0]), float(floats[1])

    return None, None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def fetch_canonical_geocode(query: str) -> dict[str, Any]:
    key = os.getenv("GOOGLE_GEOCODING_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_GEOCODING_API_KEY is required for canonical geocoding.")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    resp = requests.get(url, params={"address": query, "key": key}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError(f"Geocoding failed: {data.get('status')} {data.get('error_message', '')}")

    loc = data["results"][0]["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lon": loc["lng"],
        "provider": "google_geocoding",
    }


def fetch_canonical_weather(lat: float, lon: float) -> dict[str, Any]:
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        raise RuntimeError("OPENWEATHER_API_KEY is required for canonical weather validation.")

    url = "https://api.openweathermap.org/data/2.5/weather"
    resp = requests.get(url, params={"lat": lat, "lon": lon, "appid": key, "units": "metric"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    temp_c = data.get("main", {}).get("temp")
    if temp_c is None:
        raise RuntimeError("OpenWeather response missing temperature.")

    return {
        "temp_c": float(temp_c),
        "provider": "openweather",
    }


def build_canonical_snapshot(prompt_data: dict) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "version": prompt_data.get("version", "unknown"),
        "prompts": {},
    }

    for prompt in prompt_data.get("prompts", []):
        name = prompt["name"]
        if prompt.get("type") == "location":
            query = prompt.get("location") or prompt.get("text")
            snapshot["prompts"][name] = {
                "type": "location",
                "query": query,
                "canonical": fetch_canonical_geocode(query),
            }
        elif prompt.get("type") == "weather":
            query = prompt.get("location") or prompt.get("text")
            geo = fetch_canonical_geocode(query)
            weather = fetch_canonical_weather(geo["lat"], geo["lon"])
            snapshot["prompts"][name] = {
                "type": "weather",
                "query": query,
                "canonical": {
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "temp_c": weather["temp_c"],
                    "geo_provider": geo["provider"],
                    "weather_provider": weather["provider"],
                },
            }

    return snapshot


def validate_weather(final_text: str, canonical: dict[str, Any], max_diff_c: float) -> dict[str, Any]:
    observed_temp, unit = _parse_temperature(final_text)
    if observed_temp is None or unit is None:
        return {
            "valid": False,
            "reason": "no_temperature_found",
        }

    expected_temp_c = canonical.get("temp_c")
    if expected_temp_c is None:
        return {
            "valid": False,
            "reason": "no_canonical_temperature",
        }

    predicted_temp_c = _to_celsius(observed_temp, unit)
    diff_c = abs(predicted_temp_c - float(expected_temp_c))

    return {
        "valid": diff_c <= max_diff_c,
        "expected_temp_c": expected_temp_c,
        "predicted_temp_c": round(predicted_temp_c, 2),
        "diff_c": round(diff_c, 2),
        "max_diff_c": max_diff_c,
    }


def validate_location(final_text: str, canonical: dict[str, Any], max_km: float) -> dict[str, Any]:
    expected_lat = canonical.get("lat")
    expected_lon = canonical.get("lon")
    if expected_lat is None or expected_lon is None:
        return {"valid": False, "reason": "no_canonical_coordinates"}

    lat, lon = _parse_lat_lon(final_text)
    if lat is None or lon is None:
        return {
            "valid": False,
            "reason": "no_coordinates_found",
        }

    dist = _haversine_km(lat, lon, expected_lat, expected_lon)
    return {
        "valid": dist <= max_km,
        "predicted_lat": lat,
        "predicted_lon": lon,
        "expected_lat": expected_lat,
        "expected_lon": expected_lon,
        "distance_km": round(dist, 3),
        "max_km": max_km,
    }


def validate_result(prompt_meta: dict[str, Any], final_text: str, canonical_snapshot: dict[str, Any]) -> dict[str, Any]:
    canonical_entry = canonical_snapshot.get("prompts", {}).get(prompt_meta["name"], {})
    canonical = canonical_entry.get("canonical", {})
    validation_cfg = prompt_meta.get("validation", {})

    if prompt_meta.get("type") == "weather":
        return validate_weather(final_text, canonical, validation_cfg.get("max_diff_c", 3.0))
    if prompt_meta.get("type") == "location":
        return validate_location(final_text, canonical, validation_cfg.get("max_km", 1.0))
    return {"valid": False, "reason": "unknown_prompt_type"}


def classify_provenance(tool_used: bool, validation: dict[str, Any]) -> str:
    if not tool_used:
        return "parametric"
    if validation.get("valid") is True:
        return "tool-assisted"
    return "hybrid_or_failed"
