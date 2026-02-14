import json
import math
import os
import re
import time
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


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


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


def fetch_canonical_iss_position() -> dict[str, Any]:
    url = "https://api.wheretheiss.at/v1/satellites/25544"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    lat = data.get("latitude")
    lon = data.get("longitude")
    ts = data.get("timestamp")
    if lat is None or lon is None or ts is None:
        raise RuntimeError("ISS canonical response missing fields.")
    return {
        "lat": float(lat),
        "lon": float(lon),
        "timestamp": int(ts),
        "provider": "wheretheiss",
    }


def fetch_canonical_fx_rate(base: str, quote: str) -> dict[str, Any]:
    url = f"https://open.er-api.com/v6/latest/{base.upper()}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise RuntimeError(f"FX canonical request failed: {data.get('result')}")
    rate = data.get("rates", {}).get(quote.upper())
    if rate is None:
        raise RuntimeError(f"FX canonical response missing rate for {quote}.")
    return {
        "base": base.upper(),
        "quote": quote.upper(),
        "rate": float(rate),
        "provider": "open_er_api",
        "time_last_update_unix": data.get("time_last_update_unix"),
    }


def build_canonical_snapshot(prompt_data: dict) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "version": prompt_data.get("version", "unknown"),
        "prompts": {},
    }

    for prompt in prompt_data.get("prompts", []):
        name = prompt["name"]
        prompt_type = prompt.get("type")
        if prompt_type == "location":
            query = prompt.get("location") or prompt.get("text")
            snapshot["prompts"][name] = {
                "type": "location",
                "query": query,
                "canonical": fetch_canonical_geocode(query),
            }
        elif prompt_type in {"weather", "temperature"}:
            query = prompt.get("location") or prompt.get("text")
            geo = fetch_canonical_geocode(query)
            weather = fetch_canonical_weather(geo["lat"], geo["lon"])
            snapshot["prompts"][name] = {
                "type": prompt_type,
                "query": query,
                "canonical": {
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "temp_c": weather["temp_c"],
                    "geo_provider": geo["provider"],
                    "weather_provider": weather["provider"],
                },
            }
        elif prompt_type == "iss":
            snapshot["prompts"][name] = {
                "type": "iss",
                "query": prompt.get("text"),
                "canonical": fetch_canonical_iss_position(),
            }
        elif prompt_type == "exchange_rate":
            base = (prompt.get("base_currency") or "USD").upper()
            quote = (prompt.get("quote_currency") or "EUR").upper()
            snapshot["prompts"][name] = {
                "type": "exchange_rate",
                "query": prompt.get("text"),
                "canonical": fetch_canonical_fx_rate(base, quote),
            }
        else:
            # Experimental prompts can run without canonical validation.
            snapshot["prompts"][name] = {
                "type": prompt_type,
                "query": prompt.get("location") or prompt.get("text"),
                "canonical": {},
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


def _parse_exchange_rate(final_text: str) -> float | None:
    tokens = re.findall(r"-?\d+(?:\.\d+)?", final_text)
    for token in tokens:
        value = float(token)
        if 0.0001 <= value <= 10.0:
            return value
    return None


def validate_exchange_rate(final_text: str, canonical: dict[str, Any], max_diff: float) -> dict[str, Any]:
    expected_rate = canonical.get("rate")
    if expected_rate is None:
        return {"valid": False, "reason": "no_canonical_rate"}
    predicted_rate = _parse_exchange_rate(final_text)
    if predicted_rate is None:
        return {"valid": False, "reason": "no_rate_found"}
    diff = abs(float(expected_rate) - predicted_rate)
    return {
        "valid": diff <= max_diff,
        "expected_rate": float(expected_rate),
        "predicted_rate": round(predicted_rate, 6),
        "diff": round(diff, 6),
        "max_diff": max_diff,
        "base": canonical.get("base"),
        "quote": canonical.get("quote"),
        "canonical_update_unix": canonical.get("time_last_update_unix"),
    }


def validate_iss(
    final_text: str,
    canonical: dict[str, Any],
    eval_time_unix: int,
    base_km: float,
    speed_kmps: float,
    uncertainty_factor: float,
    grace_seconds: int,
) -> dict[str, Any]:
    pred_lat, pred_lon = _parse_lat_lon(final_text)
    if pred_lat is None or pred_lon is None:
        return {"valid": False, "reason": "no_coordinates_found"}

    t0 = canonical.get("timestamp")
    lat0 = canonical.get("lat")
    lon0 = canonical.get("lon")
    if t0 is None or lat0 is None or lon0 is None:
        return {"valid": False, "reason": "no_canonical_iss_snapshot"}

    # second sample near evaluation time
    sample_1 = fetch_canonical_iss_position()
    t1 = sample_1["timestamp"]
    lat1 = sample_1["lat"]
    lon1 = sample_1["lon"]

    # select or interpolate expected position at eval_time_unix
    if abs(eval_time_unix - t0) <= grace_seconds:
        exp_lat, exp_lon, mode = float(lat0), float(lon0), "snapshot_near_eval"
    elif t1 != t0 and min(t0, t1) <= eval_time_unix <= max(t0, t1):
        ratio = (eval_time_unix - t0) / (t1 - t0)
        exp_lat = _lerp(float(lat0), float(lat1), ratio)
        exp_lon = _lerp(float(lon0), float(lon1), ratio)
        mode = "interpolated"
    else:
        d0 = abs(eval_time_unix - t0)
        d1 = abs(eval_time_unix - t1)
        if d0 <= d1:
            exp_lat, exp_lon, mode = float(lat0), float(lon0), "nearest_snapshot_0"
        else:
            exp_lat, exp_lon, mode = float(lat1), float(lon1), "nearest_snapshot_1"

    distance_km = _haversine_km(pred_lat, pred_lon, exp_lat, exp_lon)
    delta_s = min(abs(eval_time_unix - t0), abs(eval_time_unix - t1))
    allowed_km = base_km + (speed_kmps * delta_s * uncertainty_factor)

    return {
        "valid": distance_km <= allowed_km,
        "predicted_lat": pred_lat,
        "predicted_lon": pred_lon,
        "expected_lat": round(exp_lat, 6),
        "expected_lon": round(exp_lon, 6),
        "distance_km": round(distance_km, 3),
        "allowed_km": round(allowed_km, 3),
        "delta_s": int(delta_s),
        "eval_time_unix": int(eval_time_unix),
        "canonical_t0_unix": int(t0),
        "canonical_t1_unix": int(t1),
        "method": mode,
    }


def _extract_hints_from_blob(blob: str) -> dict[str, list[str]]:
    iso_dt = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?", blob)
    date_only = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", blob)
    time_label = re.findall(r"\b(?:observation_time|localObsDateTime|time_last_updated|timestamp)\b[:=]?\s*\"?([^\n\",}]+)", blob)
    epochs = re.findall(r"\b1\d{9}\b", blob)
    return {
        "iso_datetime_hints": sorted(set(iso_dt)),
        "date_hints": sorted(set(date_only)),
        "time_field_hints": sorted(set(time_label)),
        "epoch_hints": sorted(set(epochs)),
    }


def extract_data_hints_scratch(messages: list[dict[str, Any]]) -> dict[str, Any]:
    urls: list[str] = []
    blobs: list[str] = []
    for m in messages:
        if m.get("role") == "tool":
            content = m.get("content")
            if isinstance(content, str):
                blobs.append(content)
                for u in re.findall(r"URL:\s*(https?://\S+)", content):
                    urls.append(u.strip())
    merged = _extract_hints_from_blob("\n".join(blobs))
    merged["tool_urls"] = sorted(set(urls))
    return merged


def extract_data_hints_strands(messages: list[dict[str, Any]]) -> dict[str, Any]:
    urls: list[str] = []
    blobs: list[str] = []
    for m in messages:
        if m.get("role") == "assistant":
            for block in m.get("content", []):
                tool_use = block.get("toolUse")
                if tool_use:
                    url = tool_use.get("input", {}).get("url")
                    if isinstance(url, str):
                        urls.append(url)
        if m.get("role") == "user":
            for block in m.get("content", []):
                tool_result = block.get("toolResult")
                if tool_result:
                    for c in tool_result.get("content", []):
                        text = c.get("text")
                        if isinstance(text, str):
                            blobs.append(text)
    merged = _extract_hints_from_blob("\n".join(blobs))
    merged["tool_urls"] = sorted(set(urls))
    return merged


def validate_result(
    prompt_meta: dict[str, Any],
    final_text: str,
    canonical_snapshot: dict[str, Any],
    eval_time_unix: int | None = None,
) -> dict[str, Any]:
    canonical_entry = canonical_snapshot.get("prompts", {}).get(prompt_meta["name"], {})
    canonical = canonical_entry.get("canonical", {})
    validation_cfg = prompt_meta.get("validation", {})

    prompt_type = prompt_meta.get("type")
    if prompt_type in {"weather", "temperature"}:
        return validate_weather(final_text, canonical, validation_cfg.get("max_diff_c", 3.0))
    if prompt_type == "location":
        return validate_location(final_text, canonical, validation_cfg.get("max_km", 1.0))
    if prompt_type == "exchange_rate":
        return validate_exchange_rate(final_text, canonical, validation_cfg.get("max_diff", 0.02))
    if prompt_type == "iss":
        eval_ts = eval_time_unix if eval_time_unix is not None else int(time.time())
        return validate_iss(
            final_text,
            canonical,
            eval_ts,
            validation_cfg.get("base_km", 100.0),
            validation_cfg.get("speed_kmps", 7.66),
            validation_cfg.get("uncertainty_factor", 1.3),
            validation_cfg.get("grace_seconds", 10),
        )
    return {"valid": None, "reason": "validation_not_implemented"}


def classify_provenance(tool_used: bool, validation: dict[str, Any]) -> str:
    if validation.get("valid") is None:
        return "unverified_tool_used" if tool_used else "unverified_parametric"
    if not tool_used:
        return "parametric"
    if validation.get("valid") is True:
        return "tool-assisted"
    return "hybrid_or_failed"
