"""Stretch goal: serve the Criteo uplift model as a small scoring API.

The two LightGBM boosters (treated and control) are committed under
models/, so the API runs from a fresh clone with no data download:

    pip install -r requirements-api.txt
    uvicorn api.main:app --reload

POST /score takes the 12 anonymized Criteo features and returns the
predicted uplift (treated probability minus control probability), the
decile of that score against the held-out distribution, and whether the
user falls in the top 20% the study targets.

This is a demo deployment of a model trained on public data. It makes
no claim about any real audience.
"""
from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

app = FastAPI(
    title="Uplift scoring API",
    description="Scores one user with the two-model uplift ranking from "
                "the Ad Measurement Study. Public data, personal project.",
    version="1.0.0",
)

_treated = lgb.Booster(model_file=str(MODELS / "criteo_treated.txt"))
_control = lgb.Booster(model_file=str(MODELS / "criteo_control.txt"))
_cuts = pd.read_csv(MODELS / "criteo_score_cutpoints.csv")
# cutpoints are the 10%..90% quantiles of the held-out score distribution
_cutpoints = _cuts.score_cutpoint.to_numpy()


class Features(BaseModel):
    """The 12 anonymized Criteo floats, f0 through f11."""
    f0: float = Field(..., description="anonymized feature 0")
    f1: float
    f2: float
    f3: float
    f4: float
    f5: float
    f6: float
    f7: float
    f8: float
    f9: float
    f10: float
    f11: float


class Score(BaseModel):
    uplift_score: float
    decile: int
    in_top_20pct: bool
    note: str


_LANDING = (Path(__file__).resolve().parent / "landing.html").read_text()


@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    """A designed landing page with a plain-English explanation and a
    live scoring demo; the raw interactive docs stay at /docs."""
    return HTMLResponse(_LANDING)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": "criteo two-model uplift"}


@app.post("/score", response_model=Score)
def score(x: Features) -> Score:
    row = np.array([[getattr(x, f"f{i}") for i in range(12)]],
                   dtype=np.float32)
    s = float(_treated.predict(row)[0] - _control.predict(row)[0])
    # decile 1 = highest predicted uplift
    decile = 10 - int(np.searchsorted(_cutpoints, s, side="right"))
    return Score(
        uplift_score=s,
        decile=decile,
        in_top_20pct=decile <= 2,
        note="score = P(convert | ad) - P(convert | no ad); "
             "deciles come from the held-out score distribution",
    )
