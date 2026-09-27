"""Data analysis that actually runs on this machine.

Backed by numpy/pandas/scipy/scikit-learn/matplotlib/openpyxl, so the Data
Science group is executable rather than aspirational. Every function returns
real computed output, and says so when it cannot.

Supported inputs: .csv, .xlsx/.xls, .json, .tsv, and .parquet if pyarrow is
present. Anything else is reported, not guessed at.
"""

from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    HAVE_PANDAS = True
except Exception:
    HAVE_PANDAS = False

try:
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import r2_score, accuracy_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    HAVE_SK = True
except Exception:
    HAVE_SK = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:
    HAVE_MPL = False

CHART_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "jenny" / "charts"
MAX_BYTES = 200 * 1024 * 1024


def available() -> dict:
    return {"pandas": HAVE_PANDAS, "sklearn": HAVE_SK, "matplotlib": HAVE_MPL,
            "detail": "Data analysis ready." if HAVE_PANDAS else
                      "pandas is not installed, so data analysis is unavailable."}


def _err(msg, **extra):
    return {"ok": False, "error": msg, **extra}


def load(path, sheet=None):
    """Load a tabular file into a DataFrame."""
    if not HAVE_PANDAS:
        return _err("pandas is not installed.")
    p = Path(str(path)).expanduser()
    if not p.exists():
        return _err(f"No such file: {p}")
    try:
        if p.stat().st_size > MAX_BYTES:
            return _err(f"{p.name} is {p.stat().st_size / 1048576:.0f} MB, above the {MAX_BYTES // 1048576} MB limit.")
    except Exception:
        pass
    ext = p.suffix.lower()
    try:
        if ext in (".csv", ".txt", ".tsv"):
            sep = "\t" if ext == ".tsv" else None
            return pd.read_csv(p, sep=sep, engine="python" if sep is None else "c",
                               encoding_errors="replace")
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(p, sheet_name=sheet or 0, engine="openpyxl")
        if ext == ".json":
            return pd.read_json(p)
        if ext == ".jsonl":
            return pd.read_json(p, lines=True)
        if ext == ".parquet":
            return pd.read_parquet(p)
    except Exception as e:
        return _err(f"Couldn't read {p.name}: {type(e).__name__}: {e}")
    return _err(f"I can't read '{ext or 'that'}' files. CSV, Excel, JSON, JSONL and Parquet work.")


def _frame(source):
    if isinstance(source, pd.DataFrame):
        return source, None
    df = load(source)
    if isinstance(df, dict) and df.get("ok") is False:
        return None, df
    return df, None


def describe(source):
    df, bad = _frame(source)
    if bad:
        return bad
    numeric = df.select_dtypes(include="number")
    out = {
        "ok": True, "rows": int(df.shape[0]), "columns": int(df.shape[1]),
        "column_names": [str(c) for c in df.columns[:60]],
        "dtypes": {str(k): str(v) for k, v in list(df.dtypes.items())[:40]},
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1048576, 2),
        "missing_total": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_summary": {},
    }
    if not numeric.empty:
        desc = numeric.describe().round(4)
        out["numeric_summary"] = {
            str(c): {k: (None if pd.isna(v) else float(v))
                     for k, v in desc[c].items()} for c in desc.columns[:25]
        }
        out["numeric_columns"] = [str(c) for c in numeric.columns[:40]]
    cat = df.select_dtypes(include=["object", "category"])
    if not cat.empty:
        out["categorical_columns"] = [str(c) for c in cat.columns[:25]]
        out["top_values"] = {
            str(c): {str(k): int(v) for k, v in df[c].value_counts().head(5).items()}
            for c in cat.columns[:8]
        }
    return out


def clean(source, drop_duplicates=True, fill_strategy="median", drop_empty_cols=True):
    df, bad = _frame(source)
    if bad:
        return bad
    before = df.shape
    report = {"rows_before": int(before[0]), "cols_before": int(before[1]), "actions": []}
    if drop_empty_cols:
        empty = [c for c in df.columns if df[c].isna().all()]
        if empty:
            df = df.drop(columns=empty)
            report["actions"].append(f"dropped {len(empty)} all-empty column(s)")
    if drop_duplicates:
        dups = int(df.duplicated().sum())
        if dups:
            df = df.drop_duplicates()
            report["actions"].append(f"removed {dups} duplicate row(s)")
    numeric = df.select_dtypes(include="number").columns
    if len(numeric):
        if fill_strategy == "mean":
            df[numeric] = df[numeric].fillna(df[numeric].mean())
        elif fill_strategy == "zero":
            df[numeric] = df[numeric].fillna(0)
        else:
            df[numeric] = df[numeric].fillna(df[numeric].median())
        report["actions"].append(f"filled numeric NaNs with {fill_strategy}")
    for col in df.select_dtypes(include=["object", "category"]).columns:
        mode = df[col].mode()
        if not mode.empty:
            df[col] = df[col].fillna(mode.iloc[0])
    report["actions"].append("filled text NaNs with the most common value")
    report["rows_after"] = int(df.shape[0])
    report["cols_after"] = int(df.shape[1])
    report["remaining_missing"] = int(df.isna().sum().sum())
    return {"ok": True, "report": report, "dataframe": df}


def missing_values(source):
    df, bad = _frame(source)
    if bad:
        return bad
    counts = df.isna().sum()
    total = int(df.shape[0]) or 1
    rows = []
    for col, n in counts.items():
        if n:
            rows.append({"column": str(col), "missing": int(n),
                         "percent": round(100.0 * int(n) / total, 2)})
    rows.sort(key=lambda r: -r["missing"])
    return {"ok": True, "total_cells": int(df.size), "missing_cells": int(counts.sum()),
            "columns_with_missing": len(rows), "detail": rows[:40]}


def outliers(source, column=None, method="iqr"):
    df, bad = _frame(source)
    if bad:
        return bad
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return _err("There are no numeric columns to find outliers in.")
    if column and column not in df.columns:
        return _err(f"No column named '{column}'. Numeric columns: {[str(c) for c in numeric.columns][:20]}")
    cols = [column] if column else list(numeric.columns[:15])
    found = {}
    total = 0
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        if method == "zscore":
            mu, sd = s.mean(), s.std()
            if not sd:
                continue
            mask = (s - mu).abs() > 3 * sd
        else:
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            if not iqr:
                continue
            mask = (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)
        n = int(mask.sum())
        if n:
            found[str(col)] = {"count": n, "percent": round(100.0 * n / len(s), 2),
                               "min": float(s.min()), "max": float(s.max())}
            total += n
    return {"ok": True, "method": method, "total_outliers": total,
            "columns": found,
            "text": f"Found {total} outlier value(s) across {len(found)} column(s) using {method}."}


def correlations(source, method="pearson", threshold=0.0):
    df, bad = _frame(source)
    if bad:
        return bad
    numeric = df.select_dtypes(include="number")
    if numeric.shape[1] < 2:
        return _err("Correlation needs at least two numeric columns.")
    corr = numeric.corr(method=method).round(4)
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.isna(v):
                continue
            if abs(float(v)) >= threshold:
                pairs.append({"a": str(cols[i]), "b": str(cols[j]), "r": float(v)})
    pairs.sort(key=lambda p: -abs(p["r"]))
    return {"ok": True, "method": method, "pair_count": len(pairs),
            "strongest": pairs[:25],
            "text": f"{len(pairs)} correlated pair(s); strongest is "
                    f"{pairs[0]['a']} vs {pairs[0]['b']} at r={pairs[0]['r']}" if pairs else "No pairs."}


def statistical_summary(source):
    df, bad = _frame(source)
    if bad:
        return bad
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return _err("No numeric columns to summarise.")
    rows = []
    for col in numeric.columns[:25]:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append({
            "column": str(col), "count": int(s.count()), "mean": float(s.mean()),
            "std": float(s.std()) if len(s) > 1 else 0.0,
            "min": float(s.min()), "q1": float(s.quantile(0.25)),
            "median": float(s.median()), "q3": float(s.quantile(0.75)),
            "max": float(s.max()),
            "skew": float(s.skew()) if len(s) > 2 else 0.0,
            "zeros": int((s == 0).sum()),
        })
    return {"ok": True, "columns": rows, "text": f"Statistical summary for {len(rows)} numeric column(s)."}


def regression(source, target, features=None, test_size=0.2):
    df, bad = _frame(source)
    if bad:
        return bad
    if not HAVE_SK:
        return _err("scikit-learn is not installed, so regression is unavailable.")
    if target not in df.columns:
        return _err(f"No column named '{target}'. Columns: {[str(c) for c in df.columns][:25]}")
    feats = features or [str(c) for c in df.select_dtypes(include="number").columns if c != target]
    feats = [f for f in feats if f in df.columns and f != target]
    if not feats:
        return _err("No numeric feature columns available to fit against the target.")
    work = df[[target] + feats].apply(pd.to_numeric, errors="coerce").dropna()
    if len(work) < 10:
        return _err(f"Only {len(work)} complete row(s) after dropping missing values; need at least 10.")
    X, y = work[feats].values, work[target].values
    if len(set(y.tolist())) < 3:
        return _err("The target column has too few distinct values to fit a regression.")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size, random_state=42)
    model = LinearRegression().fit(Xtr, ytr)
    pred = model.predict(Xte)
    r2 = float(r2_score(yte, pred))
    coefs = sorted(
        ({"feature": f, "coefficient": float(c)} for f, c in zip(feats, model.coef_)),
        key=lambda d: -abs(d["coefficient"]),
    )
    warnings = []
    if r2 < 0:
        warnings.append(
            f"R2 is negative ({r2:.2f}), meaning the model predicts worse than just "
            f"averaging the target. Usually caused by outliers or a non-linear relationship; "
            f"clean the data or use a different model before trusting these coefficients.")
    return {"ok": True, "target": str(target), "features": feats, "r2": round(r2, 4),
            "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
            "coefficients": coefs, "intercept": float(model.intercept_),
            "warnings": warnings,
            "text": f"Linear regression of {target}: R2={r2:.3f}. "
                    + (warnings[0] if warnings else
                       f"Strongest factor is {coefs[0]['feature']} ({coefs[0]['coefficient']:+.3f}).")}


def classification(source, target, features=None, test_size=0.2):
    df, bad = _frame(source)
    if bad:
        return bad
    if not HAVE_SK:
        return _err("scikit-learn is not installed, so classification is unavailable.")
    if target not in df.columns:
        return _err(f"No column named '{target}'. Columns: {[str(c) for c in df.columns][:25]}")
    y = df[target]
    if y.nunique(dropna=True) < 2:
        return _err(f"'{target}' has fewer than 2 distinct classes, so it cannot be a classifier target.")
    if y.nunique() > 50:
        return _err(f"'{target}' has {y.nunique()} distinct values, which is regression territory, not classification.")
    feats = features or [str(c) for c in df.select_dtypes(include="number").columns if c != target]
    feats = [f for f in feats if f in df.columns and f != target]
    if not feats:
        return _err("No numeric feature columns available to train on.")
    work = df[[target] + feats].copy()
    work[feats] = work[feats].apply(pd.to_numeric, errors="coerce")
    work = work.dropna()
    if len(work) < 20:
        return _err(f"Only {len(work)} complete row(s); need at least 20 to train.")
    counts = work[target].value_counts()
    if counts.min() < 2:
        rare = [str(k) for k, v in counts.items() if v < 2][:5]
        return _err(f"Rare classes {rare} have fewer than 2 rows, so a split would be meaningless.")
    Xtr, Xte, ytr, yte = train_test_split(
        work[feats].values, work[target].values, test_size=test_size,
        random_state=42, stratify=work[target].values)
    model = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    acc = float(accuracy_score(yte, model.predict(Xte)))
    return {"ok": True, "target": str(target), "classes": [str(c) for c in counts.index[:20]],
            "accuracy": round(acc, 4), "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
            "text": f"Classifier for {target}: {acc:.1%} accuracy across {len(counts)} class(es) on held-out data."}


def clustering(source, k=3, features=None):
    df, bad = _frame(source)
    if bad:
        return bad
    if not HAVE_SK:
        return _err("scikit-learn is not installed, so clustering is unavailable.")
    numeric = df.select_dtypes(include="number")
    cols = features or [str(c) for c in numeric.columns[:10]]
    cols = [c for c in cols if c in numeric.columns]
    if not cols:
        return _err("No numeric columns available to cluster on.")
    X = numeric[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < k * 3:
        return _err(f"Only {len(X)} complete row(s); need at least {k * 3} for k={k}.")
    k = max(2, min(int(k), len(X) - 1))
    scaled = StandardScaler().fit_transform(X.values)
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(scaled)
    out = X.copy()
    out["cluster"] = labels
    sizes = pd.Series(labels).value_counts().sort_index()
    profiles = {}
    for ci in range(k):
        sub = X[labels == ci]
        if sub.empty:
            continue
        profiles[str(ci)] = {c: round(float(sub[c].mean()), 4) for c in cols[:8]}
    return {"ok": True, "k": int(k), "features": cols, "cluster_sizes": {str(i): int(v) for i, v in sizes.items()},
            "profiles": profiles, "dataframe": out,
            "text": f"Found {k} clusters; sizes " +
                    ", ".join(f"{i}:{v}" for i, v in sizes.items()) + "."}


def forecast(source, column, periods=7, method="linear"):
    df, bad = _frame(source)
    if bad:
        return bad
    if column not in df.columns:
        return _err(f"No column named '{column}'. Columns: {[str(c) for c in df.columns][:25]}")
    s = pd.to_numeric(df[column], errors="coerce").dropna()
    if len(s) < 5:
        return _err(f"'{column}' has only {len(s)} numeric value(s); need at least 5 to forecast.")
    n = len(s)
    x = np.arange(n)
    if method == "mean":
        pred = [float(s.mean())] * int(periods)
    else:
        slope, intercept = np.polyfit(x, s.values, 1)
        pred = [float(slope * (n + i) + intercept) for i in range(int(periods))]
    return {"ok": True, "column": str(column), "method": method, "history_points": int(n),
            "forecast": [round(v, 4) for v in pred],
            "last_actual": float(s.iloc[-1]),
            "text": f"Forecast for {column} over {periods} step(s): " +
                    ", ".join(f"{v:.2f}" for v in pred[:5])}


def pivot(source, index=None, columns=None, values=None, aggfunc="sum"):
    df, bad = _frame(source)
    if bad:
        return bad
    try:
        out = df.pivot_table(index=index, columns=columns, values=values, aggfunc=aggfunc)
    except Exception as e:
        return _err(f"Pivot failed: {e}")
    return {"ok": True, "shape": list(out.shape), "data": out.reset_index().to_dict("records")[:200],
            "text": f"Pivot table: {out.shape[0]} rows x {out.shape[1]} columns using {aggfunc}."}


def kpis(source, specs):
    df, bad = _frame(source)
    if bad:
        return bad
    if isinstance(specs, str):
        specs = [s.strip() for s in specs.split(",") if s.strip()]
    results = {}
    for spec in specs or []:
        try:
            if ":" in spec:
                col, fn = spec.split(":", 1)
                col, fn = col.strip(), fn.strip()
            else:
                col, fn = spec.strip(), "sum"
            if col not in df.columns:
                results[spec] = {"ok": False, "error": f"No column '{col}'"}
                continue
            if fn in ("sum", "mean", "median", "min", "max", "count", "std"):
                val = getattr(pd.to_numeric(df[col], errors="coerce"), fn)()
                results[spec] = {"ok": True, "value": None if pd.isna(val) else float(val)}
            elif fn == "nunique":
                results[spec] = {"ok": True, "value": int(df[col].nunique())}
            else:
                results[spec] = {"ok": False, "error": f"Unsupported aggregate '{fn}'"}
        except Exception as e:
            results[spec] = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "kpis": results, "text": f"Computed {len(results)} KPI(s)."}


def trends(source, date_column, value_column=None, freq="D"):
    df, bad = _frame(source)
    if bad:
        return bad
    if date_column not in df.columns:
        return _err(f"No date column named '{date_column}'. Columns: {[str(c) for c in df.columns][:25]}")
    work = df[[date_column] + ([value_column] if value_column in df.columns else [])].copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce", format="mixed")
    work = work.dropna(subset=[date_column])
    if work.empty:
        return _err(f"Could not parse any dates in '{date_column}'.")
    if value_column and value_column in work.columns:
        work[value_column] = pd.to_numeric(work[value_column], errors="coerce")
        grouped = work.groupby(pd.Grouper(key=date_column, freq=freq))[value_column].mean().dropna()
    else:
        grouped = work.groupby(pd.Grouper(key=date_column, freq=freq)).size()
    if len(grouped) < 3:
        return _err("Not enough distinct time periods to detect a trend.")
    first, last = float(grouped.iloc[0]), float(grouped.iloc[-1])
    change = ((last - first) / abs(first) * 100.0) if first else float("inf")
    return {"ok": True, "freq": freq, "points": int(len(grouped)),
            "series": {str(k.date()): round(float(v), 4) for k, v in grouped.head(60).items()},
            "change_percent": round(change, 2) if math.isfinite(change) else None,
            "direction": "up" if last > first else ("down" if last < first else "flat"),
            "text": f"{value_column or 'count'} over {freq}: {grouped.index[0].date()} to "
                    f"{grouped.index[-1].date()}, {grouped.index[0].date()} value {first:.2f} -> {last:.2f} "
                    f"({'up' if last > first else 'down' if last < first else 'flat'})."}


def anomaly_detection(source, columns=None, contamination=0.05):
    df, bad = _frame(source)
    if bad:
        return bad
    if not HAVE_SK:
        return _err("scikit-learn is not installed, so anomaly detection is unavailable.")
    numeric = df.select_dtypes(include="number")
    cols = [c for c in (columns or list(numeric.columns[:12])) if c in numeric.columns]
    if not cols:
        return _err("No numeric columns available for anomaly detection.")
    X = numeric[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if len(X) < 20:
        return _err(f"Only {len(X)} rows; need at least 20 for anomaly detection.")
    model = IsolationForest(contamination=contamination, random_state=42).fit(X.values)
    flags = model.predict(X.values)
    idx = [int(i) for i, f in enumerate(flags) if f == -1]
    anomalies = df.iloc[idx][cols].head(25).to_dict("records")
    return {"ok": True, "columns": cols, "anomaly_count": len(idx),
            "anomaly_percent": round(100.0 * len(idx) / len(X), 2),
            "examples": [{"row": int(df.index[i]) if i < len(df.index) else i, **anomalies[j]}
                         for j, i in enumerate(idx[:10])],
            "text": f"Flagged {len(idx)} anomalous row(s) ({100.0 * len(idx) / len(X):.1f}%)."}


def data_quality(source):
    df, bad = _frame(source)
    if bad:
        return bad
    rows, cols = df.shape
    completeness = 100.0 * (1 - df.isna().sum().sum() / max(1, df.size))
    uniqueness = 100.0 * (1 - df.duplicated().sum() / max(1, rows))
    numeric = df.select_dtypes(include="number")
    const = sum(1 for c in numeric.columns if numeric[c].nunique(dropna=True) <= 1)
    const_pen = 100.0 * const / max(1, numeric.shape[1])
    score = max(0.0, 0.5 * completeness + 0.3 * uniqueness + 0.2 * (100 - const_pen))
    return {"ok": True, "score": round(score, 2),
            "components": {"completeness": round(completeness, 2),
                           "uniqueness": round(uniqueness, 2),
                           "constant_columns": int(const)},
            "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D",
            "text": f"Data quality {score:.1f}/100 (grade {('A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D')}). "
                    f"{completeness:.1f}% complete, {uniqueness:.1f}% unique."}


def compare(source_a, source_b):
    a, bad = _frame(source_a)
    if bad:
        return bad
    b, bad = _frame(source_b)
    if bad:
        return bad
    only_a = sorted(set(map(str, a.columns)) - set(map(str, b.columns)))
    only_b = sorted(set(map(str, b.columns)) - set(map(str, a.columns)))
    shared = [c for c in a.columns if c in b.columns]
    numeric = [c for c in shared if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c])]
    deltas = {}
    for col in numeric[:15]:
        ma, mb = a[col].mean(), b[col].mean()
        if pd.notna(ma) and pd.notna(mb):
            deltas[str(col)] = {"a": round(float(ma), 4), "b": round(float(mb), 4),
                                "delta": round(float(mb - ma), 4)}
    return {"ok": True, "rows_a": int(a.shape[0]), "rows_b": int(b.shape[0]),
            "only_in_a": only_a[:20], "only_in_b": only_b[:20],
            "shared_columns": len(shared), "numeric_deltas": deltas,
            "text": f"{a.shape[0]} vs {b.shape[0]} rows; {len(shared)} shared column(s), "
                    f"{len(only_a)} unique to A, {len(only_b)} unique to B."}


def chart(source, kind="hist", column=None, group=None, title=None):
    """Render a chart to PNG and return its path."""
    df, bad = _frame(source)
    if bad:
        return bad
    if not HAVE_MPL:
        return _err("matplotlib is not installed, so charts are unavailable.")
    numeric = df.select_dtypes(include="number")
    if kind in ("hist", "histogram", "bar", "box", "scatter", "line", "pie", "corr"):
        if kind != "corr" and (not column or column not in df.columns):
            return _err(f"'{kind}' needs a column. Available: {[str(c) for c in df.columns][:25]}")
    else:
        return _err(f"Unknown chart kind '{kind}'. Use hist, bar, box, scatter, line, pie or corr.")
    try:
        CHART_DIR.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(9, 5))
        if kind in ("hist", "histogram"):
            if column not in numeric.columns:
                return _err(f"'{column}' is not numeric, so a histogram does not apply.")
            ax.hist(numeric[column].dropna(), bins=30, color="#4c8dff", edgecolor="white")
            ax.set_xlabel(str(column))
        elif kind == "bar":
            counts = df[column].value_counts().head(20)
            ax.bar(range(len(counts)), counts.values, color="#4c8dff")
            ax.set_xticks(range(len(counts)))
            ax.set_xticklabels([str(i)[:18] for i in counts.index], rotation=40, ha="right")
            ax.set_ylabel("count")
        elif kind == "box":
            cols = [column] if column in numeric.columns else list(numeric.columns[:6])
            data = [numeric[c].dropna().values for c in cols]
            data = [d for d in data if len(d)]
            if not data:
                return _err("No numeric values to plot a box for.")
            keep = [c for c, d in zip(cols, [numeric[c].dropna().values for c in cols]) if len(d)]
            # matplotlib renamed `labels` to `tick_labels` in 3.9
            try:
                ax.boxplot(data, tick_labels=[str(c)[:14] for c in keep])
            except TypeError:
                ax.boxplot(data, labels=[str(c)[:14] for c in keep])
        elif kind == "scatter":
            if group and group in df.columns and column in numeric.columns:
                for key, sub in df.groupby(group):
                    ax.scatter(sub[column], range(len(sub)), label=str(key)[:14], s=18, alpha=0.7)
                ax.legend(fontsize=7)
            else:
                others = [c for c in numeric.columns if c != column]
                if not others:
                    return _err("Scatter needs a second numeric column.")
                ax.scatter(numeric[column], numeric[others[0]], s=18, alpha=0.7, color="#4c8dff")
                ax.set_ylabel(str(others[0]))
            ax.set_xlabel(str(column))
        elif kind == "line":
            cols = [column] if column in numeric.columns else list(numeric.columns[:3])
            for c in cols:
                ax.plot(numeric[c].dropna().values[:2000], label=str(c)[:16])
            ax.legend(fontsize=7)
        elif kind == "pie":
            counts = df[column].value_counts().head(8)
            ax.pie(counts.values, labels=[str(i)[:16] for i in counts.index], autopct="%1.0f%%")
        elif kind == "corr":
            cm = numeric.corr()
            im = ax.imshow(cm, cmap="coolwarm", vmin=-1, vmax=1)
            ax.set_xticks(range(len(cm.columns)))
            ax.set_xticklabels([str(c)[:10] for c in cm.columns], rotation=90)
            ax.set_yticks(range(len(cm.index)))
            ax.set_yticklabels([str(i)[:10] for i in cm.index])
            fig.colorbar(im, ax=ax)
        ax.set_title(title or f"{kind} of {column}" if column else (title or kind))
        fig.tight_layout()
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in f"{kind}_{column or 'all'}")
        out = CHART_DIR / f"{safe}.png"
        fig.savefig(out, dpi=110)
        plt.close(fig)
    except Exception as e:
        return _err(f"Chart failed: {type(e).__name__}: {e}")
    return {"ok": True, "path": str(out), "kind": kind, "column": column,
            "text": f"Saved {kind} chart to {out}"}


def validate(source, rules=None):
    """Check explicit rules of the form 'column:min>0' or 'column:unique'."""
    df, bad = _frame(source)
    if bad:
        return bad
    if isinstance(rules, str):
        rules = [r.strip() for r in rules.split(",") if r.strip()]
    results = []
    for rule in rules or []:
        try:
            if ":" not in rule:
                results.append({"rule": rule, "ok": False, "error": "expected 'column:condition'"})
                continue
            col, cond = rule.split(":", 1)
            col, cond = col.strip(), cond.strip()
            if col not in df.columns:
                results.append({"rule": rule, "ok": False, "error": f"No column '{col}'"})
                continue
            if cond == "unique":
                n = int(df[col].duplicated().sum())
                results.append({"rule": rule, "ok": n == 0, "violations": n})
            elif ">" in cond or "<" in cond:
                op = ">" if ">" in cond else "<"
                bound = float(cond.split(op)[1])
                s = pd.to_numeric(df[col], errors="coerce").dropna()
                # a violation is a row that does NOT satisfy the stated condition
                n = int((s <= bound).sum()) if op == ">" else int((s >= bound).sum())
                results.append({"rule": rule, "ok": n == 0, "violations": n,
                                "non_numeric_dropped": int(len(df) - len(s))})
            elif cond == "notnull":
                n = int(df[col].isna().sum())
                results.append({"rule": rule, "ok": n == 0, "violations": n})
            else:
                results.append({"rule": rule, "ok": False, "error": f"Unknown condition '{cond}'"})
        except Exception as e:
            results.append({"rule": rule, "ok": False, "error": str(e)[:100]})
    passed = sum(1 for r in results if r.get("ok"))
    return {"ok": True, "rules": len(results), "passed": passed, "failed": len(results) - passed,
            "detail": results[:40],
            "text": f"{passed}/{len(results)} validation rule(s) passed."}
