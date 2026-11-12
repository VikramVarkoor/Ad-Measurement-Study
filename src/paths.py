"""Single source of truth for where files live, so every script agrees."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
SQL = ROOT / "sql"
EXCEL = ROOT / "excel"
DECK = ROOT / "deck"
DASHBOARDS = ROOT / "dashboards"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

KAGGLEHUB = RAW / "kagglehub" / "datasets"

CRITEO = RAW / "criteo-research-uplift-v2.1.csv.gz"
HILLSTROM = RAW / "hillstrom.csv"
LENTA = RAW / "lenta_dataset.csv.gz"
X5_TRAIN = RAW / "x5_uplift_train.csv.gz"
MEGAFON = RAW / "megafon_dataset.csv.gz"
MARKETING_AB = KAGGLEHUB / "faviovaz" / "marketing-ab-testing" / "versions" / "1" / "marketing_AB.csv"
FACEBOOK_ADS = KAGGLEHUB / "loveall" / "clicks-conversion-tracking" / "versions" / "1" / "KAG_conversion_data.csv"
OLIST_DIR = KAGGLEHUB / "olistbr" / "brazilian-ecommerce" / "versions" / "2"

for p in (PROCESSED, RESULTS, FIGURES, EXCEL, DECK, DASHBOARDS, MODELS,
          REPORTS):
    p.mkdir(parents=True, exist_ok=True)
