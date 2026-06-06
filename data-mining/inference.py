"""
inference.py
------------
Carrega os pesos e preprocessadores salvos pelo train.py e faz inferencia no test.csv.

Funcoes principais:
    metricas_gerais(resultado)     -> dict com R2, RMSE, MSE
    casos_extremos(resultado)      -> dict com melhor e pior previsao
    previsao_aleatoria(resultado)  -> linha aleatoria do resultado

Uso:
    python inference.py
    python inference.py --data data/ --weights weights/ --output predictions/
"""

import argparse
import os
import random

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

TARGET           = "freight_value"
AVAILABLE_MODELS = ["voting_ensemble"]


# ── Pre-processamento ─────────────────────────────────────────────────────────

def aplicar_preprocessamento(X_test, weights_dir):
    """Aplica o mesmo pre-processamento do treino: one-hot + scaler."""
    scaler    = joblib.load(os.path.join(weights_dir, "scaler.joblib"))
    encoder   = joblib.load(os.path.join(weights_dir, "encoder.joblib"))
    prep_meta = joblib.load(os.path.join(weights_dir, "prep_meta.joblib"))

    num_cols = prep_meta["num_cols"]
    cat_cols = prep_meta["cat_cols"]
    medianas = prep_meta["medianas"]

    num_sc  = scaler.transform(X_test[num_cols].fillna(pd.Series(medianas)))
    cat_enc = encoder.transform(X_test[cat_cols].fillna("unknown"))

    X_sc = np.hstack([num_sc, cat_enc])
    print(f"  Preprocessamento aplicado: {X_sc.shape[1]} features.")
    return X_sc


# ── Inferencia ────────────────────────────────────────────────────────────────

def rodar_inferencia(model_name, weights_dir, X_test_sc, X_test_original, y_test):
    """
    Carrega o modelo, gera predicoes e retorna o DataFrame de resultados
    com colunas: features originais, valor_real, valor_previsto, erro_abs.
    """
    weight_path = os.path.join(weights_dir, f"{model_name}.joblib")
    if not os.path.exists(weight_path):
        raise FileNotFoundError(f"Pesos nao encontrados: {weight_path}")

    model  = joblib.load(weight_path)
    y_pred = model.predict(X_test_sc)

    resultado = X_test_original.copy().reset_index(drop=True)
    resultado["valor_previsto"] = y_pred

    if y_test is not None:
        resultado["valor_real"] = y_test.values
        resultado["erro_abs"]   = np.abs(resultado["valor_real"] - resultado["valor_previsto"])

    return resultado


# ── Funcoes de analise ────────────────────────────────────────────────────────

def metricas_gerais(resultado: pd.DataFrame) -> dict:
    """
    Calcula e retorna as metricas gerais do modelo sobre o conjunto de teste.

    Retorna
    -------
    dict com chaves: r2, rmse, mse
    """
    if "valor_real" not in resultado.columns:
        raise ValueError("O DataFrame nao possui 'valor_real'. Execute com ground truth disponivel.")

    y_true = resultado["valor_real"]
    y_pred = resultado["valor_previsto"]

    mse  = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    r2   = r2_score(y_true, y_pred)

    metrics = {"r2": round(r2, 4), "rmse": round(rmse, 4), "mse": round(mse, 4)}

    print("-- Metricas Gerais (test) --")
    print(f"  R2   : {metrics['r2']}")
    print(f"  RMSE : {metrics['rmse']}")
    print(f"  MSE  : {metrics['mse']}")

    return metrics


def casos_extremos(resultado: pd.DataFrame) -> dict:
    """
    Retorna o melhor caso (menor erro absoluto) e o pior caso (maior erro absoluto).

    Retorna
    -------
    dict com chaves:
        melhor -> Series com a linha de menor erro
        pior   -> Series com a linha de maior erro
    """
    if "erro_abs" not in resultado.columns:
        raise ValueError("O DataFrame nao possui 'erro_abs'. Execute com ground truth disponivel.")

    idx_melhor = resultado["erro_abs"].idxmin()
    idx_pior   = resultado["erro_abs"].idxmax()

    melhor = resultado.loc[idx_melhor]
    pior   = resultado.loc[idx_pior]

    print("-- Melhor Previsao --")
    print(f"  Real     : {melhor['valor_real']:.2f}")
    print(f"  Previsto : {melhor['valor_previsto']:.2f}")
    print(f"  Erro abs : {melhor['erro_abs']:.2f}")

    print("-- Pior Previsao --")
    print(f"  Real     : {pior['valor_real']:.2f}")
    print(f"  Previsto : {pior['valor_previsto']:.2f}")
    print(f"  Erro abs : {pior['erro_abs']:.2f}")

    return {"melhor": melhor, "pior": pior}


def previsao_aleatoria(resultado: pd.DataFrame, seed: int = None) -> pd.Series:
    """
    Retorna uma linha aleatoria do resultado da inferencia.

    Parametros
    ----------
    resultado : DataFrame com as predicoes
    seed      : semente para reproducibilidade (opcional)

    Retorna
    -------
    pd.Series com a linha sorteada
    """
    if seed is not None:
        random.seed(seed)

    idx  = random.randint(0, len(resultado) - 1)
    linha = resultado.iloc[idx]

    print("-- Previsao Aleatoria --")
    print(f"  Indice   : {idx}")
    print(f"  Previsto : {linha['valor_previsto']:.2f}")
    if "valor_real" in linha:
        print(f"  Real     : {linha['valor_real']:.2f}")
        print(f"  Erro abs : {linha['erro_abs']:.2f}")

    return linha


# ── Pipeline principal ────────────────────────────────────────────────────────

def main(data_dir, weights_dir, output_dir, model_choice):
    meta      = joblib.load(os.path.join(weights_dir, "meta.joblib"))
    prep_meta = joblib.load(os.path.join(weights_dir, "prep_meta.joblib"))
    target    = meta.get("target", TARGET)
    features  = prep_meta["num_cols"] + prep_meta["cat_cols"]

    print("-- Carregando test.csv --")
    df_test = pd.read_csv(os.path.join(data_dir, "test.csv"))
    X_test  = df_test[features]
    y_test  = df_test[target] if target in df_test.columns else None
    print(f"  Test: {X_test.shape}")

    X_test_sc = aplicar_preprocessamento(X_test, weights_dir)

    print(f"\n-- Rodando inferencia ({model_choice}) --")
    resultado = rodar_inferencia(model_choice, weights_dir, X_test_sc, X_test, y_test)

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"predictions_{model_choice}.csv")
    resultado.to_csv(out_path, index=False)
    print(f"  Predicoes salvas em {out_path}")

    print()
    metricas = metricas_gerais(resultado)
    print()
    casos_extremos(resultado)
    print()
    previsao_aleatoria(resultado)

    # Salva metricas
    pd.DataFrame([metricas]).to_csv(
        os.path.join(output_dir, "test_metrics.csv"), index=False
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",    type=str, default="data")
    parser.add_argument("--weights", type=str, default="weights")
    parser.add_argument("--output",  type=str, default="predictions")
    parser.add_argument("--model",   type=str, default="voting_ensemble",
                        choices=AVAILABLE_MODELS)
    args = parser.parse_args()
    main(args.data, args.weights, args.output, args.model)
