# Data Mining — Sistema de Predicao ML

Aplicacao Streamlit para visualizar o treinamento de um modelo Ensemble Learning (VotingRegressor) sobre o dataset Brazilian E-Commerce Public Dataset by Olist.

---

## Requisitos

- Python 3.8+

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

---

## Fluxo completo

```bash

# 2. Divide em train / val / test (60/20/20), remove outliers e nulos
python split_dataset.py --csv olist_freight_dataset.csv

# 3. Treina o VotingRegressor e salva os pesos
python train.py

# 4. Roda a inferencia no conjunto de teste
python inference.py

# 5. Sobe a aplicacao Streamlit
streamlit run app.py
```

---

## Scripts

### `build_dataset.py`

Monta o `olist_freight_dataset.csv` a partir dos CSVs brutos do Olist.

```bash
python build_dataset.py
python build_dataset.py --olist "caminho/para/pasta/" --output meu_dataset.csv
```

### `split_dataset.py`

Carrega um CSV, trata nulos, remove outliers e divide em train/val/test.

```bash
python split_dataset.py --csv olist_freight_dataset.csv
python split_dataset.py --csv olist_freight_dataset.csv --outlier-pct 1.0  # sem remocao
python split_dataset.py --train 0.7 --val 0.15                             # proporcao customizada
```

### `train.py`

Treina o VotingRegressor com pre-processamento identico ao notebook (one-hot encoding + StandardScaler).

```bash
python train.py
python train.py --data data/ --weights weights/
python train.py --no-plot   # pula o grafico de normalizacao
```

Artefatos salvos em `weights/`:
- `voting_ensemble.joblib` — pesos do modelo
- `scaler.joblib` — StandardScaler ajustado no treino
- `encoder.joblib` — OneHotEncoder ajustado no treino
- `prep_meta.joblib` — metadados do pre-processamento
- `meta.joblib` — metadados do treino (target, tamanhos dos splits)
- `val_metrics.csv` — metricas na validacao
- `normalizacao.png` — histogramas antes/depois do StandardScaler

### `inference.py`

Carrega os pesos e avalia o modelo no conjunto de teste.

```bash
python inference.py
python inference.py --data data/ --weights weights/ --output predictions/
```

#### Funcoes disponiveis para uso em codigo

```python
from inference import (
    aplicar_preprocessamento,
    rodar_inferencia,
    metricas_gerais,
    casos_extremos,
    previsao_aleatoria,
)
import joblib, pandas as pd

# Carrega preprocessadores e executa inferencia
prep_meta = joblib.load("weights/prep_meta.joblib")
meta      = joblib.load("weights/meta.joblib")
features  = prep_meta["num_cols"] + prep_meta["cat_cols"]

df_test = pd.read_csv("data/test.csv")
X_test  = df_test[features]
y_test  = df_test[meta["target"]]

X_test_sc = aplicar_preprocessamento(X_test, "weights")
resultado = rodar_inferencia("voting_ensemble", "weights", X_test_sc, X_test, y_test)
# resultado: DataFrame com colunas features + valor_real + valor_previsto + erro_abs

# 1. Metricas gerais — retorna dict com R2, RMSE e MSE
metricas = metricas_gerais(resultado)
# {"r2": 0.7613, "rmse": 5.98, "mse": 35.76}

# 2. Casos extremos — retorna melhor e pior previsao
extremos = casos_extremos(resultado)
melhor = extremos["melhor"]  # pd.Series com a linha de menor erro absoluto
pior   = extremos["pior"]    # pd.Series com a linha de maior erro absoluto

# 3. Previsao aleatoria — retorna uma linha sorteada
linha = previsao_aleatoria(resultado)           # aleatorio
linha = previsao_aleatoria(resultado, seed=42)  # reproduzivel
```

---

## Modelo

O modelo e um **VotingRegressor** composto por:

- `ExtraTreesRegressor` — splits completamente aleatorios, alta diversidade
- `GradientBoostingRegressor` — arvores sequenciais, corrige erros residuais
- `RandomForestRegressor` — arvores independentes em paralelo

Os hiperparametros estao definidos em `model.py`.

### Features utilizadas

**Numericas (10):** `price`, `product_weight_g`, `product_length_cm`, `product_height_cm`,
`product_width_cm`, `volume_cm3`, `effective_weight_g`, `distance_km`, `items_in_order`, `estimated_delivery_days`

**Categoricas com one-hot encoding (3):** `customer_state`, `seller_state`, `product_category_name_english`

**Total apos encoding:** ~128 features

### Pre-processamento

| Tipo | Tratamento |
|---|---|
| Categoricas | `fillna("unknown")` + `OneHotEncoder(drop="first")` |
| Numericas | `fillna(mediana do treino)` + `StandardScaler` |
| Outliers no target | Remove `freight_value > percentil 99.5` |

> Todos os `fit()` sao realizados APENAS no conjunto de treino para evitar data leakage.
