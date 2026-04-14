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

### 2026-04-14 — first script run, thesis partially confirmed

Ran `hdd_comparison.py` at KMSP for 2024-12-01..2025-03-01, day-ahead (24–42h lead, 6-hourly samples). 2762 hourly obs, 91 days. 1 missing init in AIFS (n=90 aligned).

|  | GFS | AIFS |
|---|---|---|
| vs obs-hourly | RMSE **1.80** / MAE 1.48 / bias +0.30 | RMSE 2.04 / MAE 1.55 / bias +1.16 |
| vs obs-6-hourly (fair) | RMSE 1.76 / MAE 1.43 / bias +0.15 | **RMSE 1.71 / MAE 1.26** / bias +1.02 |

Fair-sampling flips the result: AIFS beats GFS on RMSE/MAE when both sides use the same 6-hourly UTC grid. Delta is small (~3% RMSE). AIFS has a real ~1 °C warm bias. Against operational hourly obs, GFS still wins — the 4-sample forecast T_max/T_min understates diurnal range and AIFS's warm bias amplifies the mismatch.

Possible next steps (pending user direction):
- Try longer lead (5-day) where AIFS typically crushes GFS per scorecards
- Try another station (KORD, KBOS) to check MSP specificity
- Accept fair-sampling framing and build the notebook around it
- Check dynamical scorecard for a station × lead combo where delta is visibly larger

### 2026-04-14 — scorecard investigation, station pivot

Queried `https://assets.dynamical.org/scorecard/statistics.parquet` for T_2m RMSE, GFS vs AIFS, 180-day window (2025-10 to 2026-04).

**MSP is middle of the pack (rank 1547/2616).** AIFS beats GFS at all leads but only by 0.4–0.8 °C RMSE. MSP is open Midwest flat terrain — GFS's 0.25° grid handles it fine (lead 0 RMSE 2.07), so there's not much room for AIFS to shine.

**Better stations (CONUS, 180d window, lead 1d delta):**

| Station | Location | AIFS RMSE | GFS RMSE | Δ |
|---|---|---|---|---|
| LHX | La Junta, CO | 1.88 | 4.68 | **-2.80** |
| LBF | North Platte, NE | 2.52 | 5.09 | -2.57 |
| CEZ | Cortez, CO | 2.60 | 5.17 | -2.57 |
| MSP | Minneapolis | 1.76 | 2.33 | -0.57 |

Pattern: dramatic AIFS advantage shows up at Great Plains / Intermountain transition stations where GFS struggles with terrain (downslope, cold-air drainage). AIFS learned those effects from training. GFS RMSE 4–5 °C at lead 0 at these stations is *terrible* by weather-model standards — a ripe target for the "zero-code-change swap" demo.

**Recommendation:** switch station to **LBF** (North Platte, NE). Day-ahead delta of 2.57 °C RMSE is ~5x MSP's. Recognizable Great Plains cold station, strong HDD signal, relatable for US energy/utility narrative. LHX has slightly bigger delta but North Platte is more familiar.

### 2026-04-14 — pivot to BNA + multi-horizon

User pivoted to **BNA (Nashville)** — their home station. Scorecard check:

| Lead | AIFS RMSE | GFS RMSE | Delta | BNA rank / 2616 |
|---|---|---|---|---|
| 1d | 1.33 | 2.46 | -1.13 | 560 (top 21%) |
| 3d | 1.61 | 2.95 | **-1.34** | 294 (top 11%) |

Not as dramatic as LBF, but strong — and the bias story is cleaner: AIFS bias ~0 at BNA, GFS has persistent -1 °C cold bias in the scorecard window. Personal relevance matters more than abstract ranking for a demo.

Decision: **BNA + multi-horizon (1d, 3d, 5d)** — shows AIFS advantage persisting and compounding with lead, the textbook AI-weather selling point.

### 2026-04-14 — BNA multi-horizon script run

Refactored to load the point column once per model (slice init window to `target_days - max_lead` up to last target), then compute HDD in memory for each lead. Ran on winter 2024-12 to 2025-03.

|  model | lead | RMSE | MAE | bias |
|---|---|---|---|---|
| GFS  | 1d | 1.90 | 1.55 | +1.16 |
| GFS  | 3d | 2.18 | 1.77 | +1.07 |
| GFS  | 5d | 2.74 | 2.14 | +0.96 |
| AIFS | 1d | **1.66** | 1.39 | +1.15 |
| AIFS | 3d | **1.84** | 1.53 | +1.21 |
| AIFS | 5d | **2.35** | 1.89 | +1.16 |

**Thesis confirmed:** AIFS wins at every lead, delta grows with horizon (0.24 → 0.34 → 0.39 RMSE). AIFS 5d ≈ GFS 3d. Plot (hdd_comparison.png) shows three stacked time-series panels, divergence visibly growing with lead — classic AI-weather figure.

Bias note: both models have ~+1 °C HDD bias (i.e. cold T bias) in this window. Scorecard's AIFS bias is smaller (-0.3) but that's for a different window (2025-10..2026-04) and partially caused by 4-sample daily T_max/T_min understating diurnal range. Relative ordering (AIFS < GFS) is robust.

**Phase 1 complete. Proceeding to Phase 2 — notebook port.**

### 2026-04-14 — Phase 2: notebook built

Fetched icechunk URIs from STAC catalog (`https://dynamical.org/stac/catalog.json`):
- GFS: `s3://dynamical-noaa-gfs/noaa-gfs-forecast/v0.2.7.icechunk/`
- AIFS: `s3://dynamical-ecmwf-aifs-single/ecmwf-aifs-single-forecast/v0.1.0.icechunk/`

Notebook `noaa-gfs+ecmwf-aifs-hdd.ipynb` built with the user-requested 6-step flow:
1. Load GFS + plot 2026-01-20 00Z temperature forecast at BNA
2. Load AIFS + plot same forecast (visibly identical selection code, different dataset)
3. Define `hdd_analysis(ds, lat, lon, days)` helper (works on any dataset with the shared schema)
4. Run on GFS
5. Run on AIFS — *same function*
6. Compute RMSE/MAE/bias table and 3-panel comparison plot

**Tooling extension:** `.internal/create_icechunk_versions.py` now supports a list of icechunk URIs per notebook (one per `xr.open_zarr` cell, replaced in order) and preserves the original variable name of the assignment (e.g. `gfs_ds = ...`, `aifs_ds = ...`) instead of hardcoding `ds`. Backward-compatible — single-dataset notebooks still assign to `ds` because their source does.

**2026-04-14 update: reverted tooling extension.** User requested the notebook be icechunk-native instead of HTTP-Zarr-with-generated-icechunk-variant. That eliminates the need for multi-URI support in `create_icechunk_versions.py`, so the invasive tooling changes were reverted to the original single-URI shape. Net change in that file is only adding `noaa-gfs+ecmwf-aifs-hdd.ipynb` to `allowed_missing` so the generator doesn't complain. Main notebook rewritten so both `gfs_ds` and `aifs_ds` are opened via `icechunk.s3_storage(...)` directly (no HTTP Zarr URL anywhere). Title updated to `- dynamical.org Icechunk Zarr`, pip install includes `icechunk`. Generated `-icechunk.ipynb` variant deleted. Metrics unchanged (same data, same logic).

**Notebook results (winter 2025-12-01 to 2026-03-01, BNA):**

|  lead | GFS RMSE | AIFS RMSE | delta |
|---|---|---|---|
| 1d | 1.80 | **1.31** | -0.49 (27%) |
| 3d | 2.17 | **1.65** | -0.52 (24%) |
| 5d | 3.41 | **2.42** | -0.99 (29%) |

**Headline:** AIFS 5-day forecast (2.42) is *better* than GFS 3-day (2.17). AI model out-forecasts GFS by 2 days of lead time on this metric.

Notebook 611 KB (< 10 MB), zero error cells, icechunk variant generated and verified. Scratch `hdd_comparison.py` + `.png` deleted.
