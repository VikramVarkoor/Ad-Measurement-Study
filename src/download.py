"""`make data`: fetch every public dataset into data/raw/ (nothing committed).

Direct URLs are used where the publisher offers one; the three Kaggle
datasets come through kagglehub's anonymous download of public datasets.
Each file is skipped if already present, so the command is idempotent.
"""
from __future__ import annotations

import os
import shutil
import urllib.request

from . import paths

DIRECT = {
    # official Criteo release, mirrored by Criteo on Hugging Face (CC BY-NC-SA 4.0)
    paths.CRITEO: "https://huggingface.co/datasets/criteo/criteo-uplift/resolve/main/criteo-research-uplift-v2.1.csv.gz",
    # Kevin Hillstrom's MineThatData challenge file
    paths.HILLSTROM: "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
    # scikit-uplift mirrors of the public uplift datasets
    paths.LENTA: "https://sklift.s3.eu-west-2.amazonaws.com/lenta_dataset.csv.gz",
    paths.X5_TRAIN: "https://sklift.s3.eu-west-2.amazonaws.com/uplift_train.csv.gz",
    paths.MEGAFON: "https://sklift.s3.eu-west-2.amazonaws.com/megafon_dataset.csv.gz",
}

KAGGLE = [
    "faviovaz/marketing-ab-testing",
    "loveall/clicks-conversion-tracking",
    "olistbr/brazilian-ecommerce",
]


def run() -> None:
    paths.RAW.mkdir(parents=True, exist_ok=True)
    for dest, url in DIRECT.items():
        if dest.exists():
            print(f"have    {dest.name}")
            continue
        print(f"fetch   {dest.name}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(dest)

    os.environ.setdefault("KAGGLEHUB_CACHE", str(paths.RAW / "kagglehub"))
    import kagglehub
    for ds in KAGGLE:
        print(f"kaggle  {ds}")
        kagglehub.dataset_download(ds)

    from .experiments import materialize
    materialize("criteo")
    print("done: raw files in data/raw/, criteo materialized to parquet")


if __name__ == "__main__":
    run()
