from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DEFAULT_DATASET = Path(r"C:\Users\Win11\Downloads\14754498\olive-ripening-dataset.csv")
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "olive_harvest_model.pkl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train olive oil-content harvest model (FCDM + FCFW) from fruit measurements."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to olive ripening CSV.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output .pkl model path.")
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "harvest_plots",
        help="Directory for optional plots.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-plots", action="store_true", help="Disable plot generation.")
    return parser.parse_args()


def _normalize_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def classify_maturity(oil_content: float) -> tuple[str, str]:
    if oil_content < 15:
        return "Immature", "Too early to harvest"
    if oil_content < 18:
        return "Early Ripening", "Harvest possible but yield is low"
    if oil_content <= 22:
        return "Optimal Harvest Stage", "Recommended harvest window"
    return "Late Harvest", "Harvest immediately"


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Dataset not found: {path}")

    df = pd.read_csv(path, sep=";", decimal=",", header=1)
    df.columns = [str(col).strip() for col in df.columns]
    return df


def step1_report(df: pd.DataFrame) -> None:
    print("\n=== STEP 1 - LOAD DATA ===")
    print(f"Dataset shape: {df.shape}")
    print("Columns:")
    for col in df.columns:
        print(f"- {col}")

    print("\nSummary statistics:")
    print(df.describe(include="all").transpose().to_string())

    print("\nMissing values:")
    print(df.isna().sum().to_string())


def prepare_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str], str | None]:
    target_cols = ["FCDM Reference (%)", "FCFW Reference (%)"]
    if not all(col in df.columns for col in target_cols):
        # Fallback: keep the instruction "last two columns are targets".
        target_cols = [df.columns[-1], df.columns[-2]]
        # Ensure output order is FCDM then FCFW when available.
        target_cols = sorted(target_cols, key=lambda c: ("fcdm" not in c.lower(), c))

    date_column = None
    for col in df.columns:
        if _normalize_key(col) == "date":
            date_column = col
            break

    work = df.copy()
    if date_column is not None:
        work[date_column] = pd.to_datetime(work[date_column].ffill(), dayfirst=True, errors="coerce")
        work["Date ordinal"] = work[date_column].map(lambda x: x.toordinal() if pd.notna(x) else np.nan)
        work = work.drop(columns=[date_column])

    x = work.drop(columns=target_cols)
    y = work[target_cols].astype(float)
    return x, y, target_cols, date_column


def build_preprocessor(x: pd.DataFrame) -> tuple[ColumnTransformer, list[str], list[str]]:
    numeric_features = x.select_dtypes(include=[np.number]).columns.tolist()
    categorical_features = [col for col in x.columns if col not in numeric_features]

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ]
    )
    return preprocessor, numeric_features, categorical_features


def build_models(seed: int) -> dict[str, Any]:
    return {
        "RandomForestRegressor": RandomForestRegressor(n_estimators=320, random_state=seed, n_jobs=-1),
        "GradientBoostingRegressor": MultiOutputRegressor(GradientBoostingRegressor(random_state=seed)),
        "LinearRegression": LinearRegression(),
    }


def evaluate_model(y_true: pd.DataFrame, y_pred: np.ndarray, target_cols: list[str]) -> dict[str, Any]:
    per_target: dict[str, dict[str, float]] = {}
    for idx, target in enumerate(target_cols):
        per_target[target] = {
            "r2": float(r2_score(y_true.iloc[:, idx], y_pred[:, idx])),
            "mae": float(mean_absolute_error(y_true.iloc[:, idx], y_pred[:, idx])),
            "mse": float(mean_squared_error(y_true.iloc[:, idx], y_pred[:, idx])),
        }

    avg_r2 = float(np.mean([v["r2"] for v in per_target.values()]))
    avg_mae = float(np.mean([v["mae"] for v in per_target.values()]))
    avg_mse = float(np.mean([v["mse"] for v in per_target.values()]))
    return {
        "per_target": per_target,
        "avg_r2": avg_r2,
        "avg_mae": avg_mae,
        "avg_mse": avg_mse,
    }


def select_best(metrics_by_model: dict[str, dict[str, Any]]) -> str:
    ranked = sorted(
        metrics_by_model.items(),
        key=lambda item: (-item[1]["avg_r2"], item[1]["avg_mae"], item[1]["avg_mse"]),
    )
    return ranked[0][0]


def extract_feature_importance(
    pipeline: Pipeline,
    x_train: pd.DataFrame,
) -> pd.DataFrame | None:
    pre = pipeline.named_steps["preprocessor"]
    reg = pipeline.named_steps["regressor"]

    if not hasattr(pre, "get_feature_names_out"):
        return None

    names = pre.get_feature_names_out()

    if isinstance(reg, RandomForestRegressor) and hasattr(reg, "feature_importances_"):
        values = reg.feature_importances_
    elif isinstance(reg, LinearRegression) and hasattr(reg, "coef_"):
        coef = np.asarray(reg.coef_)
        values = np.mean(np.abs(coef), axis=0) if coef.ndim == 2 else np.abs(coef)
    else:
        return None

    if len(values) != len(names):
        return None

    importance = pd.DataFrame({"feature": names, "importance": values}).sort_values(
        by="importance", ascending=False
    )
    return importance


def save_plots(
    plots_dir: Path,
    y_train: pd.DataFrame,
    y_test: pd.DataFrame,
    y_pred: np.ndarray,
    target_cols: list[str],
    feature_importance: pd.DataFrame | None,
) -> None:
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Oil content distribution.
    fig, axes = plt.subplots(1, len(target_cols), figsize=(11, 4))
    if len(target_cols) == 1:
        axes = [axes]
    for idx, target in enumerate(target_cols):
        axes[idx].hist(y_train.iloc[:, idx], bins=20, alpha=0.8, color="#4f8f3f")
        axes[idx].set_title(f"Distribution: {target}")
        axes[idx].set_xlabel("Oil content")
        axes[idx].set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(plots_dir / "oil_content_distribution.png", dpi=140)
    plt.close(fig)

    # Prediction vs real.
    fig, axes = plt.subplots(1, len(target_cols), figsize=(11, 4))
    if len(target_cols) == 1:
        axes = [axes]
    for idx, target in enumerate(target_cols):
        axes[idx].scatter(y_test.iloc[:, idx], y_pred[:, idx], alpha=0.7, color="#2f6c2a", edgecolor="none")
        low = min(float(y_test.iloc[:, idx].min()), float(y_pred[:, idx].min()))
        high = max(float(y_test.iloc[:, idx].max()), float(y_pred[:, idx].max()))
        axes[idx].plot([low, high], [low, high], "--", color="#b7533f", linewidth=1.5)
        axes[idx].set_title(f"Prediction vs Real: {target}")
        axes[idx].set_xlabel("Real")
        axes[idx].set_ylabel("Predicted")
    fig.tight_layout()
    fig.savefig(plots_dir / "prediction_vs_real.png", dpi=140)
    plt.close(fig)

    # Feature importance (when available).
    if feature_importance is not None and not feature_importance.empty:
        top = feature_importance.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(top["feature"], top["importance"], color="#5f9f43")
        ax.set_title("Top Feature Importance")
        ax.set_xlabel("Importance")
        fig.tight_layout()
        fig.savefig(plots_dir / "feature_importance.png", dpi=140)
        plt.close(fig)


def predict_olive_harvest(sample: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    feature_columns: list[str] = bundle["feature_columns"]
    numeric_features: list[str] = bundle["numeric_features"]
    target_columns: list[str] = bundle["target_columns"]
    pipeline: Pipeline = bundle["pipeline"]

    normalized_map = {_normalize_key(col): col for col in feature_columns}
    row = {col: np.nan for col in feature_columns}

    for key, value in sample.items():
        normalized = _normalize_key(str(key))
        if normalized in normalized_map:
            row[normalized_map[normalized]] = value

    if "Date ordinal" in row:
        raw_date = sample.get("Date") or sample.get("date")
        if raw_date and pd.isna(row["Date ordinal"]):
            parsed = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
            if pd.notna(parsed):
                row["Date ordinal"] = float(parsed.toordinal())

    x_input = pd.DataFrame([row])
    for col in numeric_features:
        if col in x_input.columns:
            x_input[col] = pd.to_numeric(x_input[col], errors="coerce")

    y_pred = pipeline.predict(x_input)[0]
    pred_map = {target_columns[idx]: float(y_pred[idx]) for idx in range(len(target_columns))}

    fcdm_key = next((col for col in target_columns if "fcdm" in col.lower()), target_columns[0])
    fcfw_key = next((col for col in target_columns if "fcfw" in col.lower()), target_columns[-1])

    # Maturity thresholds (15-22) match fresh-weight scale better, so use FCFW as oil_content.
    estimated_oil_content = float(pred_map[fcfw_key])
    maturity_stage, harvest_recommendation = classify_maturity(estimated_oil_content)

    return {
        "estimated_oil_content": round(estimated_oil_content, 3),
        "estimated_fcdm": round(float(pred_map[fcdm_key]), 3),
        "estimated_fcfw": round(float(pred_map[fcfw_key]), 3),
        "maturity_stage": maturity_stage,
        "harvest_recommendation": harvest_recommendation,
    }


def main() -> None:
    args = parse_args()

    df = load_dataset(args.dataset)
    step1_report(df)

    print("\n=== STEP 2 - DATA PREPROCESSING ===")
    x, y, target_cols, date_col = prepare_dataset(df)
    preprocessor, numeric_features, categorical_features = build_preprocessor(x)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.seed,
    )
    print(f"Train size: {x_train.shape[0]} rows")
    print(f"Test size: {x_test.shape[0]} rows")
    print(f"Numeric features normalized: {len(numeric_features)}")
    print(f"Categorical features: {len(categorical_features)}")

    print("\n=== STEP 3 - TRAIN MODELS ===")
    model_candidates = build_models(args.seed)
    fitted_pipelines: dict[str, Pipeline] = {}
    metrics_by_model: dict[str, dict[str, Any]] = {}
    preds_by_model: dict[str, np.ndarray] = {}

    for model_name, regressor in model_candidates.items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", regressor),
            ]
        )
        pipeline.fit(x_train, y_train)
        preds = pipeline.predict(x_test)

        fitted_pipelines[model_name] = pipeline
        preds_by_model[model_name] = preds
        metrics_by_model[model_name] = evaluate_model(y_test, preds, target_cols)

        m = metrics_by_model[model_name]
        print(
            f"{model_name}: avg_r2={m['avg_r2']:.4f} avg_mae={m['avg_mae']:.4f} avg_mse={m['avg_mse']:.4f}"
        )

    best_model_name = select_best(metrics_by_model)
    best_pipeline = fitted_pipelines[best_model_name]
    best_preds = preds_by_model[best_model_name]

    print(f"Best model selected: {best_model_name}")

    print("\n=== STEP 4/5 - MATURITY LOGIC + PREDICTION FUNCTION ===")
    bundle = {
        "pipeline": best_pipeline,
        "feature_columns": x.columns.tolist(),
        "target_columns": target_cols,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "date_column": date_col,
        "best_model_name": best_model_name,
        "metrics": metrics_by_model,
    }

    sample_prediction = predict_olive_harvest(x_test.iloc[0].to_dict(), bundle)
    print("Sample predict_olive_harvest(sample):")
    print(json.dumps(sample_prediction, indent=2))

    print("\n=== STEP 6 - SAVE MODEL ===")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.output)
    print(f"Model saved to: {args.output}")

    metrics_path = args.output.with_suffix(".metrics.json")
    with metrics_path.open("w", encoding="utf-8") as fp:
        json.dump(metrics_by_model, fp, indent=2)
    print(f"Metrics saved to: {metrics_path}")

    if not args.no_plots:
        print("\n=== STEP 8 - OPTIONAL VISUALIZATION ===")
        importance = extract_feature_importance(best_pipeline, x_train)
        save_plots(
            plots_dir=args.plots_dir,
            y_train=y_train,
            y_test=y_test,
            y_pred=best_preds,
            target_cols=target_cols,
            feature_importance=importance,
        )
        print(f"Plots saved under: {args.plots_dir}")


if __name__ == "__main__":
    main()
