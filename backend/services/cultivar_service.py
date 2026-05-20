from __future__ import annotations

from typing import Any

CULTIVARS: list[dict[str, str | float]] = [
    {
        "cultivar": "Chemlali Sfax",
        "typical_harvest_start": "November",
        "typical_harvest_end": "January",
        "oil_yield": "high",
        "climate_adaptation": "central/south Tunisia, drought-tolerant",
        "region": "central/south Tunisia",
    },
    {
        "cultivar": "Chetoui",
        "typical_harvest_start": "October",
        "typical_harvest_end": "December",
        "oil_yield": "medium-high",
        "climate_adaptation": "north Tunisia, cooler/wetter adaptation",
        "region": "north Tunisia",
    },
    {
        "cultivar": "Meski",
        "typical_harvest_start": "September",
        "typical_harvest_end": "November",
        "oil_yield": "medium",
        "climate_adaptation": "table-olive focused, coastal suitability",
        "region": "Sahel and coastal Tunisia",
    },
    {
        "cultivar": "Oueslati",
        "typical_harvest_start": "November",
        "typical_harvest_end": "January",
        "oil_yield": "medium",
        "climate_adaptation": "semi-arid inland adaptation",
        "region": "Kairouan and center",
    },
    {
        "cultivar": "Zarrazi",
        "typical_harvest_start": "November",
        "typical_harvest_end": "February",
        "oil_yield": "medium-high",
        "climate_adaptation": "southern arid adaptation",
        "region": "south Tunisia",
    },
    {
        "cultivar": "Arbequina",
        "typical_harvest_start": "October",
        "typical_harvest_end": "December",
        "oil_yield": "medium",
        "climate_adaptation": "adaptable, performs in moderate climates",
        "region": "introduced cultivar",
    },
    {
        "cultivar": "Koroneiki",
        "typical_harvest_start": "October",
        "typical_harvest_end": "December",
        "oil_yield": "medium-high",
        "climate_adaptation": "heat tolerant with good oil quality stability",
        "region": "introduced cultivar",
    },
    {
        "cultivar": "Unknown",
        "typical_harvest_start": "October",
        "typical_harvest_end": "January",
        "oil_yield": "unknown",
        "climate_adaptation": "not enough cultivar information",
        "region": "unknown",
    },
]

_NORMALIZED = {str(row["cultivar"]).lower(): row for row in CULTIVARS}
_ALIASES = {
    "chemlali": "chemlali sfax",
    "chemlali sfax": "chemlali sfax",
    "chetoui": "chetoui",
    "meski": "meski",
    "oueslati": "oueslati",
    "zarrazi": "zarrazi",
    "arbequina": "arbequina",
    "koroneiki": "koroneiki",
    "unknown": "unknown",
}


def list_cultivars() -> list[dict[str, str | float]]:
    return CULTIVARS


def get_cultivar(name: str | None) -> dict[str, str | float]:
    raw = (name or "").strip().lower()
    key = _ALIASES.get(raw)
    if key and key in _NORMALIZED:
        return _NORMALIZED[key]
    if raw in _NORMALIZED:
        return _NORMALIZED[raw]
    return _NORMALIZED["unknown"]


def infer_cultivar_from_region(location: str | None) -> str:
    text = (location or "").strip().lower()
    if not text:
        return "Unknown"
    if "sfax" in text:
        return "Chemlali Sfax"
    if any(token in text for token in ["north", "bizerte", "zaghouan", "beja", "jendouba", "nabeul"]):
        return "Chetoui"
    if any(token in text for token in ["sahel", "sousse", "monastir", "mahdia"]):
        return "Meski"
    return "Unknown"


def resolve_cultivar(
    *,
    user_selected: str | None,
    ai_detected: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    user = (user_selected or "").strip()
    ai = (ai_detected or "").strip()

    if user and user.lower() != "unknown":
        chosen = user
        source = "user selected"
    elif ai and ai.lower() != "unknown":
        chosen = ai
        source = "AI detected"
    else:
        chosen = infer_cultivar_from_region(location)
        source = "regional estimate"

    meta = get_cultivar(chosen)
    return {
        "cultivar": str(meta["cultivar"]),
        "source": source,
        "metadata": meta,
    }
