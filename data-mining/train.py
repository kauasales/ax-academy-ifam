"""
train.py
--------
Treina o VotingRegressor (ensemble) e salva os pesos em weights/.

Pre-processamento:
  - Categoricas: fillna('unknown') + OneHotEncoder(drop='first') fit no treino
  - Numericas  : fillna(mediana) + StandardScaler fit no treino
  (igual ao notebook, fit APENAS no treino para evitar data leakage)

Uso:
    python train.py
    python train.py --data data/ --weights weights/
    python train.py --no-plot
"""

import argparse
import os
import time

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from model import build_model, SEED

TARGET = "freight_value"

NUM_FEATURES = [
    "price", "product_weight_g", "product_length_cm", "product_height_cm",
    "product_width_cm", "volume_cm3", "effective_weight_g",
    "distance_km", "items_in_order", "estimated_delivery_days",
]

CAT_FEATURES = [
    "customer_state", "seller_state", "product_category_name_english",
]


def carregar_splits(data_dir: str, target: str = TARGET):
    paths = {s: os.path.join(data_dir, f"{s}.csv") for s in ("train", "val", "test")}
    for s, p in paths.items():
        if not os.path.exists(p):
            raise FileNotFoundError(f"{s}.csv nao encontrado em '{data_dir}'.\nExecute: python split_dataset.py")

    df_train = pd.read_csv(paths["train"])
    df_val   = pd.read_csv(paths["val"])
    df_test  = pd.read_csv(paths["test"])

    if target not in df_train.columns:
        raise KeyError(f"Target '{target}' nao encontrado. Colunas: {list(df_train.columns)}")

    num_cols = [c for c in NUM_FEATURES if c in df_train.columns]
    cat_cols = [c for c in CAT_FEATURES if c in df_train.columns]

    print(f"  Numericas  ({len(num_cols)}): {num_cols}")
    print(f"  Categoricas ({len(cat_cols)}): {cat_cols}")

    X_train = df_train[num_cols + cat_cols]
    X_val   = df_val[num_cols + cat_cols]
    X_test  = df_test[num_cols + cat_cols]
    y_train = df_train[target]
    y_val   = df_val[target]
    y_test  = df_test[target]

    return X_train, y_train, X_val, y_val, X_test, y_test, num_cols, cat_cols


def preprocessar(X_train, X_val, X_test, num_cols, cat_cols, weights_dir):
    """
    Pre-processamento identico ao notebook:
      1. Categoricas: fillna('unknown') + OneHotEncoder(drop='first') fit no treino
      2. Numericas  : fillna(mediana do treino) + StandardScaler fit no treino
    Fit APENAS no treino para evitar data leakage.
    """
    enc = OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False)

    def prep_cat(df, fit=False):
        d = df[cat_cols].copy().fillna("unknown")
        if fit:
            enc.fit(d)
        return enc.transform(d)

    cat_train = prep_cat(X_train, fit=True)
    cat_val   = prep_cat(X_val)
    cat_test  = prep_cat(X_test)

    medianas = X_train[num_cols].median()
    scaler   = StandardScaler()
    num_train = scaler.fit_transform(X_train[num_cols].fillna(medianas))
    num_val   = scaler.transform(X_val[num_cols].fillna(medianas))
    num_test  = scaler.transform(X_test[num_cols].fillna(medianas))

    X_train_sc = np.hstack([num_train, cat_train])
    X_val_sc   = np.hstack([num_val,   cat_val])
    X_test_sc  = np.hstack([num_test,  cat_test])

    print(f"  Shape apos encoding: {X_train_sc.shape[1]} features "
          f"({len(num_cols)} num + {cat_train.shape[1]} one-hot)")

    joblib.dump(scaler, os.path.join(weights_dir, "scaler.joblib"))
    joblib.dump(enc,    os.path.join(weights_dir, "encoder.joblib"))
    joblib.dump({
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "cat_feature_names": enc.get_feature_names_out(cat_cols).tolist(),
        "medianas": medianas.to_dict(),
    }, os.path.join(weights_dir, "prep_meta.joblib"))
    print(f"  Scaler  salvo em {weights_dir}/scaler.joblib")
    print(f"  Encoder salvo em {weights_dir}/encoder.joblib")

    return X_train_sc, X_val_sc, X_test_sc


def plotar_normalizacao(X_train, X_train_sc, num_cols, output_dir):
    feats_vis = [f for f in ["effective_weight_g", "distance_km"] if f in num_cols]
    if not feats_vis:
        feats_vis = num_cols[:2]
    if not feats_vis:
        return
    cores = ["#3498db", "#e67e22"]
    fig, axes = plt.subplots(len(feats_vis), 2, figsize=(13, 4 * len(feats_vis)))
    fig.suptitle("StandardScaler - Antes vs. Depois", fontsize=13, fontweight="bold")
    if len(feats_vis) == 1:
        axes = [axes]
    for row, (feat, cor) in enumerate(zip(feats_vis, cores)):
        idx      = num_cols.index(feat)
        col_orig = X_train[feat].dropna()
        col_sc   = X_train_sc[:, idx]
        axes[row][0].hist(col_orig, bins=50, color=cor, edgecolor="white", alpha=0.85)
        axes[row][0].set_title(f"{feat} - ANTES", fontweight="bold")
        axes[row][0].axvline(col_orig.mean(), color="red", linestyle="--",
                              label=f"Media={col_orig.mean():.1f}")
        axes[row][0].legend(fontsize=8)
        axes[row][1].hist(col_sc, bins=50, color=cor, edgecolor="white", alpha=0.85)
        axes[row][1].set_title(f"{feat} - DEPOIS (z-score)", fontweight="bold")
        axes[row][1].axvline(col_sc.mean(), color="red", linestyle="--", label="Media~0")
        axes[row][1].legend(fontsize=8)
    plt.tight_layout()
    plot_path = os.path.join(output_dir, "normalizacao.png")
    fig.savefig(plot_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Grafico salvo em {plot_path}")


def avaliar(name, y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)
    print(f"  [{name}]  R2={r2:.4f}  RMSE={rmse:.2f}")
    return {"model": name, "r2_val": r2, "rmse_val": rmse}


def treinar_e_salvar(data_dir, weights_dir, plot=True, target=TARGET):
    os.makedirs(weights_dir, exist_ok=True)

    print("-- Carregando splits --")
    X_train, y_train, X_val, y_val, X_test, y_test, num_cols, cat_cols = carregar_splits(data_dir, target)
    print(f"  Train: {X_train.shape}  |  Val: {X_val.shape}  |  Test: {X_test.shape}")

    print("\n-- Pre-processamento (fit so no treino) --")
    X_train_sc, X_val_sc, X_test_sc = preprocessar(
        X_train, X_val, X_test, num_cols, cat_cols, weights_dir
    )

    if plot:
        print("\n-- Gerando visualizacao da normalizacao --")
        plotar_normalizacao(X_train, X_train_sc, num_cols, weights_dir)

    print("\n-- Treinando VotingRegressor (ensemble) --")
    t0       = time.time()
    ensemble = build_model()
    ensemble.fit(X_train_sc, y_train)
    elapsed  = time.time() - t0
    metrics  = avaliar("voting_ensemble", y_val, ensemble.predict(X_val_sc))
    metrics["train_time_s"] = round(elapsed, 2)

    path = os.path.join(weights_dir, "voting_ensemble.joblib")
    joblib.dump(ensemble, path)
    print(f"  Pesos salvos em {path}  ({elapsed:.1f}s)")

    joblib.dump({"target": target, "train_size": len(X_train),
                 "val_size": len(X_val), "test_size": len(X_test)},
                os.path.join(weights_dir, "meta.joblib"))

    print("\n-- Resumo (val) --")
    df_res = pd.DataFrame([metrics])
    print(df_res.to_string(index=False))
    df_res.to_csv(os.path.join(weights_dir, "val_metrics.csv"), index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",    type=str, default="data")
    parser.add_argument("--weights", type=str, default="weights")
    parser.add_argument("--target",  type=str, default=TARGET)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()
    treinar_e_salvar(args.data, args.weights, plot=not args.no_plot, target=args.target)
