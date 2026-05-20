from __future__ import annotations

from functools import lru_cache

from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

SUPPORTED_LANGS = {"en", "fr", "ar"}

try:
    import argostranslate.package
    import argostranslate.translate

    ARGOS_AVAILABLE = True
except Exception:
    ARGOS_AVAILABLE = False


STATIC_TRANSLATIONS: dict[str, dict[str, str]] = {
    "fr": {
        "High confidence": "Confiance elevee",
        "Medium confidence": "Confiance moyenne",
        "Low confidence": "Confiance faible",
        "Needs review": "A verifier",
        "Uncertain": "Incertain",
        "Unknown": "Inconnu",
        "Mild": "Legere",
        "Moderate": "Moderee",
        "Severe": "Severe",
        "leaf": "feuille",
        "fruit": "fruit",
        "branch": "branche",
        "unknown": "inconnu",
        "Leaf": "Feuille",
        "Fruit": "Fruit",
        "Branch": "Branche",
        "No clear disease detected": "Aucune maladie evidente detectee",
        "No visible symptom": "Aucun symptome visible",
        "Olive Peacock Spot": "Oeil de paon de l'olivier",
        "Olive Peacock Spot (Spilocaea oleaginea)": "Oeil de paon de l'olivier (Spilocaea oleaginea)",
        "Aculus Olearius (olive mite damage)": "Aculus olearius (degats d'acariens)",
        "Outside current harvest season": "Hors saison de recolte actuelle",
        "Next season cycle": "Cycle de la prochaine saison",
        "Not in active harvest window": "Hors fenetre active de recolte",
        "In active harvest window": "Dans la fenetre active de recolte",
        "Too early": "Trop tot",
        "Not ready yet": "Pas encore pret",
        "Approaching harvest": "Recolte proche",
        "Harvest now": "Recolter maintenant",
        "Late / urgent": "Tardif / urgent",
        "Data inconsistency": "Incoherence des donnees",
        "Consistent": "Coherent",
        "Inconsistent": "Incoherent",
        "Today": "Aujourd'hui",
        "Immediate (0-3 days)": "Immediate (0-3 jours)",
        "Current field sample": "Echantillon du jour",
        "Monitor color change": "Suivre le changement de couleur",
        "Likely readiness checkpoint": "Point probable de verification de maturite",
        "Pending estimate": "Estimation en attente",
        "Image not suitable for harvest estimation": "Image non adaptee a l'estimation de recolte",
        "Image quality check failed.": "Le controle qualite de l'image a echoue.",
        "Plant part is unclear. The image cannot be routed reliably to a disease model.": "La partie de la plante n'est pas claire. L'image ne peut pas etre routée de facon fiable vers un modele de maladie.",
        "Re-take one clear close-up of a leaf, fruit, or branch.": "Prenez une photo rapprochee et nette d'une feuille, d'un fruit ou d'une branche.",
        "Upload a clearer close-up image with proper lighting and visible symptom area.": "Televersez une image rapprochee plus nette, bien eclairee et avec une zone symptomatique visible.",
        "Leaf evidence is not strong enough for a reliable diagnosis from this image.": "Les indices visibles sur la feuille ne sont pas assez forts pour un diagnostic fiable a partir de cette image.",
        "Upload another clear close-up from an affected area and a second angle.": "Televersez une autre photo nette de la zone atteinte avec un second angle.",
        "Leaf symptoms and model evidence are consistent for this diagnosis.": "Les symptomes foliaires et le modele sont coherents pour ce diagnostic.",
        "Apply recommended management and rescan in 5-7 days.": "Appliquez la conduite recommandee puis refaites un scan dans 5 a 7 jours.",
        "No strong disease pattern is visible in this leaf image.": "Aucun motif pathologique net n'est visible sur cette image de feuille.",
        "Continue monitoring and rescan in 7 days or when symptoms appear.": "Poursuivez la surveillance et refaites un scan dans 7 jours ou lors de l'apparition de symptomes.",
        "Leaf is visible but clear lesion evidence is weak.": "La feuille est visible mais les lesions ne sont pas suffisamment nettes.",
        "Capture another close-up if new spots appear; otherwise continue routine monitoring.": "Prenez une autre photo rapprochee si de nouvelles taches apparaissent, sinon poursuivez la surveillance habituelle.",
        "Strong visible leaf symptoms; returning likely diagnosis with conservative confidence.": "Des symptomes foliaires visibles sont presents; retour d'un diagnostic probable avec une confiance prudente.",
        "Prediction conflicts with visible symptom evidence; confidence reduced.": "La prediction entre en conflit avec les symptomes visibles; la confiance a ete reduite.",
        "Weather history unavailable; fallback climate profile used.": "Historique meteo indisponible; profil climatique par defaut utilise.",
        "Unknown Tunisian cultivar: cautious default priors applied.": "Cultivar tunisien inconnu : hypotheses prudentes par defaut appliquees.",
    },
    "ar": {
        "High confidence": "ثقة عالية",
        "Medium confidence": "ثقة متوسطة",
        "Low confidence": "ثقة منخفضة",
        "Needs review": "تحتاج إلى مراجعة",
        "Uncertain": "غير مؤكد",
        "Unknown": "غير معروف",
        "Mild": "خفيف",
        "Moderate": "متوسط",
        "Severe": "شديد",
        "leaf": "ورقة",
        "fruit": "ثمرة",
        "branch": "غصن",
        "unknown": "غير معروف",
        "Leaf": "ورقة",
        "Fruit": "ثمرة",
        "Branch": "غصن",
        "No clear disease detected": "لم يتم اكتشاف مرض واضح",
        "No visible symptom": "لا توجد أعراض مرئية",
        "Olive Peacock Spot": "عين الطاووس في الزيتون",
        "Olive Peacock Spot (Spilocaea oleaginea)": "عين الطاووس في الزيتون (Spilocaea oleaginea)",
        "Aculus Olearius (olive mite damage)": "أكاروس الزيتون (ضرر الحلم)",
        "Outside current harvest season": "خارج موسم الحصاد الحالي",
        "Next season cycle": "دورة الموسم القادم",
        "Not in active harvest window": "خارج نافذة الحصاد النشطة",
        "In active harvest window": "داخل نافذة الحصاد النشطة",
        "Too early": "مبكر جدا",
        "Not ready yet": "غير جاهز بعد",
        "Approaching harvest": "الحصاد يقترب",
        "Harvest now": "احصد الآن",
        "Late / urgent": "متأخر / عاجل",
        "Data inconsistency": "تعارض في البيانات",
        "Consistent": "متسق",
        "Inconsistent": "غير متسق",
        "Today": "اليوم",
        "Immediate (0-3 days)": "فوري (0-3 أيام)",
        "Current field sample": "عينة اليوم",
        "Monitor color change": "راقب تغير اللون",
        "Likely readiness checkpoint": "نقطة مرجحة للتحقق من الجاهزية",
        "Pending estimate": "التقدير قيد الانتظار",
        "Image not suitable for harvest estimation": "الصورة غير مناسبة لتقدير الحصاد",
        "Image quality check failed.": "فشل فحص جودة الصورة.",
        "Plant part is unclear. The image cannot be routed reliably to a disease model.": "جزء النبات غير واضح. لا يمكن توجيه الصورة بشكل موثوق إلى نموذج الأمراض.",
        "Re-take one clear close-up of a leaf, fruit, or branch.": "التقط صورة قريبة وواضحة لورقة أو ثمرة أو غصن.",
        "Upload a clearer close-up image with proper lighting and visible symptom area.": "حمّل صورة أقرب وأكثر وضوحا مع إضاءة مناسبة ومنطقة أعراض مرئية.",
        "Leaf evidence is not strong enough for a reliable diagnosis from this image.": "الأدلة الظاهرة على الورقة ليست كافية لتشخيص موثوق من هذه الصورة.",
        "Upload another clear close-up from an affected area and a second angle.": "حمّل صورة قريبة أخرى من المنطقة المصابة ومن زاوية ثانية.",
        "Leaf symptoms and model evidence are consistent for this diagnosis.": "أعراض الورقة ونتيجة النموذج متسقة مع هذا التشخيص.",
        "Apply recommended management and rescan in 5-7 days.": "طبّق الإجراء الموصى به ثم أعد الفحص خلال 5 إلى 7 أيام.",
        "No strong disease pattern is visible in this leaf image.": "لا يظهر نمط مرضي واضح في صورة الورقة هذه.",
        "Continue monitoring and rescan in 7 days or when symptoms appear.": "واصل المراقبة وأعد الفحص بعد 7 أيام أو عند ظهور الأعراض.",
        "Leaf is visible but clear lesion evidence is weak.": "الورقة ظاهرة لكن أدلة الآفات ليست واضحة بما يكفي.",
        "Capture another close-up if new spots appear; otherwise continue routine monitoring.": "التقط صورة قريبة أخرى إذا ظهرت بقع جديدة، وإلا واصل المتابعة المعتادة.",
        "Strong visible leaf symptoms; returning likely diagnosis with conservative confidence.": "توجد أعراض واضحة على الورقة؛ تم إرجاع تشخيص محتمل بثقة حذرة.",
        "Prediction conflicts with visible symptom evidence; confidence reduced.": "التنبؤ يتعارض مع الأعراض المرئية؛ تم خفض الثقة.",
        "Weather history unavailable; fallback climate profile used.": "سجل الطقس غير متاح؛ تم استخدام ملف مناخي افتراضي.",
        "Unknown Tunisian cultivar: cautious default priors applied.": "صنف تونسي غير معروف: تم تطبيق افتراضات حذرة افتراضية.",
    },
}


@lru_cache(maxsize=1)
def _installed_languages():
    if not ARGOS_AVAILABLE:
        return []
    return argostranslate.translate.get_installed_languages()


def detect_language(text: str, hint: str | None = None) -> str:
    if hint in SUPPORTED_LANGS:
        return hint
    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGS:
            return lang
    except LangDetectException:
        pass
    return "fr"


def _exact_translate(text: str, to_lang: str) -> str | None:
    bucket = STATIC_TRANSLATIONS.get(to_lang, {})
    translated = bucket.get(text)
    return translated if translated else None


def _replace_fragments(text: str, to_lang: str) -> str:
    bucket = STATIC_TRANSLATIONS.get(to_lang, {})
    translated = text
    for source in sorted(bucket.keys(), key=len, reverse=True):
        translated = translated.replace(source, bucket[source])
    return translated


def _ensure_argos_translation(from_lang: str, to_lang: str) -> None:
    if not ARGOS_AVAILABLE:
        return
    installed_codes = {lang.code for lang in _installed_languages()}
    if from_lang in installed_codes and to_lang in installed_codes:
        return
    try:
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        for package in available_packages:
            if package.from_code == from_lang and package.to_code == to_lang:
                download_path = package.download()
                argostranslate.package.install_from_path(download_path)
                _installed_languages.cache_clear()
                break
    except Exception:
        return


def _argos_translate(text: str, from_lang: str, to_lang: str) -> str | None:
    if not ARGOS_AVAILABLE:
        return None

    _ensure_argos_translation(from_lang, to_lang)
    from_lang_obj = None
    to_lang_obj = None
    for lang in _installed_languages():
        if lang.code == from_lang:
            from_lang_obj = lang
        if lang.code == to_lang:
            to_lang_obj = lang

    if from_lang_obj is None or to_lang_obj is None:
        return None

    try:
        translator = from_lang_obj.get_translation(to_lang_obj)
        if translator is None:
            return None
        translated = translator.translate(text)
        return translated if translated and translated.strip() else None
    except Exception:
        return None


def translate_text(text: str, from_lang: str, to_lang: str) -> str:
    from_lang = from_lang if from_lang in SUPPORTED_LANGS else "en"
    to_lang = to_lang if to_lang in SUPPORTED_LANGS else "fr"

    if not isinstance(text, str) or not text.strip():
        return text
    if from_lang == to_lang:
        return text

    exact = _exact_translate(text, to_lang)
    if exact:
        return exact

    argos_translated = _argos_translate(text, from_lang, to_lang)
    if argos_translated and argos_translated != text:
        return argos_translated

    static_fallback = _replace_fragments(text, to_lang)
    return static_fallback if static_fallback.strip() else text
