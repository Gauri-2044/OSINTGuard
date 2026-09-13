Run app :
flask --app main run
FASTAPI : uvicorn main:app --reload ---- In the folder of the main file
python -m uvicorn app.main:app --reloadpython -m uvicorn app.main:app --reload ----- FROM root

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