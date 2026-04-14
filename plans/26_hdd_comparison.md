# GFS vs AIFS — Heating Degree Days comparison

PR [#26](https://github.com/dynamical-org/notebooks/pull/26) · closes issue [#15](https://github.com/dynamical-org/notebooks/issues/15)

## Context

Issue #15 started as a request from @rsignell for a forecast-comparison notebook (HRRR vs GFS winds at his house on Buzzards Bay). In the recap with @aldenks, the framing crystallized around **Heating Degree Days (HDD)** as a concrete downstream metric:

> Compute HDD error (RMSE or MAE) on GFS, run the same calculation on AIFS, show AIFS is lower at a real station where the delta is visible. The whole point is that it's a deterministic transform — no training, no model, just a function. Same pipeline, swap the forecast input, better result. The "show" is the zero-code-change hot-swap.

**Approach:** write a Python script first to iterate on correctness, then port to a Jupyter notebook following existing repo conventions.

**Decisions:**
- **Station:** `KMSP` Minneapolis-St. Paul — maximum HDD signal, best chance GFS vs AIFS delta exceeds noise.
- **Horizon:** day-ahead (24–48h) only for the first pass. Extend later if the code stays clean.
- **Window:** 2024-12-01 to 2025-03-01 (AIFS starts 2024-04; need a cold winter).

## Data sources

| Source | URL | Key fields |
|---|---|---|
| GFS forecast | `https://data.dynamical.org/noaa/gfs/forecast/latest.zarr` | `temperature_2m`, dims `(init_time, lead_time, latitude, longitude)`, 6-hourly inits, hourly-then-3-hourly lead, from 2021-05 |
| AIFS single forecast | `https://data.dynamical.org/ecmwf/aifs-single/forecast/latest.zarr` | `temperature_2m`, dims `(init_time, lead_time, latitude, longitude)`, 6-hourly inits, 6-hourly lead, from 2024-04 |
| ASOS observations | `https://data.source.coop/dynamical/asos-parquet/year={YYYY}/data.parquet` | `station`, `valid`, `tmpc`, `latitude`, `longitude` — hourly, global, ICAO-keyed |

Both zarr datasets share dimension and variable names — selection code is literally identical, only the URL changes. That's the point.

## Phase 1 — Python script

- [ ] Add `duckdb` to `pyproject.toml`
- [ ] Write `hdd_comparison.py` at repo root (scratch; deleted in Phase 2)
- [ ] Run and verify:
  - [ ] Observed HDD non-zero across winter range (sanity)
  - [ ] Forecast HDD has no NaN gaps
  - [ ] `RMSE_AIFS < RMSE_GFS` — if not, investigate before moving on
  - [ ] `hdd_comparison.png` visually shows three curves, AIFS closer to obs

**Script shape:**

```python
STATION_ICAO = "KMSP"
START = "2024-12-01"
END   = "2025-03-01"
HDD_BASE_C = 18.333  # 65°F

# 1. Station metadata + hourly obs via duckdb against asos-parquet
# 2. Observed daily HDD: hourly -> daily T_max/T_min -> T_avg -> HDD
# 3. forecast_hdd(zarr_url, days) — one function, two calls
#    For each day D: init_time = D-1 at 00Z, lead 24h..42h at 6h step
# 4. RMSE + MAE for each model
# 5. matplotlib three-series plot -> hdd_comparison.png
```

**Fair-comparison detail:** GFS has hourly lead times for 0–120h; AIFS only 6-hourly. To isolate model quality from sampling frequency, forecast T_max/T_min for both use the same 6-hourly sample set (00, 06, 12, 18Z). Observations keep their full hourly resolution — that's ground truth, not something to handicap.

## Phase 2 — Notebook adaptation

Only after Phase 1 numbers look right.

**Name:** `noaa-gfs+ecmwf-aifs-hdd.ipynb` (follows the `+` composition convention from `noaa-stations+gefs.ipynb`).

- [ ] Create notebook mirroring `noaa-stations+gefs.ipynb` structure
- [ ] Markdown intro: what HDD is, why it matters, zero-code-change swap framing
- [ ] `%pip install` cell with `duckdb`
- [ ] **One** `forecast_hdd(zarr_url, ...)` helper, called twice — visibly lean into "same function, different URL"
- [ ] Metrics printout + matplotlib plot
- [ ] Register in `.internal/create_icechunk_versions.py` with icechunk S3 URI (user provides)
- [ ] `uv run .internal/run_notebooks.py noaa-gfs+ecmwf-aifs-hdd.ipynb`
- [ ] Notebook < 10MB
- [ ] Delete `hdd_comparison.py`
- [ ] Mark PR ready for review

## Critical files

- `noaa-stations+gefs.ipynb` — pattern to mirror
- `noaa-gfs-forecast.ipynb`, `ecmwf-aifs-single-forecast.ipynb` — dataset references
- `pyproject.toml` — add `duckdb`
- `.internal/create_icechunk_versions.py` — register new notebook
- `~/workspace/asos-parquet/README.md` — DuckDB query patterns

## Log
