from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarvestWindow:
    low: float
    high: float
    label: str


def normalize_cultivar(cultivar: str | None) -> str:
    raw = (cultivar or "").strip().lower()
    if "chemlali" in raw:
        return "chemlali"
    if "ch" in raw and "tou" in raw:
        return "chetoui"
    if "meski" in raw:
        return "meski"
    if "arbequina" in raw:
        return "arbequina"
    if "koroneiki" in raw:
        return "koroneiki"
    if "oueslati" in raw:
        return "oueslati"
    if "zarrazi" in raw:
        return "zarrazi"
    return "unknown"


def estimate_maturity_index(ripeness_index: float) -> float:
    value = max(0.0, min(1.0, float(ripeness_index)))
    return round(value * 7.0, 2)


def ioc_maturity_class(mi: float) -> str:
    if mi < 1.0:
        return "MI 0-1 (green to yellow-green)"
    if mi < 2.0:
        return "MI 1-2 (early color change)"
    if mi < 3.0:
        return "MI 2-3 (early veraison)"
    if mi < 4.0:
        return "MI 3-4 (mid veraison)"
    if mi < 5.0:
        return "MI 4-5 (late-mid ripening)"
    if mi < 6.0:
        return "MI 5-6 (advanced ripening)"
    return "MI 6-7 (very ripe)"


def _window_for(cultivar_key: str, target_style: str) -> HarvestWindow:
    style = (target_style or "premium_oil").strip().lower()

    if cultivar_key == "meski":
        if style == "table_green":
            return HarvestWindow(0.0, 2.0, "Meski table-green window")
        if style == "table_black":
            return HarvestWindow(4.0, 6.0, "Meski table-black window")
        if style == "table_olives":
            return HarvestWindow(2.0, 4.5, "Meski table-olive window")
        return HarvestWindow(2.0, 3.5, "Meski turning-color table window")

    if cultivar_key == "chetoui":
        if style == "table_olives":
            return HarvestWindow(2.0, 4.2, "Chetoui table-olive window")
        if style == "premium_oil":
            return HarvestWindow(2.0, 3.7, "Chetoui premium oil window")
        if style == "yield_oil":
            return HarvestWindow(4.5, 6.0, "Chetoui yield-oriented oil window")
        return HarvestWindow(2.5, 4.0, "Chetoui balanced oil window")

    if cultivar_key == "chemlali":
        if style == "table_olives":
            return HarvestWindow(2.2, 4.4, "Chemlali table-olive window")
        if style == "yield_oil":
            return HarvestWindow(4.5, 6.0, "Chemlali yield-oriented oil window")
        if style == "balanced_oil":
            return HarvestWindow(2.5, 4.0, "Chemlali balanced oil window")
        return HarvestWindow(3.0, 4.0, "Chemlali premium oil window")

    if cultivar_key in {"arbequina", "koroneiki", "oueslati", "zarrazi"}:
        if style == "table_olives":
            return HarvestWindow(2.0, 4.2, f"{cultivar_key.title()} table-olive window")
        if style == "yield_oil":
            return HarvestWindow(4.3, 6.0, f"{cultivar_key.title()} yield-oriented oil window")
        if style == "balanced_oil":
            return HarvestWindow(2.4, 4.1, f"{cultivar_key.title()} balanced oil window")
        return HarvestWindow(2.8, 4.0, f"{cultivar_key.title()} premium oil window")

    if style == "table_olives":
        return HarvestWindow(2.0, 4.0, "Generic table-olive window")
    if style == "yield_oil":
        return HarvestWindow(4.5, 6.0, "Generic yield-oriented oil window")
    if style == "balanced_oil":
        return HarvestWindow(2.5, 4.0, "Generic balanced oil window")
    return HarvestWindow(3.0, 4.0, "Generic premium oil window")


def get_harvest_window(cultivar: str | None, target_style: str | None) -> HarvestWindow:
    cultivar_key = normalize_cultivar(cultivar)
    return _window_for(cultivar_key, target_style or "premium_oil")


def harvest_decision(
    *,
    cultivar: str | None,
    target_style: str | None,
    maturity_index: float,
    estimated_oil_content: float,
    disease: str | None = None,
    health_score: int | None = None,
) -> dict[str, str | float]:
    window = get_harvest_window(cultivar, target_style)
    mi = float(maturity_index)

    disease_text = (disease or "").strip().lower()
    active_disease = disease_text not in {"", "none", "none detected", "healthy"}
    low_health = health_score is not None and int(health_score) < 60

    if active_disease and low_health:
        return {
            "maturity_index_estimate": round(mi, 2),
            "ioc_maturity_class": ioc_maturity_class(mi),
            "maturity_stage": "Disease-limited decision",
            "harvest_recommendation": (
                "Harvest timing is low-reliability now because disease pressure is active. "
                "Stabilize disease first, then re-check MI in 7-10 days."
            ),
            "tunisian_window": f"{window.label}: MI {window.low:.1f}-{window.high:.1f}",
            "reliability": "low",
            "notes": (
                "For Tunisian groves, use MI tracking and regular sampling every 7-10 days; "
                "avoid exact-date decisions from leaf-only disease context."
            ),
        }

    if mi < window.low:
        stage = "Before target window"
        action = (
            f"Too early for {window.label}. Continue weekly MI sampling (7-10 days). "
            "For premium oil, wait until the target MI range is reached."
        )
    elif mi > window.high:
        stage = "After target window"
        action = (
            f"Past the preferred {window.label}. Harvest soon to reduce quality loss risk "
            "(phenolic decline, oxidation/defect risk if fruit handling is delayed)."
        )
    else:
        stage = "Inside target window"
        action = (
            f"Inside {window.label}. This is a suitable harvest window if fruit condition and "
            "processing logistics are ready (rapid fruit-to-mill handling)."
        )

    return {
        "maturity_index_estimate": round(mi, 2),
        "ioc_maturity_class": ioc_maturity_class(mi),
        "maturity_stage": stage,
        "harvest_recommendation": action,
        "tunisian_window": f"{window.label}: MI {window.low:.1f}-{window.high:.1f}",
        "reliability": "medium",
        "notes": (
            f"Estimated oil content: {estimated_oil_content:.2f}%. "
            "Use MI-based monitoring rather than fixed calendar dates."
        ),
    }
