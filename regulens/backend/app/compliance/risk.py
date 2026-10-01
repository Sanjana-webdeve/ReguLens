"""FR-10: transparent, rule-based risk classification.
This is a SYSTEM-GENERATED prioritisation aid, NOT a legal or regulatory determination."""

DISCLAIMER = ("System-generated risk classification to help prioritise review. "
              "It is not a legal or regulatory determination.")

HIGH_IMPACT_CATEGORIES = {"kyc", "aml", "customer due diligence", "capital", "liquidity", "sanctions"}
IMPACT_WORDS = ("customer", "onboard", "fraud", "sanction", "suspicious", "report", "terror", "beneficial", "penalt")


def classify(status: str, mandatory: bool, category: str, requirement_text: str):
    if status not in ("MISSING", "PARTIALLY_SATISFIED"):
        return None, 0.0, []
    factors = []
    score = 6.0 if status == "MISSING" else 3.0
    factors.append(f"Policy coverage: {status.replace('_', ' ').lower()} (+{score:g})")
    if mandatory:
        score += 3
        factors.append("Mandatory requirement (+3)")
    else:
        factors.append("Optional/recommended requirement (+0)")
    if category.lower() in HIGH_IMPACT_CATEGORIES:
        score += 1.5
        factors.append(f"High-impact regulatory area: {category} (+1.5)")
    if any(w in requirement_text.lower() for w in IMPACT_WORDS):
        score += 1
        factors.append("Affects customer/financial-crime process (+1)")
    level = "HIGH" if score >= 8 else "MEDIUM" if score >= 5 else "LOW"
    return level, score, factors
