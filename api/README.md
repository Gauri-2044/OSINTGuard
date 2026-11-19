Run the app from the `api` directory:

```bash
python -m uvicorn app.main:app --reload
```

Or run it from the repository root:

```bash
python -m uvicorn app.main:app --reload --app-dir api
```

Train the risk model from the `api` directory:

```bash
python -m models.risk_model
```

If spaCy reports that `en_core_web_sm` is missing, install it once:

```bash
python -m spacy download en_core_web_sm
```

Use spaCy/custom NER for:

PERSON
ORGANIZATION
LOCATION
JOB_ROLE
PROJECT_NAME
PRODUCT
SOFTWARE
CLOUD_PROVIDER
TEAM/DEPARTMENT

###### INFERENCE ENGINE
```bash
Text
 ↓
spaCy NER        → entity
 ↓
Dependency Parse → entity ka sentence mein relation
 ↓
POS / Lemma       → action/meaning clues
 ↓
Your Rules        → cybersecurity context
```

### TODO:
step 1 done with deduplication/overlapping entities   remaining

spaCy context ko samajhne ke liye linguistic information dega; final cybersecurity context tumhare rules decide karenge.

### Analysis and optional rewrite

`POST /analyze` and `POST /api/analyze-post` use the shared local analysis service. The latter returns `masked_text` and `rewritten_text: null`; it never calls Gemini. `warnings` remains the response field for compatibility, with the internal schema named `Finding`.

The scanner offers a separate Generate rewrite action calling `POST /api/rewrite` with `{"text": "original draft"}`. The legacy `/rewrite` endpoint and `masked_text` request alias remain supported. The backend recomputes masking; provider errors return a generic 503 while previously obtained analysis remains usable. Gemini requests use a 30-second HTTP timeout. A rewrite is a candidate to review, not a guarantee of safe publication.

Blocking pipeline routes are synchronous so FastAPI dispatches them through its thread pool. A single spaCy model is shared by entity/context services per worker, and the risk model is initialized before serving requests. Raw pipeline diagnostics are not printed. The existing risk model/rule fallback remains until the text classifier is validated and integrated.
