"""HDD comparison: GFS vs AIFS day-ahead forecasts at a single ASOS station.

Computes heating-degree-days (HDD) error for each model against hourly ASOS
observations. Same pipeline for both — only the zarr URL changes.

Ground truth: hourly asos-parquet obs -> daily T_max/T_min -> T_avg -> HDD
Forecast:     6-hourly samples from init (D-1) 00Z, leads 24..42h -> same math
"""

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

STATION = "BNA"
START = "2024-12-01"
END = "2025-03-01"
HDD_BASE_C = (65 - 32) * 5 / 9  # 18.333 °C
LEADS_DAYS = [1, 3, 5]

ASOS_BASE = "https://data.source.coop/dynamical/asos-parquet"
GFS_URL = "https://data.dynamical.org/noaa/gfs/forecast/latest.zarr"
AIFS_URL = "https://data.dynamical.org/ecmwf/aifs-single/forecast/latest.zarr"


def load_station(station: str, start: str, end: str) -> tuple[float, float, pd.Series]:
    years = sorted({int(start[:4]), int(end[:4])})
    urls = [f"{ASOS_BASE}/year={y}/data.parquet" for y in years]
    df = duckdb.execute(
        """
        SELECT valid, tmpc, latitude, longitude
        FROM read_parquet(?, hive_partitioning=true)
        WHERE station = ?
          AND valid BETWEEN ? AND ?
          AND tmpc IS NOT NULL
        ORDER BY valid
        """,
        [urls, station, start, end],
    ).fetchdf()
    if df.empty:
        raise RuntimeError(f"No observations for {station} in {start}..{end}")
    lat = float(df["latitude"].iloc[0])
    lon = float(df["longitude"].iloc[0])
    obs = pd.Series(
        df["tmpc"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(pd.to_datetime(df["valid"], utc=True)).tz_convert("UTC").tz_localize(None),
        name="tmpc",
    )
    return lat, lon, obs


def daily_hdd(t_subdaily: pd.Series) -> pd.Series:
    """Daily HDD from sub-daily temperatures. T_avg = (T_max + T_min) / 2."""
    daily = t_subdaily.resample("1D").agg(["max", "min"]).dropna()
    t_avg = (daily["max"] + daily["min"]) / 2
    return (HDD_BASE_C - t_avg).clip(lower=0)


def load_forecast_point(
    zarr_url: str,
    station_lat: float,
    station_lon: float,
    target_days: pd.DatetimeIndex,
    max_lead_days: int,
) -> xr.DataArray:
    """Load temperature_2m at the station point for an init window that covers
    the longest lead we need. Point-column is materialized once per model."""
    init_min = (target_days - pd.Timedelta(days=max_lead_days))[0]
    init_max = target_days[-1]
    ds = xr.open_zarr(zarr_url, chunks=None)
    return (
        ds["temperature_2m"]
        .sel(init_time=slice(init_min, init_max))
        .sel(latitude=station_lat, longitude=station_lon, method="nearest")
        .load()
    )


def forecast_hdd(
    t2m_point: xr.DataArray,
    target_days: pd.DatetimeIndex,
    lead_days: int,
) -> pd.Series:
    """Forecast HDD at a single lead. For each target day D, the forecast uses
    init (D - lead_days) at 00Z and lead_times [24L, 24L+6, 24L+12, 24L+18]
    (four 6-hourly samples spanning day D)."""
    init_times = target_days - pd.Timedelta(days=lead_days)
    base_hours = 24 * lead_days
    leads = pd.to_timedelta([base_hours + h for h in (0, 6, 12, 18)], unit="h")

    sub = t2m_point.sel(lead_time=leads).reindex(init_time=init_times)
    arr = np.asarray(sub.values, dtype=float)  # (len(target_days), 4)

    if np.nanmean(arr) > 100:  # Kelvin fallback
        arr = arr - 273.15

    with np.errstate(all="ignore"):
        t_max = np.nanmax(arr, axis=1)
        t_min = np.nanmin(arr, axis=1)
    t_avg = (t_max + t_min) / 2
    hdd_values = np.clip(HDD_BASE_C - t_avg, 0, None)
    return pd.Series(hdd_values, index=target_days, name="hdd")


def main() -> None:
    lat, lon, obs = load_station(STATION, START, END)
    print(f"Station {STATION}: ({lat:.3f}, {lon:.3f}), {len(obs)} hourly obs")

    obs_hdd = daily_hdd(obs)
    print(f"Observed HDD: n={len(obs_hdd)} sum={obs_hdd.sum():.0f} max={obs_hdd.max():.1f}")

    target_days = obs_hdd.index
    max_lead = max(LEADS_DAYS)

    results: dict[tuple[str, int], pd.Series] = {}
    metrics: list[dict] = []
    for name, url in [("GFS", GFS_URL), ("AIFS", AIFS_URL)]:
        print(f"Loading {name}...")
        t2m_point = load_forecast_point(url, lat, lon, target_days, max_lead)
        for lead_days in LEADS_DAYS:
            fc = forecast_hdd(t2m_point, target_days, lead_days)
            aligned = pd.concat({"obs": obs_hdd, "fc": fc}, axis=1).dropna()
            err = aligned["fc"] - aligned["obs"]
            rmse = float(np.sqrt((err**2).mean()))
            mae = float(err.abs().mean())
            bias = float(err.mean())
            metrics.append(
                dict(model=name, lead=lead_days, n=len(aligned), rmse=rmse, mae=mae, bias=bias)
            )
            results[(name, lead_days)] = fc

    print()
    print(f"{'model':<6}{'lead':>6}{'n':>6}{'RMSE':>8}{'MAE':>8}{'bias':>8}")
    for m in metrics:
        print(
            f"{m['model']:<6}{m['lead']:>5}d{m['n']:>6}"
            f"{m['rmse']:>8.2f}{m['mae']:>8.2f}{m['bias']:>+8.2f}"
        )

    fig, axes = plt.subplots(len(LEADS_DAYS), 1, figsize=(12, 3 * len(LEADS_DAYS)), sharex=True)
    for ax, lead_days in zip(axes, LEADS_DAYS):
        ax.plot(obs_hdd.index, obs_hdd.values, label="Observed", color="black", lw=2)
        for name, color in [("GFS", "tab:orange"), ("AIFS", "tab:blue")]:
            fc = results[(name, lead_days)]
            row = next(m for m in metrics if m["model"] == name and m["lead"] == lead_days)
            ax.plot(
                fc.index, fc.values,
                label=f"{name}  RMSE={row['rmse']:.2f}",
                color=color, alpha=0.85,
            )
        ax.set_ylabel("HDD (°C base 18.3)")
        ax.set_title(f"{lead_days}-day lead forecast")
        ax.legend(loc="upper right")
        ax.grid(alpha=0.3)
    axes[0].text(
        0.01, 0.95,
        f"{STATION}  |  {START}..{END}",
        transform=axes[0].transAxes, fontsize=11, fontweight="bold", va="top",
    )
    fig.tight_layout()
    fig.savefig("hdd_comparison.png", dpi=120)
    print("Saved hdd_comparison.png")


if __name__ == "__main__":
    main()
