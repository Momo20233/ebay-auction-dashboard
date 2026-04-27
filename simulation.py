"""Monte Carlo auction simulation engine."""
import numpy as np
import itertools

# ── Grid search parameter space ──────────────────────────────────────────────
GRID_SP_RATIOS  = [0.3, 0.5, 0.6, 0.8]        # start price / market price
GRID_PI_RATIOS  = [0.01, 0.02, 0.05]           # price interval / market price
GRID_DURATIONS  = [30, 60, 90]                  # auction rounds

GRID_INTERACTIVE_SP = [0.3, 0.5, 0.7]
GRID_INTERACTIVE_PI = [0.01, 0.02, 0.05]
GRID_INTERACTIVE_DUR = [30, 60, 90]


# ── Core simulation ───────────────────────────────────────────────────────────

def _run_auction(market_price: float, start_price: float,
                 price_interval: float, duration: int, viewers: int) -> dict:
    n = max(2, int(viewers * 0.25))
    valuations  = np.random.normal(market_price * 0.85, market_price * 0.2, n).clip(min=1.0)
    active_prob = np.clip(np.random.normal(0.4, 0.1, n), 0.05, 0.95)

    price = float(start_price)
    bids  = 0

    for _ in range(duration):
        order = np.random.permutation(n)
        for i in order:
            if price < valuations[i] and np.random.rand() < active_prob[i]:
                price += price_interval
                bids  += 1

    return {"final_price": price, "bid_count": bids, "sold": price > start_price}


def _simulate_many(n_sim: int, market_price: float, start_price: float,
                   price_interval: float, duration: int, viewers: int) -> dict:
    res    = [_run_auction(market_price, start_price, price_interval, duration, viewers)
              for _ in range(n_sim)]
    prices = [r["final_price"] for r in res]
    bids   = [r["bid_count"]   for r in res]
    sold   = [r["sold"]        for r in res]
    return {
        "price_mean":        float(np.mean(prices)),
        "price_p10":         float(np.percentile(prices, 10)),
        "price_p50":         float(np.percentile(prices, 50)),
        "price_p90":         float(np.percentile(prices, 90)),
        "avg_bids":          float(np.mean(bids)),
        "sell_through_rate": float(np.mean(sold)),
    }


def _score(sim: dict, function_type: str) -> float:
    gmv  = sim["price_mean"] * sim["sell_through_rate"]
    fast = sim["sell_through_rate"] * np.log1p(sim["avg_bids"]) * 100
    if function_type == "GMV":
        return gmv
    if function_type == "traffic":
        return fast
    return 0.6 * gmv + 0.4 * fast   # custom: balanced


# ── Public API ────────────────────────────────────────────────────────────────

def recommend(product_id: str, market_price: float, function_type: str,
              viewers: int = 80, n_sim: int = 30) -> dict:
    """Grid search to find optimal auction parameters for one product."""
    best_score = -np.inf
    best       = None

    grid = list(itertools.product(GRID_SP_RATIOS, GRID_PI_RATIOS, GRID_DURATIONS))
    for sp_r, pi_r, dur in grid:
        sp  = market_price * sp_r
        pi  = max(1.0, market_price * pi_r)
        sim = _simulate_many(n_sim, market_price, sp, pi, dur, viewers)
        s   = _score(sim, function_type)

        if s > best_score:
            best_score = s
            best = {
                "product_id":            product_id,
                "function_type":         function_type,
                "rec_start_price_ratio": sp_r,
                "rec_interval_ratio":    pi_r,
                "rec_duration":          dur,
                "rec_start_price":       round(sp,  2),
                "rec_price_interval":    round(pi,  2),
                "price_p50":             round(sim["price_p50"],         2),
                "sell_through_rate":     round(sim["sell_through_rate"], 3),
                "avg_bids":              round(sim["avg_bids"],          1),
                "expected_score":        round(best_score,               2),
            }

    return best


def simulate_new_product(market_price: float, function_type: str = "GMV",
                         viewers: int = 80, n_sim: int = 20) -> dict:
    """Interactive single-product simulation: recommendation + distribution data."""
    best_score = -np.inf
    best       = None

    grid = list(itertools.product(GRID_INTERACTIVE_SP, GRID_INTERACTIVE_PI, GRID_INTERACTIVE_DUR))
    for sp_r, pi_r, dur in grid:
        sp  = market_price * sp_r
        pi  = max(1.0, market_price * pi_r)
        sim = _simulate_many(n_sim, market_price, sp, pi, dur, viewers)
        s   = _score(sim, function_type)

        if s > best_score:
            best_score = s
            best = {
                "product_id":            "PREVIEW",
                "function_type":         function_type,
                "rec_start_price_ratio": sp_r,
                "rec_interval_ratio":    pi_r,
                "rec_duration":          dur,
                "rec_start_price":       round(sp,  2),
                "rec_price_interval":    round(pi,  2),
                "price_p50":             round(sim["price_p50"],         2),
                "sell_through_rate":     round(sim["sell_through_rate"], 3),
                "avg_bids":              round(sim["avg_bids"],          1),
                "expected_score":        round(best_score,               2),
            }

    # Distribution curves for mini-chart (4 start-price scenarios)
    dist_labels = ["50%","60%","70%","80%","90%","100%","110%","120%","130%","140%"]
    dist_data   = {}
    bins         = np.linspace(0.5, 1.4, 11)
    for sp_r in [0.3, 0.5, 0.7, 0.9]:
        sp     = market_price * sp_r
        pi     = max(1.0, market_price * 0.02)
        prices = [_run_auction(market_price, sp, pi, 60, viewers)["final_price"]
                  for _ in range(40)]
        ratios = [p / market_price for p in prices]
        hist, _ = np.histogram(ratios, bins=bins)
        dist_data[f"SP={int(sp_r*100)}%"] = hist.tolist()

    best["dist_labels"] = dist_labels
    best["dist_data"]   = dist_data
    return best
