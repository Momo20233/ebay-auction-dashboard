"""FastAPI backend for eBay Auction Parameter Recommendation Dashboard."""
import json
import os
import threading
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from data_loader import load_and_prepare
from simulation import recommend, simulate_new_product

# ── Config ────────────────────────────────────────────────────────────────────
EXCEL_PATH = Path(__file__).parent.parent / "NYU Capstone - eBay Auction Simulation Data_副本.xlsx"
CACHE_FILE = Path(__file__).parent / "cache" / "recommendations.json"
CACHE_FILE.parent.mkdir(exist_ok=True)

N_SIM_CACHE = 30   # simulations per grid combo for background cache

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="eBay Auction Dashboard")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
_HTML_PATH = Path(__file__).parent / "templates" / "index.html"

# ── Global state ──────────────────────────────────────────────────────────────
_df   = None
_recs: dict | None = None
_lock = threading.Lock()
_sim_state = {"running": False, "progress": 0, "total": 0, "done": False, "error": None}


def _get_df():
    global _df
    if _df is None:
        _df = load_and_prepare(str(EXCEL_PATH))
    return _df


def _get_recs() -> dict | None:
    global _recs
    with _lock:
        if _recs is not None:
            return _recs
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                data = json.load(f)
            _recs = {r["product_id"]: r for r in data}
            return _recs
    return None


def _run_simulations():
    global _recs, _sim_state
    try:
        df    = _get_df()
        total = len(df)
        _sim_state.update(running=True, progress=0, total=total, done=False, error=None)

        results = []
        for i, (_, row) in enumerate(df.iterrows()):
            rec = recommend(
                product_id   = str(row["product_id"]),
                market_price = float(row["market_price"]),
                function_type= str(row["function_type"]),
                viewers      = int(row["viewers"]),
                n_sim        = N_SIM_CACHE,
            )
            if rec:
                results.append(rec)
            _sim_state["progress"] = i + 1

        with open(CACHE_FILE, "w") as f:
            json.dump(results, f, indent=2)

        with _lock:
            _recs = {r["product_id"]: r for r in results}

        _sim_state.update(done=True, running=False)

    except Exception as exc:
        _sim_state.update(running=False, error=str(exc))
        raise


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup():
    df = _get_df()
    if CACHE_FILE.exists():
        _get_recs()
        _sim_state.update(done=True, running=False)
    else:
        _sim_state["total"] = len(df)
        threading.Thread(target=_run_simulations, daemon=True).start()


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def index():
    return HTMLResponse(_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/api/portfolio")
async def portfolio():
    df   = _get_df()
    recs = _get_recs()

    actual_gmv = float(df["final_price"].sum())
    avg_bids   = float(df["total_bids"].mean())

    sim_avg_str = None
    if recs:
        sim_avg_str = round(float(np.mean([r.get("sell_through_rate", 0.7)
                                           for r in recs.values()])), 3)

    strategy_dist = df["function_type"].value_counts().to_dict()

    return {
        "actual_gmv":   round(actual_gmv, 2),
        "products":     len(df),
        "avg_bids":     round(avg_bids, 1),
        "sim_avg_str":  sim_avg_str,
        "baseline_str": 0.58,
        "strategy_dist": strategy_dist,
        "sim_ready":    recs is not None,
    }


@app.get("/api/products")
async def products():
    df   = _get_df()
    recs = _get_recs()

    rows = []
    for _, row in df.iterrows():
        pid = str(row["product_id"])
        item = {
            "product_id":          pid,
            "short_title":         str(row["short_title"]),
            "category":            str(row.get("category_short", "")),
            "condition":           str(row.get("condition", "")),
            "market_price":        round(float(row["market_price"]),    2),
            "actual_start_price":  round(float(row["start_price"]),     2),
            "actual_sp_ratio":     round(float(row["actual_sp_ratio"]), 3),
            "actual_interval":     round(float(row["bid_increment"]),   2),
            "actual_duration_hrs": int(row["duration_hours"]),
            "actual_bidders":      int(row["number_of_bidders"]),
            "actual_bids":         int(row["total_bids"]),
            "actual_final_price":  round(float(row["final_price"]),     2),
            "function_type":       str(row["function_type"]),
            "is_virtual":          bool(row["is_virtual"]),
        }

        if recs and pid in recs:
            r = recs[pid]
            item.update({
                "rec_start_price":       r.get("rec_start_price"),
                "rec_start_price_ratio": r.get("rec_start_price_ratio"),
                "rec_interval":          r.get("rec_price_interval"),
                "rec_duration":          r.get("rec_duration"),
                "sim_str":               r.get("sell_through_rate"),
                "sim_p50":               r.get("price_p50"),
                "avg_bids_sim":          r.get("avg_bids"),
                "expected_score":        r.get("expected_score"),
            })

        rows.append(item)

    return {"products": rows, "sim_ready": recs is not None}


@app.get("/api/sim/status")
async def sim_status():
    return _sim_state


@app.post("/api/sim/new")
async def sim_new(data: dict):
    market_price  = float(data.get("market_price", 100))
    function_type = str(data.get("function_type", "GMV"))
    viewers       = int(data.get("viewers", 80))

    if market_price <= 0:
        return JSONResponse({"error": "Invalid market price"}, status_code=400)

    result = simulate_new_product(market_price, function_type, viewers)
    return result


@app.post("/api/refresh")
async def refresh():
    global _recs
    if _sim_state["running"]:
        return JSONResponse({"error": "Already running"}, status_code=400)
    CACHE_FILE.unlink(missing_ok=True)
    with _lock:
        _recs = None
    _sim_state.update(done=False)
    threading.Thread(target=_run_simulations, daemon=True).start()
    return {"status": "started"}


@app.get("/api/charts/funnel")
async def funnel():
    df          = _get_df()
    avg_watch   = float(df["watch_count"].mean())
    avg_bidders = float(df["number_of_bidders"].mean())
    interested  = avg_watch * 0.25
    winners     = avg_bidders * 0.72

    return {
        "stages": ["Viewers", "Interested", "Active Bidders", "Winners (sold)"],
        "values": [round(avg_watch, 1), round(interested, 1),
                   round(avg_bidders, 1), round(winners, 1)],
        "pcts":   [100,
                   round(interested  / avg_watch * 100, 1),
                   round(avg_bidders / avg_watch * 100, 1),
                   round(winners     / avg_watch * 100, 1)],
        "colors": ["#378ADD", "#1D9E75", "#D85A30", "#BA7517"],
    }


@app.get("/api/charts/distribution")
async def distribution():
    # Pre-computed theoretical simulation data (from notebook n=300)
    return {
        "labels": ["50%","60%","70%","80%","90%","100%","110%","120%","130%","140%"],
        "datasets": {
            "SP=30%": [32, 45, 62, 80,  95,  108, 118, 124, 128, 130],
            "SP=50%": [55, 68, 82, 98,  112, 125, 132, 136, 138, 139],
            "SP=70%": [72, 85, 99, 112, 124, 133, 137, 139, 140, 140],
            "SP=90%": [91,102,114, 125, 132, 136, 138, 139, 140, 140],
        },
    }


@app.get("/api/charts/str")
async def str_chart():
    df = _get_df()

    # Theoretical curve (from simulation)
    theo_ratios = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    theo_str    = [0.91, 0.86, 0.80, 0.75, 0.68, 0.60, 0.51]

    # Empirical distribution of actual start-price ratios in the dataset
    buckets = (df["actual_sp_ratio"] * 10).round() / 10
    emp     = buckets.value_counts().sort_index()

    return {
        "theoretical": {"ratios": theo_ratios, "str": theo_str},
        "empirical":   {"ratios": emp.index.tolist(), "counts": emp.values.tolist()},
    }


@app.get("/api/charts/scatter")
async def scatter():
    df   = _get_df()
    recs = _get_recs()

    rows = []
    for _, row in df.iterrows():
        pid = str(row["product_id"])
        str_val = recs[pid]["sell_through_rate"] if recs and pid in recs else None
        rows.append({
            "product_id":    pid,
            "market_price":  round(float(row["market_price"]), 2),
            "function_type": str(row["function_type"]),
            "sim_str":       str_val,
            "actual_sp_ratio": round(float(row["actual_sp_ratio"]), 3),
            "title":         str(row["short_title"]),
        })

    return {"points": rows}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
