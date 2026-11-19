# Runtime risk policy

Implemented 2026-10-21. This change does not train, export or modify model artifacts.
It changes runtime evidence handling and response policy, not detector accuracy.

## Verified source audit

Sources inspected: entity_service.py, gliner_service.py, nlp_service.py,
context_rules.json, build_features.py, risk_service.py, analysis_service.py,
attack_mapping_service.py, attack_mapping.json, API routes, masking_service.py,
main.py and the frontend warning consumer. spaCy labels were checked in installed
en_core_web_sm metadata. Supported labels are not a claim of observed predictions.

| Detector | Emitted labels before normalization |
|---|---|
| Regex | IP_ADDRESS, IPV6, MAC_ADDRESS, PORT, EMAIL, PHONE, URL, DOMAIN, VERSION, DATE, API_KEY, JWT |
| Dictionary (custom) | CLOUD_PROVIDER, SOFTWARE |
| spaCy | CARDINAL, DATE, EVENT, FAC, GPE, LANGUAGE, LAW, LOC, MONEY, NORP, ORDINAL, ORG, PERCENT, PERSON, PRODUCT, QUANTITY, TIME, WORK_OF_ART |
| GLiNER | VERSION, SOFTWARE, CLOUD_PROVIDER, HOSTNAME, INTERNAL_PROJECT, ORG, PERSON, FILE_PATH, USERNAME, DEVICE |

| Rule | JSON expects | Original mismatch / treatment |
|---|---|---|
| Production infrastructure | SOFTWARE + VERSION | Available |
| Software version | SOFTWARE + VERSION | Available; keyword v now whole-term, not substring |
| Cloud infrastructure | CLOUD_PROVIDER | Available; provider mention is not proof of sensitive infrastructure |
| Network information | IP_ADDRESS | IPV6 now accepted as an alternative |
| Employee information | PERSON + ORG | Available; co-occurrence does not establish employment |
| Contact information | EMAIL | PHONE now accepted as an alternative, without renaming it |
| Travel information | LOCATION | GPE / LOC normalized to LOCATION |
| Project information | PROJECT_NAME | PROJECT_NAME / INTERNAL_PROJECT normalized to PROJECT |
| Internal system | INTERNAL_TOOL | No current detector emits it; do not relabel SOFTWARE or HOSTNAME to fabricate it |
| Credential exposure | API_KEY | JWT accepted; additional keywords no longer required |
| Location information | LOCATION | GPE / LOC normalized to LOCATION |
| Date information | DATE | Available; contextual ambiguity remains |

## Complete replacement files and responsibilities

The actual files in the workspace contain the complete implementations.

1. api/app/services/context_service.py: sentence-level rule evidence.
   Depends on context_rules.json, shared nlp and label_normalization.py.
   Emits rule IDs, offsets and provenance evidence; no independent risk_hint.
2. api/app/services/severity_policy.py: deterministic policy over entities and
   context findings. Depends on canonical normalization only.
3. api/app/services/risk_service.py: legacy RF/debug inference. Depends on the
   unchanged FEATURE_NAMES schema and existing artifact; load/inference failure
   returns unavailable, not synthetic 100% confidence.
4. api/app/services/analysis_service.py: orchestration and one public decision.
   Depends on detectors, contexts, features, legacy baseline, policy, mapping and masking.
5. tests/test_runtime_severity.py: pytest coverage of policy and HTTP contracts.
   Existing tests/test_routes.py updated for the new detector interface and mocked startup.

Additional required integration:
- label_normalization.py is the sole alias mapping. Original labels and source
  are retained; GLiNER also retains detector_label (the prompt label).
- entity_service.py tags credential regex matches as credential_pattern and
  reports request-local status. Only IP/port patterns have separate validators.
- gliner_service.py reports disabled, unavailable, available or not_run states;
  inference errors do not return misleading successful empty detections.
- nlp_service.py tolerates a missing spaCy dependency/model. Context matching
  degrades to whole-post scope when sentence segmentation is unavailable.
- masking_service.py masks the union of overlapping intervals. Analysis uses
  all candidates, not the greedy overlap selection used for legacy RF features.
- API adapters consume policy warnings, preserve required warning fields and
  expose findings, detector status, limitations and legacy_debug.
- main.py has one lifespan function; the duplicate previously shadowed RF startup.
- Frontend no longer claims that no findings means safe to publish and displays
  incomplete detector coverage.

## Public decision contract

risk.severity, risk.prediction (compatibility alias), top-level severity, findings
and warnings all use the same **post-level** High/Medium/Low severity.
A warning's severity is the overall post priority, not a separately estimated
severity for that individual piece of evidence.

warnings retains detected_risk, severity and hacker_tactic.
No secret value or original sentence is copied into warning text, rationales,
or finding evidence. The entities response still contains submitted entity text
for compatibility; it is not written to application logs.

legacy_debug.random_forest is explicitly debug_only. Its prediction may disagree
with the policy because it is a historical baseline, not another severity.
FEATURE_NAMES and feature order are unchanged; legacy feature entity inputs
remain overlap-resolved, pre-normalization candidates. Corrected context matches
can change feature values, so this is not a promise of historical bit-for-bit
predictions.

Structurally matched API_KEY/JWT candidates from regex force High even if their
authenticity is unknown. credential_pattern means format/context matched the
configured regex, not provider verification or a checksum. Unvalidated credential
candidates receive Medium. There are no network credential-validation calls.

Most personal/technical context hits receive Medium; project/cloud/internal-name
and schedule mentions default to Low. A project or hostname alone never proves
confidentiality. Low and an empty warning list never mean guaranteed safety.

Attack mappings are potential associations, not observed attacks, probabilities,
or independent severity sources. Their external taxonomy attributions were not
revalidated in this runtime task.

## Detector controls and limitations

OSINT_REGEX_ENABLED, OSINT_DICTIONARY_ENABLED, OSINT_SPACY_ENABLED and
OSINT_GLINER_ENABLED accept 0 / false / no to disable the corresponding detector.
Disabling spaCy NER does not disable the shared sentence parser.
Response detector statuses include context_rules. analysis_complete is false
when any detector is disabled, unavailable, degraded or skipped for empty input.
An available detector is not a guarantee of recall.

Rules cannot reliably distinguish negation, quotation, tutorial examples,
hypothetical infrastructure or actual deployment. Same-sentence entities need
not be related. Whole-post fallback increases this ambiguity. These limitations
are returned in the response. Credential examples may conservatively receive High.

Empty strings remain HTTP 422 according to existing request validation.
The internal analysis function handles empty/whitespace input without warnings.
Existing regex coverage and model quality have not been benchmarked or improved
by this policy change. Models are not automatically retrained.

## Validation actually executed

- Final targeted run:
  python -m pytest tests/test_runtime_severity.py tests/test_routes.py tests/test_entity_training.py -q -p no:cacheprovider
  Result: 36 passed.
- Frontend: npm run build succeeded.
- git diff --check for touched tracked implementation files succeeded.
- Earlier broader run including test_exposure_classifier.py: 39 passed, 1 failed.
  ExposureTests.test_current_source_parses_without_execution assumes every source
  row has review_status pending; the current source has approved rows.
  The dataset and that expectation were left unchanged.

Tests isolate neural models and the external rewrite provider; they are not
live GLiNER accuracy tests or trained-model benchmarks. Both HTTP analysis
endpoints were tested with real regex credential detection and a legacy Safe
prediction to verify policy independence. Model artifacts were not modified.
