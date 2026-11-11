"""Phase 7: build excel/measurement_tracker.xlsx — a workbook a measurement
team could actually use.

Every analytical number in the workbook is a LIVE FORMULA (SUMIFS, XLOOKUP,
LET, NORM.S.DIST, SUMPRODUCT...), not a pasted value. The Checks sheet puts
the Python pipeline's numbers next to the Excel formulas and shows the
difference; open the file in Excel and every diff should read ~0.

Native PivotTables cannot be written by xlsxwriter; Pivot_View holds the same
cross-tab built from SUMIFS plus one-line instructions for inserting a real
PivotTable from the Data_Campaigns table (Insert > PivotTable > Campaigns).
"""
from __future__ import annotations

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from . import paths

VALUE_PER_CONVERSION = 50.0


def build() -> None:
    raw = pd.read_csv(paths.FACEBOOK_ADS)
    raw = raw.rename(columns={
        "xyz_campaign_id": "campaign_id", "Impressions": "impressions",
        "Clicks": "clicks", "Spent": "spend", "Approved_Conversion": "conversions",
    })[["ad_id", "campaign_id", "age", "gender", "interest",
        "impressions", "clicks", "spend", "conversions"]]
    kpi_dict = pd.read_csv(paths.RESULTS / "kpi_dictionary.csv")
    lift = pd.read_csv(paths.RESULTS / "lift_results.csv")
    meta_studies = pd.read_csv(paths.RESULTS / "meta_studies.csv")
    meta_results = pd.read_csv(paths.RESULTS / "meta_results.csv")
    rollup = pd.read_csv(paths.RESULTS / "campaign_rollup.csv")
    weekly = pd.read_csv(paths.RESULTS / "weekly_ecom.csv")

    out = paths.EXCEL / "measurement_tracker.xlsx"
    wb = xlsxwriter.Workbook(str(out), {"use_future_functions": True})

    # ---------------------------------------------------------- formats
    h1 = wb.add_format({"bold": True, "font_size": 16, "font_color": "#0b0b0b"})
    h2 = wb.add_format({"bold": True, "font_size": 12, "font_color": "#2a78d6"})
    head = wb.add_format({"bold": True, "bg_color": "#eef3fa", "border": 1,
                          "border_color": "#c9d4e4"})
    note = wb.add_format({"font_color": "#52514e", "italic": True})
    num4 = wb.add_format({"num_format": "0.0000"})
    num2 = wb.add_format({"num_format": "0.00"})
    pct2 = wb.add_format({"num_format": "0.00%"})
    money = wb.add_format({"num_format": "#,##0.00"})
    intf = wb.add_format({"num_format": "#,##0"})
    input_fmt = wb.add_format({"bg_color": "#fff7e6", "border": 1,
                               "border_color": "#eda100", "num_format": "0.00"})
    good = wb.add_format({"bg_color": "#e8f5e9", "font_color": "#1b5e20"})
    bad = wb.add_format({"bg_color": "#fdecea", "font_color": "#b71c1c"})

    def sheet_title(ws, title, subtitle=None):
        ws.write(0, 0, title, h1)
        if subtitle:
            ws.write(1, 0, subtitle, note)

    # ---------------------------------------------------------- README
    ws = wb.add_worksheet("README")
    sheet_title(ws, "Measurement tracker — Ad Measurement Study",
                "Public datasets, personal project. Version 1.0.")
    rows = [
        ("", ""),
        ("Purpose", "One workbook that computes campaign KPIs, reads any A/B test, "
                    "and pools experiments — with every number as a live formula."),
        ("", ""),
        ("Sheet guide", ""),
        ("KPI_Dictionary", "每 metric: formula, unit, edge cases".replace("每", "Every")),
        ("Data_Campaigns", "Facebook ad campaign data (Kaggle) as an Excel Table"),
        ("KPI_Calc", "Per-campaign KPIs from SUMIFS over the table — sums first, ratios second"),
        ("Pivot_View", "Campaign x age cross-tab from formulas; see note for a native PivotTable"),
        ("Scenario", "Value-per-conversion assumption drives ROAS and break-even CPA"),
        ("Experiment_Calc", "Type four counts from any A/B test; lift, interval, z, p and MDE recalc"),
        ("Meta_Analysis", "Six studies pooled: fixed effect and random effects, Q and I-squared"),
        ("Tracker", "Study/task tracker with a status dropdown and conditional formats"),
        ("Dashboard", "KPI tiles and two charts fed by the sheets above"),
        ("Checks", "Python pipeline numbers vs Excel formulas; differences should be ~0"),
        ("", ""),
        ("Data sources and licences", ""),
        ("Criteo Uplift v2.1", "Criteo AI Lab via Hugging Face — CC BY-NC-SA 4.0"),
        ("Hillstrom e-mail", "MineThatData challenge — free for analysis, credit the source"),
        ("Marketing A/B, Facebook ads, Olist", "Kaggle — non-commercial research, credit the source"),
        ("Lenta / X5 / MegaFon", "scikit-uplift mirrors of public uplift datasets"),
    ]
    for i, (a, b) in enumerate(rows, start=2):
        ws.write(i, 0, a, h2 if b == "" and a else None)
        ws.write(i, 1, b)
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 95)

    # ---------------------------------------------------- KPI_Dictionary
    ws = wb.add_worksheet("KPI_Dictionary")
    sheet_title(ws, "KPI dictionary", "The definitions every other sheet uses.")
    for c, col in enumerate(["Metric", "Formula", "Unit", "Edge cases"]):
        ws.write(3, c, col, head)
    for r, row in kpi_dict.iterrows():
        ws.write(4 + r, 0, row["metric"])
        ws.write(4 + r, 1, row["formula"])
        ws.write(4 + r, 2, row["unit"])
        ws.write(4 + r, 3, row["edge_cases"])
    ws.set_column(0, 0, 26); ws.set_column(1, 1, 44)
    ws.set_column(2, 2, 24); ws.set_column(3, 3, 80)

    # ---------------------------------------------------- Data_Campaigns
    ws = wb.add_worksheet("Data_Campaigns")
    n = len(raw)
    cols = list(raw.columns)
    ws.add_table(0, 0, n, len(cols) - 1, {
        "name": "Campaigns",
        "columns": [{"header": c} for c in cols],
        "style": "Table Style Light 9",
    })
    for r, row in raw.iterrows():
        for c, col in enumerate(cols):
            ws.write(r + 1, c, row[col])
    ws.set_column(0, len(cols) - 1, 12)

    # -------------------------------------------------------- KPI_Calc
    ws = wb.add_worksheet("KPI_Calc")
    sheet_title(ws, "Campaign KPIs from structured references",
                "Sums first, ratios second — never an average of ad-level ratios.")
    headers = ["campaign_id", "ads", "impressions", "clicks", "spend",
               "conversions", "CTR", "CPM", "CPC", "CVR", "CPA"]
    for c, col in enumerate(headers):
        ws.write(3, c, col, head)
    camps = sorted(raw["campaign_id"].unique())
    for i, camp in enumerate(camps):
        r = 4 + i
        ws.write_number(r, 0, camp)
        a = f"$A{r + 1}"
        ws.write_formula(r, 1, f"=COUNTIF(Campaigns[campaign_id],{a})", intf)
        ws.write_formula(r, 2, f"=SUMIFS(Campaigns[impressions],Campaigns[campaign_id],{a})", intf)
        ws.write_formula(r, 3, f"=SUMIFS(Campaigns[clicks],Campaigns[campaign_id],{a})", intf)
        ws.write_formula(r, 4, f"=SUMIFS(Campaigns[spend],Campaigns[campaign_id],{a})", money)
        ws.write_formula(r, 5, f"=SUMIFS(Campaigns[conversions],Campaigns[campaign_id],{a})", intf)
        ws.write_formula(r, 6, f"=IFERROR(D{r+1}/C{r+1},\"\")", num4)
        ws.write_formula(r, 7, f"=IFERROR(E{r+1}/C{r+1}*1000,\"\")", num4)
        ws.write_formula(r, 8, f"=IFERROR(E{r+1}/D{r+1},\"\")", num2)
        ws.write_formula(r, 9, f"=IFERROR(F{r+1}/D{r+1},\"\")", num4)
        ws.write_formula(r, 10, f"=IFERROR(E{r+1}/F{r+1},\"\")", num2)
    tot = 4 + len(camps)
    ws.write(tot, 0, "TOTAL", head)
    for c, l in [(1, "B"), (2, "C"), (3, "D"), (4, "E"), (5, "F")]:
        ws.write_formula(tot, c, f"=SUM({l}5:{l}{tot})",
                         money if l == "E" else intf)
    ws.write_formula(tot, 10, f"=IFERROR(E{tot+1}/F{tot+1},\"\")", num2)
    ws.write(tot + 2, 0, "XLOOKUP + LET example — CPA of the campaign typed in M2:", note)
    ws.write(3, 12, "campaign", head)
    ws.write_number(1, 12, camps[-1], input_fmt)
    ws.write_formula(
        1, 13,
        f"=LET(c,M2, s,SUMIFS(Campaigns[spend],Campaigns[campaign_id],c), "
        f"v,SUMIFS(Campaigns[conversions],Campaigns[campaign_id],c), "
        f"IF(v=0,\"no conversions\",s/v))", num2)
    ws.write(0, 13, "its CPA:", note)
    ws.set_column(0, 10, 12); ws.set_column(12, 13, 14)

    # ------------------------------------------------------- Pivot_View
    ws = wb.add_worksheet("Pivot_View")
    sheet_title(ws, "Campaign x age cross-tab (formula-built)",
                "For a native PivotTable with slicers: select any cell in "
                "Data_Campaigns, Insert > PivotTable; rows campaign_id, "
                "columns age, values Sum of spend. This sheet computes the "
                "same cross-tab from SUMIFS so the numbers live-update too.")
    ages = sorted(raw["age"].unique())
    ws.write(4, 0, "spend by campaign x age", h2)
    for c, agev in enumerate(ages):
        ws.write(5, 1 + c, agev, head)
    ws.write(5, 1 + len(ages), "total", head)
    for i, camp in enumerate(camps):
        r = 6 + i
        ws.write_number(r, 0, camp, head)
        for c, agev in enumerate(ages):
            ws.write_formula(
                r, 1 + c,
                f"=SUMIFS(Campaigns[spend],Campaigns[campaign_id],$A{r+1},"
                f"Campaigns[age],{xl_rowcol_to_cell(5, 1 + c, row_abs=True)})",
                money)
        ws.write_formula(r, 1 + len(ages),
                         f"=SUM(B{r+1}:{chr(ord('B') + len(ages) - 1)}{r+1})", money)
    ws.set_column(0, len(ages) + 1, 13)

    # --------------------------------------------------------- Scenario
    ws = wb.add_worksheet("Scenario")
    sheet_title(ws, "Scenario: what is a conversion worth?",
                "The data has no revenue column, so ROAS exists only under an "
                "assumption. Change the orange cell; everything recalculates. "
                "Goal Seek (Data > What-If Analysis) on B6 to 1.0 by changing "
                "B4 finds the break-even value per conversion.")
    ws.write(3, 0, "Value per conversion (USD) — ASSUMPTION", head)
    ws.write_number(3, 1, VALUE_PER_CONVERSION, input_fmt)
    ws.data_validation(3, 1, 3, 1, {
        "validate": "decimal", "criteria": ">=", "value": 0,
        "input_title": "Assumed value per conversion",
        "input_message": "USD per approved conversion. An assumption, not data.",
    })
    ws.write(5, 0, "Total ROAS at this value", head)
    ws.write_formula(5, 1, "=KPI_Calc!F8*B4/KPI_Calc!E8", num2)
    ws.write(6, 0, "Break-even CPA (= value per conversion)", head)
    ws.write_formula(6, 1, "=B4", money)
    ws.write(8, 0, "Per campaign", h2)
    for c, col in enumerate(["campaign_id", "spend", "conversions", "CPA",
                             "ROAS at assumed value", "profitable at this value?"]):
        ws.write(9, c, col, head)
    for i in range(len(camps)):
        r = 10 + i
        k = 5 + i  # KPI_Calc row (1-based)
        ws.write_formula(r, 0, f"=KPI_Calc!A{k}")
        ws.write_formula(r, 1, f"=KPI_Calc!E{k}", money)
        ws.write_formula(r, 2, f"=KPI_Calc!F{k}", intf)
        ws.write_formula(r, 3, f"=KPI_Calc!K{k}", num2)
        ws.write_formula(r, 4, f"=IFERROR(C{r+1}*$B$4/B{r+1},\"\")", num2)
        ws.write_formula(r, 5, f"=IF(E{r+1}>=1,\"yes\",\"no\")")
    ws.conditional_format(10, 5, 9 + len(camps), 5, {
        "type": "cell", "criteria": "==", "value": '"yes"', "format": good})
    ws.conditional_format(10, 5, 9 + len(camps), 5, {
        "type": "cell", "criteria": "==", "value": '"no"', "format": bad})
    ws.set_column(0, 5, 22)

    # -------------------------------------------------- Experiment_Calc
    ws = wb.add_worksheet("Experiment_Calc")
    sheet_title(ws, "Read any A/B test from four counts",
                "Type the four orange counts; everything below recalculates. "
                "Pre-filled with the Hillstrom e-mail test.")
    hl = lift[lift.study == "hillstrom"].iloc[0]
    inputs = [("Treated users (N_t)", int(hl.n_treated)),
              ("Treated conversions (X_t)", int(hl.events_treated)),
              ("Control users (N_c)", int(hl.n_control)),
              ("Control conversions (X_c)", int(hl.events_control))]
    for i, (lab, val) in enumerate(inputs):
        ws.write(3 + i, 0, lab, head)
        ws.write_number(3 + i, 1, val, input_fmt)
    calc = [
        ("Treated rate", "=B5/B4", pct2),
        ("Control rate", "=B7/B6", pct2),
        ("Absolute lift (pp)", "=(B9-B10)*100", num4),
        ("Relative lift", "=(B9-B10)/B10", pct2),
        ("Incremental conversions", "=(B9-B10)*B4", num2),
        ("SE of the lift (unpooled)", "=SQRT(B9*(1-B9)/B4+B10*(1-B10)/B6)", num4),
        ("95% CI low (pp)", "=((B9-B10)-1.959964*B14)*100", num4),
        ("95% CI high (pp)", "=((B9-B10)+1.959964*B14)*100", num4),
        ("Pooled rate", "=(B5+B7)/(B4+B6)", pct2),
        ("SE under the null (pooled)", "=SQRT(B17*(1-B17)*(1/B4+1/B6))", num4),
        ("z", "=(B9-B10)/B18", num2),
        ("p-value (two-sided)", "=2*(1-NORM.S.DIST(ABS(B19),TRUE))", num4),
        ("MDE abs (pp), 80% power, alpha 5%",
         "=(1.959964+0.841621)*SQRT(B10*(1-B10)*(1/B4+1/B6))*100", num4),
        ("Verdict", "=IF(OR(B15>0,B16<0),\"lift detected\","
                    "IF(B21>B10*0.1*100,\"we could not tell (underpowered)\","
                    "\"no meaningful effect\"))", None),
    ]
    for i, (lab, formula, fmt) in enumerate(calc):
        r = 8 + i
        ws.write(r, 0, lab, head)
        ws.write_formula(r, 1, formula, fmt)
    ws.set_column(0, 0, 34); ws.set_column(1, 1, 18)

    # ---------------------------------------------------- Meta_Analysis
    ws = wb.add_worksheet("Meta_Analysis")
    sheet_title(ws, "Pooling the six experiments",
                "Log risk ratios, inverse-variance weights, fixed effect, "
                "DerSimonian–Laird random effects. Only counts are pasted; "
                "every statistic is a formula.")
    cols = ["study", "X_t", "N_t", "X_c", "N_c", "log RR", "variance",
            "weight (FE)", "RE weight"]
    for c, col in enumerate(cols):
        ws.write(3, c, col, head)
    k = len(meta_studies)
    first, last = 5, 4 + k  # 1-based data rows
    for i, row in meta_studies.iterrows():
        r = 4 + i
        ws.write(r, 0, row["study"])
        ws.write_number(r, 1, int(row["x_t"]), intf)
        ws.write_number(r, 2, int(row["n_t"]), intf)
        ws.write_number(r, 3, int(row["x_c"]), intf)
        ws.write_number(r, 4, int(row["n_c"]), intf)
        ws.write_formula(r, 5, f"=LN((B{r+1}/C{r+1})/(D{r+1}/E{r+1}))", num4)
        ws.write_formula(r, 6, f"=1/B{r+1}-1/C{r+1}+1/D{r+1}-1/E{r+1}", num4)
        ws.write_formula(r, 7, f"=1/G{r+1}", num2)
        ws.write_formula(r, 8, f"=1/(G{r+1}+$B${last+9})", num2)
    stats = [
        ("k (studies)", f"=COUNT(G{first}:G{last})", intf),
        ("Fixed effect (log)", f"=SUMPRODUCT(H{first}:H{last},F{first}:F{last})/SUM(H{first}:H{last})", num4),
        ("Fixed effect SE", f"=SQRT(1/SUM(H{first}:H{last}))", num4),
        ("Fixed RR", f"=EXP(B{last+2})", num4),
        ("Fixed RR 95% CI low", f"=EXP(B{last+2}-1.959964*B{last+3})", num4),
        ("Fixed RR 95% CI high", f"=EXP(B{last+2}+1.959964*B{last+3})", num4),
        ("Q", f"=SUMPRODUCT(H{first}:H{last},(F{first}:F{last}-B{last+2})^2)", num2),
        ("I² = (Q-df)/Q", f"=MAX(0,(B{last+7}-(B{last+1}-1))/B{last+7})", pct2),
        ("tau² (DL)",
         f"=MAX(0,(B{last+7}-(B{last+1}-1))/(SUM(H{first}:H{last})-SUMSQ(H{first}:H{last})/SUM(H{first}:H{last})))",
         num4),
        ("Random effect (log)", f"=SUMPRODUCT(I{first}:I{last},F{first}:F{last})/SUM(I{first}:I{last})", num4),
        ("Random effect SE", f"=SQRT(1/SUM(I{first}:I{last}))", num4),
        ("Random RR", f"=EXP(B{last+10})", num4),
        ("Random RR 95% CI low", f"=EXP(B{last+10}-1.959964*B{last+11})", num4),
        ("Random RR 95% CI high", f"=EXP(B{last+10}+1.959964*B{last+11})", num4),
    ]
    for i, (lab, formula, fmt) in enumerate(stats):
        r = last + i  # 0-based; 1-based row = last+1+i, matching the B refs above
        ws.write(r, 0, lab, head)
        ws.write_formula(r, 1, formula, fmt)
    ws.set_column(0, 0, 24); ws.set_column(1, 8, 13)

    # ---------------------------------------------------------- Tracker
    ws = wb.add_worksheet("Tracker")
    sheet_title(ws, "Study and task tracker")
    track_cols = ["item", "owner", "status", "last_updated", "notes"]
    for c, col in enumerate(track_cols):
        ws.write(3, c, col, head)
    items = [
        ("Criteo lift + intervals", "Vikram", "Done", "analysed by assignment (ITT)"),
        ("Hillstrom lift + CUPED", "Vikram", "Done", "CUPED narrowed CI by ~0% — reported honestly"),
        ("Marketing A/B lift", "Vikram", "Done", "control saw a PSA, not nothing"),
        ("Lenta lift", "Vikram", "Done", "intended split undocumented — SRM recorded only"),
        ("X5 lift", "Vikram", "Done", "SMS promotion, labelled as such"),
        ("MegaFon lift", "Vikram", "Done", "synthetic features"),
        ("Meta-analysis", "Vikram", "Done", "I² 99.7% — pooled number is a summary, not a law"),
        ("Uplift model", "Vikram", "Done", "Criteo strong, Hillstrom barely above random"),
        ("Olist monitor + diagnosis", "Vikram", "Done", "association only"),
        ("Tableau / Looker dashboards", "Vikram", "In progress", "CSV exports ready in dashboards/"),
        ("Geographic holdout proposal", "Vikram", "Not started", "the real next test"),
    ]
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    for i, (item, owner, status, notes_v) in enumerate(items):
        r = 4 + i
        ws.write(r, 0, item); ws.write(r, 1, owner)
        ws.write(r, 2, status); ws.write(r, 3, today); ws.write(r, 4, notes_v)
    last_tr = 4 + len(items) - 1
    ws.data_validation(4, 2, last_tr, 2, {
        "validate": "list", "source": ["Not started", "In progress", "Done", "Blocked"]})
    ws.conditional_format(4, 2, last_tr, 2, {
        "type": "cell", "criteria": "==", "value": '"Done"', "format": good})
    ws.conditional_format(4, 2, last_tr, 2, {
        "type": "cell", "criteria": "==", "value": '"Blocked"', "format": bad})
    ws.set_column(0, 0, 30); ws.set_column(1, 3, 14); ws.set_column(4, 4, 60)

    # ---------------------------------------------------- Dashboard data
    wsd = wb.add_worksheet("Data_Weekly")
    wsd.write_row(0, 0, ["week", "orders", "late_share", "avg_review_score"])
    for i, row in weekly.iterrows():
        wsd.write(i + 1, 0, str(row["purchase_week"])[:10])
        wsd.write_number(i + 1, 1, float(row["orders"]))
        wsd.write_number(i + 1, 2, float(row["late_share"]))
        wsd.write_number(i + 1, 3, float(row["avg_review_score"]))
    wsd.hide()

    # -------------------------------------------------------- Dashboard
    ws = wb.add_worksheet("Dashboard")
    sheet_title(ws, "Measurement dashboard",
                "Tiles and charts update from the sheets above.")
    tiles = [
        ("Total ad spend (USD)", "=KPI_Calc!E8", money),
        ("Approved conversions", "=KPI_Calc!F8", intf),
        ("Blended CPA (USD)", "=KPI_Calc!K8", num2),
        ("Pooled RR (random effects)", f"=Meta_Analysis!B{last+12}", num4),
        ("Hillstrom lift (pp)", "=Experiment_Calc!B11", num4),
        ("Scenario ROAS", "=Scenario!B6", num2),
    ]
    for i, (lab, f, fmt) in enumerate(tiles):
        r, c = 3 + (i // 3) * 3, (i % 3) * 3
        ws.write(r, c, lab, head)
        ws.write_formula(r + 1, c, f, fmt)
    chart1 = wb.add_chart({"type": "column"})
    nk = len(camps)
    chart1.add_series({
        "name": "CPA by campaign",
        "categories": f"=KPI_Calc!$A$5:$A${4+nk}",
        "values": f"=KPI_Calc!$K$5:$K${4+nk}",
        "fill": {"color": "#2a78d6"},
    })
    chart1.set_title({"name": "Campaign 1178 pays the most per conversion"})
    chart1.set_legend({"none": True})
    ws.insert_chart(10, 0, chart1, {"x_scale": 1.1, "y_scale": 1.1})
    chart2 = wb.add_chart({"type": "line"})
    nw = len(weekly)
    chart2.add_series({
        "name": "Weekly orders",
        "categories": f"=Data_Weekly!$A$2:$A${nw+1}",
        "values": f"=Data_Weekly!$B$2:$B${nw+1}",
        "line": {"color": "#2a78d6", "width": 2},
    })
    chart2.set_title({"name": "Olist weekly delivered orders"})
    chart2.set_legend({"none": True})
    ws.insert_chart(10, 6, chart2, {"x_scale": 1.1, "y_scale": 1.1})

    # ----------------------------------------------------------- Checks
    ws = wb.add_worksheet("Checks")
    sheet_title(ws, "Python vs Excel — two independent calculations",
                "Left: the Python pipeline's numbers (results/*.csv). Right: "
                "this workbook's formulas. Open in Excel; every diff should "
                "be ~0. A nonzero diff is a bug, and finding it is the point.")
    for c, col in enumerate(["check", "python", "excel formula result", "diff", "pass?"]):
        ws.write(3, c, col, head)
    fe_rr = float(meta_results.loc[meta_results.model == "fixed effect", "rr"].iloc[0])
    re_rr = float(meta_results.loc[meta_results.model.str.startswith("random"), "rr"].iloc[0])
    i2 = float(meta_results["I2"].iloc[0])
    checks = [
        ("total spend", float(rollup["spend"].sum()), "=KPI_Calc!E8"),
        ("total conversions", float(rollup["conversions"].sum()), "=KPI_Calc!F8"),
        ("blended CPA", float(rollup["spend"].sum() / rollup["conversions"].sum()),
         "=KPI_Calc!K8"),
        ("Hillstrom abs lift (pp)", float(hl["abs_lift_pp"]), "=Experiment_Calc!B11"),
        ("Hillstrom CI low (pp)", float(hl["ci_low_pp"]), "=Experiment_Calc!B15"),
        ("Hillstrom CI high (pp)", float(hl["ci_high_pp"]), "=Experiment_Calc!B16"),
        ("Hillstrom z", float(hl["z"]), "=Experiment_Calc!B19"),
        ("Hillstrom MDE (pp)", float(hl["mde_abs_pp"]), "=Experiment_Calc!B21"),
        ("Fixed-effect RR", fe_rr, f"=Meta_Analysis!B{last+4}"),
        ("Random-effects RR", re_rr, f"=Meta_Analysis!B{last+12}"),
        ("I²", i2, f"=Meta_Analysis!B{last+8}"),
    ]
    for i, (lab, py, formula) in enumerate(checks):
        r = 4 + i
        ws.write(r, 0, lab)
        ws.write_number(r, 1, py, num4)
        ws.write_formula(r, 2, formula, num4)
        ws.write_formula(r, 3, f"=C{r+1}-B{r+1}", num4)
        ws.write_formula(r, 4, f"=IF(ABS(D{r+1})<0.0001,\"PASS\",\"CHECK\")")
    lastc = 4 + len(checks) - 1
    ws.conditional_format(4, 4, lastc, 4, {
        "type": "cell", "criteria": "==", "value": '"PASS"', "format": good})
    ws.conditional_format(4, 4, lastc, 4, {
        "type": "cell", "criteria": "==", "value": '"CHECK"', "format": bad})
    ws.set_column(0, 0, 28); ws.set_column(1, 4, 20)

    wb.close()
    print(f"wrote {out}")


if __name__ == "__main__":
    build()
