from __future__ import annotations

import re
from typing import Any

import requests

from backend.core.config import settings
from backend.services.translation_service import detect_language, translate_text

SYSTEM_PROMPT = (
    "You are an agricultural assistant specialized in olive tree cultivation and olive farming.\n"
    "Use Tunisian olive-harvest agronomy logic:\n"
    "- Harvest timing must be MI/RI-index based, not fixed calendar-date based.\n"
    "- Premium oil target often MI 3-4 (mid veraison), but cultivar and season matter.\n"
    "- Chemlali often around MI 3-4 for quality-focused oil.\n"
    "- Chetoui commonly around MI >2 and <3 or up to ~3.7 depending objective.\n"
    "- Meski is primarily table olive: green styles earlier (MI 0-2), black styles later (MI 4-6).\n"
    "- If disease is active, do not present harvest timing as precise/reliable.\n"
    "- Recommend regular sampling every 7-10 days and avoid overconfident exact-day claims.\n"
    "Answer format:\nDiagnosis:\nReasoning:\nAction Plan:\nNext Check:"
)

OLIVE_DOMAIN_KEYWORDS = {
    "olive",
    "leaf",
    "leaves",
    "tree",
    "disease",
    "spot",
    "fung",
    "yellow",
    "chlorosis",
    "harvest",
    "irrigation",
    "fertilizer",
    "soil",
    "fruit",
    "anthracnose",
    "peacock",
    "nutrition",
    "water",
    "pest",
    "fungicide",
    "maturity",
    "ri",
    "mi",
    "chemlali",
    "chetoui",
    "meski",
    "tunisia",
    "tunisian",
}


class ChatService:
    def __init__(self) -> None:
        self.model_name = settings.ollama_model
        self.url = settings.ollama_url

    def ask(
        self,
        message: str,
        language_hint: str | None = None,
        latest_analysis: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        detected_lang = detect_language(message, language_hint)
        english_message = translate_text(message, detected_lang, "en")

        forced_logic_reply = self._logic_response(english_message, latest_analysis)
        if forced_logic_reply is not None:
            raw_response = forced_logic_reply
        else:
            raw_response = self._ask_ollama(english_message, latest_analysis)
            if raw_response is None or self._looks_low_quality(raw_response):
                raw_response = self._fallback_response(english_message, latest_analysis)

        localized_response = translate_text(raw_response, "en", detected_lang)
        return localized_response, detected_lang

    def _ask_ollama(self, message_en: str, latest_analysis: dict[str, Any] | None) -> str | None:
        analysis_context = self._analysis_context(latest_analysis)
        payload = {
            "model": self.model_name,
            "prompt": (
                f"{SYSTEM_PROMPT}\n\n"
                f"Last image analysis context:\n{analysis_context}\n\n"
                "Output format:\n"
                "Diagnosis:\nReasoning:\nAction Plan:\nNext Check:\n\n"
                f"Farmer question: {message_en}\nAssistant:"
            ),
            "stream": False,
        }
        try:
            response = requests.post(self.url, json=payload, timeout=80)
            response.raise_for_status()
            body = response.json()
            content = body.get("response", "").strip()
            return content if content else None
        except Exception:
            return None

    def _logic_response(self, message_en: str, latest_analysis: dict[str, Any] | None) -> str | None:
        msg = message_en.lower()
        asks_disease_type = any(
            phrase in msg
            for phrase in [
                "what disease",
                "which disease",
                "disease type",
                "name of disease",
                "type of disease",
                "what is the disease",
            ]
        )
        asks_harvest_logic = "harvest" in msg and any(
            token in msg for token in ["why", "date", "window", "when", "exact"]
        )
        if asks_disease_type and latest_analysis is not None:
            return self._disease_from_latest_analysis(latest_analysis)
        if asks_harvest_logic and latest_analysis is not None:
            return self._harvest_reliability_from_latest_analysis(latest_analysis)
        return None

    def _fallback_response(
        self, message_en: str, latest_analysis: dict[str, Any] | None
    ) -> str:
        msg = message_en.lower()

        if self._is_greeting(msg):
            return (
                "I can help with olive disease diagnosis, treatment planning, irrigation, nutrition, "
                "and harvest decisions. Upload a leaf/fruit image for a concrete diagnosis."
            )

        if not self._is_olive_domain(msg):
            return (
                "I focus on olive farming support. Ask me about olive diseases, yellow leaves, irrigation, "
                "nutrition, pruning, or harvest management."
            )

        if latest_analysis is not None and ("result" in msg or "my tree" in msg or "this tree" in msg):
            return self._latest_analysis_summary(latest_analysis)

        if "yellow" in msg or "chlorosis" in msg:
            return (
                "Likely causes: water stress, nitrogen deficiency, or root oxygen stress.\n"
                "Action Plan:\n"
                "1) Check soil moisture at 20-40 cm depth before irrigation.\n"
                "2) Inspect drainage; avoid standing water around roots.\n"
                "3) Apply balanced nutrition (N + micronutrients) after confirming deficiency."
            )
        if "spot" in msg or "fung" in msg or "peacock" in msg:
            return (
                "Possible fungal leaf disease (e.g., peacock spot / olive leaf spot).\n"
                "Action Plan:\n"
                "1) Remove heavily infected leaves and improve canopy airflow.\n"
                "2) Avoid overhead irrigation late in the day.\n"
                "3) Use a registered fungicide strategy according to local agronomy guidance."
            )
        if "harvest" in msg:
            if latest_analysis is not None:
                return self._harvest_reliability_from_latest_analysis(latest_analysis)
            return (
                "Harvest timing should be maturity-index based, not exact-date based.\n"
                "For Tunisia, practical windows are often around MI 3-4 for quality-focused oil.\n"
                "Chemlali often MI 3-4, Chetoui often >2 and <3 or up to ~3.7 depending objective.\n"
                "Re-sample every 7-10 days and confirm with fruit maturity checks before final harvest."
            )

        symptom_guess = self._symptom_based_disease_guess(msg)
        if symptom_guess is not None:
            return symptom_guess

        return (
            "To give a precise diagnosis, share symptoms (spots color, leaf yellowing pattern, fruit lesions), "
            "recent irrigation frequency, and weather/humidity. If possible, upload a new image analysis."
        )

    def _analysis_context(self, latest_analysis: dict[str, Any] | None) -> str:
        if latest_analysis is None:
            return "No previous analysis available."
        return (
            f"Variety: {latest_analysis.get('variety', 'unknown')}\n"
            f"Disease: {latest_analysis.get('disease', 'unknown')}\n"
            f"Severity: {latest_analysis.get('severity', 'unknown')}\n"
            f"Health score: {latest_analysis.get('health_score', 'unknown')}/100\n"
            f"Risk level: {latest_analysis.get('risk_level', 'unknown')}\n"
            f"Harvest window: {latest_analysis.get('harvest_window', 'unknown')}"
        )

    def _looks_low_quality(self, text: str) -> bool:
        lower = text.lower().strip()
        if len(lower) < 40:
            return True
        banned_fragments = [
            "as an ai language model",
            "i cannot provide medical",
            "i don't have enough information",
        ]
        return any(fragment in lower for fragment in banned_fragments)

    def _is_greeting(self, msg: str) -> bool:
        return bool(re.fullmatch(r"\s*(hi|hello|hey|salam|bonjour|bonsoir)\s*[!.]?\s*", msg))

    def _is_olive_domain(self, msg: str) -> bool:
        return any(keyword in msg for keyword in OLIVE_DOMAIN_KEYWORDS)

    def _disease_from_latest_analysis(self, latest_analysis: dict[str, Any]) -> str:
        disease = str(latest_analysis.get("disease", "Unknown"))
        severity = str(latest_analysis.get("severity", "Unknown"))
        score = latest_analysis.get("health_score", "Unknown")

        if disease.lower() in {"none", "none detected", "healthy"}:
            return (
                f"Latest analysis: no disease detected.\n"
                f"Health Score: {score}/100.\n"
                "Recommendation: continue monitoring and repeat analysis weekly."
            )

        return (
            f"Latest detected disease: {disease}.\n"
            f"Severity: {severity}. Health Score: {score}/100.\n"
            "Recommendation: start treatment now, improve airflow, and re-scan leaf images after 7-10 days."
        )

    def _harvest_reliability_from_latest_analysis(self, latest_analysis: dict[str, Any]) -> str:
        disease = str(latest_analysis.get("disease", "Unknown"))
        severity = str(latest_analysis.get("severity", "Unknown")).lower()
        score = int(latest_analysis.get("health_score", 0))
        window = str(latest_analysis.get("harvest_window", "Unknown"))

        active_disease = disease.lower() not in {"none", "none detected", "healthy"}
        if active_disease and (severity in {"moderate", "severe"} or score < 60):
            return (
                "Harvest date is intentionally not treated as reliable right now.\n"
                f"Reason: active disease ({disease}), severity={severity}, health score={score}/100.\n"
                "Action Plan: stabilize disease first, then re-check maturity index (MI/RI) every 7-10 days."
            )

        if active_disease:
            return (
                f"Current harvest window: {window}.\n"
                "This is a low-reliability estimate because mild disease/stress is present. "
                "Use MI-based fruit maturity checks before final harvest decision."
            )

        return (
            f"Current harvest window: {window}. Tree condition is stable, so this estimate is usable.\n"
            "Final decision should still be validated with MI/RI sampling (typically every 7-10 days)."
        )

    def _latest_analysis_summary(self, latest_analysis: dict[str, Any]) -> str:
        return (
            "Latest analysis summary:\n"
            f"- Variety: {latest_analysis.get('variety', 'Unknown')}\n"
            f"- Disease: {latest_analysis.get('disease', 'Unknown')}\n"
            f"- Severity: {latest_analysis.get('severity', 'Unknown')}\n"
            f"- Health score: {latest_analysis.get('health_score', 'Unknown')}/100\n"
            f"- Harvest window: {latest_analysis.get('harvest_window', 'Unknown')}"
        )

    def _symptom_based_disease_guess(self, msg: str) -> str | None:
        if "black spot" in msg or ("dark spot" in msg and "yellow halo" in msg):
            return (
                "Most likely disease: Peacock spot (Spilocaea oleagina).\n"
                "Why: dark circular spots with yellow halo are typical signs.\n"
                "Action Plan: sanitation + canopy airflow + fungicide strategy."
            )
        if "fruit rot" in msg or "sunken lesion" in msg:
            return (
                "Most likely disease: Anthracnose.\n"
                "Why: fruit rot and sunken lesions are common anthracnose symptoms.\n"
                "Action Plan: remove infected fruit, reduce canopy humidity, and apply targeted control."
            )
        if "yellow" in msg and "no spot" in msg:
            return (
                "Most likely issue: nutrient or irrigation stress rather than fungal disease.\n"
                "Action Plan: check moisture profile and run a nutrient correction plan."
            )
        return None
