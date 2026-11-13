# Diabetes Insight Dashboard

A full-stack diabetes risk prediction web app. Enter 8 clinical health parameters and get an instant risk assessment — **Low**, **Moderate**, or **High** — along with key contributing factors and dataset-level statistical insights.

---

## Features

- **Risk Assessment** — Evaluates 8 clinical parameters and returns a risk level with confidence score and explanation
- **Dataset Statistics** — Shows mean, median, and range for glucose, BMI, blood pressure, and age from the training dataset
- **Data Insights** — Highlights key risk indicators and patterns found in the diabetes dataset
- **FastAPI Backend** — Serves a trained scikit-learn model via REST API for ML-powered predictions
- **Responsive UI** — Works on desktop and mobile

---

## Screenshots

### Dashboard — Risk Assessment Form
![Dashboard](visuals/Dashboard.png)

### Prediction Result
![Prediction Result](visuals/Result.png)

### Dataset Statistics & Insights
![Dataset Stats](visuals/Stats.png)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| UI Components | shadcn/ui, Radix UI, Tailwind CSS |
| Charts & Icons | Recharts, Lucide React |
| Forms | React Hook Form, Zod |
| Backend | FastAPI, Uvicorn |
| ML Model | scikit-learn, joblib |
| Data | pandas |

---

## Input Parameters

The prediction form takes 8 clinical parameters:

| Parameter | Unit | Description |
|---|---|---|
| Pregnancies | count | Number of times pregnant |
| Glucose | mg/dL | Plasma glucose concentration (2hr OGTT) |
| Blood Pressure | mmHg | Diastolic blood pressure |
| Skin Thickness | mm | Triceps skinfold thickness |
| Insulin | μU/mL | 2-hour serum insulin |
| BMI | kg/m² | Body mass index |
| Diabetes Pedigree Function | — | Genetic risk score (family history) |
| Age | years | Age of the patient |

---

## Project Structure

```
Diabetes-Insight-Dashboard/
├── src/
│   ├── pages/
│   │   ├── Index.tsx           # Main dashboard page
│   │   └── NotFound.tsx        # 404 page
│   ├── components/
│   │   ├── PredictionForm.tsx  # 8-parameter input form
│   │   ├── PredictionResult.tsx# Risk result display
│   │   ├── DataVisualization.tsx# Dataset stats & insights
│   │   ├── PredictorDemo.tsx   # Backend API demo
│   │   └── ui/                 # shadcn/ui component library
│   ├── api/
│   │   └── predict.ts          # Backend API client
│   ├── hooks/                  # use-toast, use-mobile
│   └── lib/
│       └── utils.ts
├── backend/
│   ├── app.py                  # FastAPI server (/ health, /predict)
│   ├── model.joblib            # Trained scikit-learn model
│   ├── train_model.py          # Model training script
│   └── requirements.txt
├── public/
│   └── Doc.svg                 # App favicon
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

---

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) v18 or higher
- Python 3.9 or higher

---

### Frontend Setup

```bash
# Install dependencies
npm install

# Start dev server on http://localhost:8080
npm run dev
```

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

---

### Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Retrain the model
python train_model.py

# Start the API server on http://localhost:8000
uvicorn app:app --reload
```

#### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check — confirms model is loaded |
| `POST` | `/predict` | Accepts `{ "features": [f1, f2, ..., f8] }`, returns prediction |

---

### Environment Variables

Create a `.env` file in the project root to override the backend URL:

```env
VITE_BACKEND_URL=http://localhost:8000
```

If not set, the app defaults to `http://localhost:8000`.

---

## Risk Scoring Logic

The frontend computes a risk score from the input parameters using clinical thresholds:

| Condition | Score |
|---|---|
| Glucose > 140 mg/dL | +30 |
| BMI > 30 | +25 |
| Age > 45 | +20 |
| Blood Pressure > 80 mmHg | +15 |
| Diabetes Pedigree Function > 0.8 | +15 |
| Pregnancies > 3 | +10 |

**Risk levels:** Score < 30 → Low · 30–59 → Moderate · 60+ → High

---

## Disclaimer

> This tool is for **educational purposes only**. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider.
