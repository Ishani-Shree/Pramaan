# Underwater Microplastic Detection System

An AI-powered system that classifies underwater microplastic particles from microscopy images using deep learning (EfficientNet-B2). Upload an image to the live web dashboard and get an instant contamination state with per-class confidence scores.

---

## Dashboard

![Dashboard](visuals/Dashboard.png)

---

## Prediction Example

![Prediction](visuals/predic.png)

---

## Features

- 5-class polymer classification — Alkyd, Bead, Cellophane, Degraded, Fiber
- 5 contamination severity levels (State 0 Clean → State 4 Critical)
- Real-time web dashboard with animated underwater UI
- Drag-and-drop image upload with instant results
- Prediction history log (last 8 analyses)
- Per-class confidence bar chart
- **97.3% validation accuracy** on held-out test set
- Runs on CPU — no GPU required

---

## Project Structure

```
Underwater_Microplastic_Detection/
├── train.py          # Model training (EfficientNet-B2 + CosineAnnealing)
├── verify.py         # Quick accuracy check on 10 random validation samples
├── dashboard.py      # Flask web app — live detection interface
├── dataset/
│   ├── data.yaml     # Dataset config (paths, class names)
│   ├── train/
│   │   ├── images/   # Training images (.jpg)
│   │   └── labels/   # YOLO-format label files (.txt)
│   └── valid/
│       ├── images/   # Validation images (.jpg)
│       └── labels/
└── visuals/
    ├── Dashboard.png
    └── predic.png
```

---

## Setup

### 1. Install dependencies

```bash
pip install torch torchvision flask scikit-learn seaborn matplotlib pillow
```

### 2. Prepare dataset

Place the dataset under `C:\microplastic\dataset\` with the following layout:

```
C:\microplastic\dataset\
├── train\
│   ├── images\   ← training .jpg files
│   └── labels\   ← YOLO .txt label files
└── valid\
    ├── images\
    └── labels\
```

### 3. Train the model

```bash
python train.py
```

Trains for 60 epochs with CosineAnnealingLR. Saves the best checkpoint to `C:\microplastic\models\best_model.pth` and plots to `C:\microplastic\results\`.

### 4. (Optional) Verify predictions

```bash
python verify.py
```

Runs 10 random validation images through the saved model and prints actual vs predicted class with confidence.

### 5. Launch the dashboard

```bash
python dashboard.py
```

Open **http://127.0.0.1:5001** in your browser.

---

## Model Details

| Property | Value |
|---|---|
| Architecture | EfficientNet-B2 |
| Input size | 260 × 260 px |
| Pretrained on | ImageNet |
| Classes | 5 (alkyd, bead, cellophane, degraded, fiber) |
| Training images | 453 |
| Validation images | 204 |
| Epochs | 60 |
| Optimizer | AdamW (lr=3e-4, weight_decay=1e-4) |
| Scheduler | CosineAnnealingLR |
| Loss | CrossEntropy + label smoothing 0.05 |
| Best val accuracy | **97.3%** |
| Device | CPU / GPU (auto-detected) |

---

## Classes & Contamination States

| Class | State | Severity | Hazard |
|---|---|---|---|
| Alkyd | 1 — Trace debris | Low | Low |
| Bead | 2 — Moderate contamination | Medium | Medium |
| Cellophane | 2 — Moderate contamination | Medium | Medium |
| Degraded | 3 — Heavy contamination | High | High |
| Fiber | 4 — Critical pollution | Critical | Danger |

---

## Tech Stack

- Python 3.10
- PyTorch + TorchVision (EfficientNet-B2)
- Flask (web dashboard)
- Scikit-learn (metrics)
- Matplotlib + Seaborn (training plots)
- Pillow (image loading)
