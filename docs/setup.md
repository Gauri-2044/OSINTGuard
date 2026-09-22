# OSINTGuard Setup Guide

This guide explains how to run OSINTGuard locally for development.

---

## Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Node.js 18+
- Git
- npm

---

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/OSINTGuard.git
cd OSINTGuard
```

#### Backend Setup
2. Go to the Backend
cd backend
3. Create a Virtual Environment
Windows
python -m venv venv
venv\Scripts\activate
Linux / macOS
python3 -m venv venv
source venv/bin/activate
4. Install Dependencies
pip install -r requirements.txt
5. Install spaCy Model

OSINTGuard uses spaCy for entity extraction.

python -m spacy download en_core_web_sm
6. Configure Environment Variables

Create a .env file in the backend directory.

GEMINI_API_KEY=your_gemini_api_key

Do not commit the .env file to Git.

Use .env.example as a reference.

7. Start the Backend

From the backend directory:
```bash
uvicorn main:app --reload
```
The API will be available at: http://127.0.0.1:8000

API Documentation

Swagger UI: http://127.0.0.1:8000/docs
ReDoc: http://127.0.0.1:8000/redoc

####  Frontend Setup
8. Go to the Frontend

Open another terminal:

cd frontend
9. Install Dependencies
npm install
10. Start the Frontend
npm run dev

The frontend will normally be available at:

http://localhost:5173
Running OSINTGuard

Open the frontend in your browser and enter the content you want to analyze.