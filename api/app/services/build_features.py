FEATURE_NAMES = (
    "has_software",
    "has_version",
    "has_ip",
    "has_email",
    "has_location",
    "has_person",
    "has_org",
    "context_infrastructure",
    "context_travel",
    "context_employee",
)


def build_features(entities, contexts):

    labels = {e["label"] for e in entities}
    context_names = {c["context"] for c in contexts}

    features = {
        "has_software": int("SOFTWARE" in labels),
        "has_version": int("VERSION" in labels),
        "has_ip": int("IP_ADDRESS" in labels),
        "has_email": int("EMAIL" in labels),
        "has_location": int("LOCATION" in labels),
        "has_person": int("PERSON" in labels),
        "has_org": int("ORG" in labels),

        "context_infrastructure": int(
            "Production Infrastructure Disclosure" in context_names
            or "Infrastructure Disclosure" in context_names
        ),

        "context_travel": int(
            "Travel Information Disclosure" in context_names
            or "Future Travel Disclosure" in context_names
        ),

        "context_employee": int(
            "Employee Information Disclosure" in context_names
        )
    }

    return {name: features[name] for name in FEATURE_NAMES}