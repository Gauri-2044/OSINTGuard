"""Deterministic disclosure severity, never an attack probability.

Structural credential validation does not verify authenticity, permissions,
expiration or provider acceptance. Rule co-occurrence is not semantic inference.
"""
from app.services.label_normalization import normalize_entity

RANK = {"Low": 0, "Medium": 1, "High": 2}
UNCERTAINTY = (
    "Severity describes potential disclosure impact, not attack probability. "
    "Credential validity is unknown. Rules may misread negation, examples, "
    "tutorials and deployment context; undetected exposure remains possible."
)
MEDIUM_RULES = {
    "production_infrastructure_disclosure", "software_version_disclosure",
    "network_information_disclosure", "employee_information_disclosure",
    "contact_information_disclosure", "travel_information_disclosure",
    "location_information_disclosure",
}

def evaluate_severity(entities, contexts):
    findings = []
    for raw in entities:
        entity = normalize_entity(raw)
        if entity["label"] not in {"API_KEY", "JWT"}:
            continue
        validated = (entity.get("source") == "regex" and
                     entity.get("validation") == "credential_pattern")
        findings.append({
            "kind": "entity", "detected_risk": "Credential or Secret Exposure",
            "severity": "High" if validated else "Medium",
            "rationale": ("A credential-like value passed structural pattern checks; "
                          "treat it as exposed even though validity is unknown."
                          if validated else
                          "An unvalidated credential candidate needs review."),
            "hacker_tactic": "Potential credential misuse; validity and attacker activity are unknown.",
            "evidence": [{k: entity[k] for k in (
                "label", "original_label", "source", "start", "end", "score",
                "validation", "detector_label",
            ) if k in entity}],
        })
    for context in contexts:
        rule_id = context.get("rule_id")
        if rule_id == "credential_exposure":
            continue
        severity = "Medium" if rule_id in MEDIUM_RULES else "Low"
        rationale = "A rule found entity and keyword co-occurrence; verify the context."
        if rule_id in {"project_information_disclosure", "internal_system_disclosure"}:
            rationale = "A name or internal-system mention does not establish confidentiality."
        findings.append({
            "kind": "context", "rule_id": rule_id,
            "detected_risk": context["context"], "severity": severity,
            "rationale": rationale,
            "hacker_tactic": "Potential information gathering; no attack is established.",
            "evidence": context.get("evidence", []),
        })
    severity = max((f["severity"] for f in findings), key=RANK.get, default="Low")
    # Warnings show post-level severity, consistently with the overall decision.
    for finding in findings:
        finding["severity"] = severity
        finding["uncertainty_note"] = UNCERTAINTY
    return {
        "severity": severity,
        "rationale": list(dict.fromkeys(f["rationale"] for f in findings)) or [
            "No configured exposure evidence was detected; this is not a guarantee of safety."],
        "uncertainty_note": UNCERTAINTY, "policy_version": "1.0",
        "findings": findings,
    }
