"""
split_dataset.py
----------------
Carrega um CSV (ou gera dados sinteticos) e salva os splits train/val/test.

Proporcao padrao: 60% train | 20% val | 20% test  (igual ao notebook)

Uso:
    python split_dataset.py --csv olist_freight_dataset.csv
    python split_dataset.py --csv meu_dataset.csv --target freight_value
    python split_dataset.py --csv meu_dataset.csv --outlier-pct 1.0  # sem remocao
    python split_dataset.py                                           # dados sinteticos
"""

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

SEED = 42


def carregar_csv(
    path: str,
    sep: str = ",",
    encoding: str = "utf-8",
    drop_unnamed: bool = True,
) -> pd.DataFrame:
    """
    Le um arquivo CSV e retorna um DataFrame limpo.

    Parametros
    ----------
    path : str
        Caminho para o arquivo CSV.
    sep : str
        Separador de colunas (default: ',').
    encoding : str
        Encoding do arquivo (default: 'utf-8').
    drop_unnamed : bool
        Remove colunas 'Unnamed: *' geradas por indices soltos (default: True).

    Retorna
    -------
    pd.DataFrame
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    df = pd.read_csv(path, sep=sep, encoding=encoding)

    if drop_unnamed:
        unnamed = [c for c in df.columns if c.startswith("Unnamed:")]
        if unnamed:
            df = df.drop(columns=unnamed)

    # Remove linhas completamente vazias
    df = df.dropna(how="all").reset_index(drop=True)

    print(f"CSV carregado: {path}")
    print(f"  Shape   : {df.shape}")
    print(f"  Colunas : {list(df.columns)}")
    nulos = df.isnull().sum()
    nulos = nulos[nulos > 0]
    if not nulos.empty:
        print(f"  Nulos   : {nulos.to_dict()}")

    return df


def tratar_nulos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tratamento de nulos para o dataset Olist (igual ao notebook):
      - product_category_name_english: fillna('unknown')
      - distance_km: fillna(mediana)
    Para outros datasets, os nulos numericos serao tratados no train.py.
    """
    if "product_category_name_english" in df.columns:
        antes = df["product_category_name_english"].isna().sum()
        df["product_category_name_english"] = df["product_category_name_english"].fillna("unknown")
        if antes:
            print(f"  product_category_name_english: {antes} nulos -> 'unknown'")

    if "distance_km" in df.columns:
        antes = df["distance_km"].isna().sum()
        mediana = df["distance_km"].median()
        df["distance_km"] = df["distance_km"].fillna(mediana)
        if antes:
            print(f"  distance_km: {antes} nulos -> mediana ({mediana:.1f} km)")

    return df


def remover_outliers(df: pd.DataFrame, target: str, pct: float = 0.995) -> pd.DataFrame:
    """
    Remove linhas onde o target excede o percentil pct.
    Fretes extremos distorcem o aprendizado sem agregar valor real.
    (igual ao notebook: percentil 99.5)
    """
    if pct >= 1.0:
        return df
    limite = df[target].quantile(pct)
    antes  = len(df)
    df     = df[df[target] <= limite].copy()
    print(f"  Outliers removidos: {antes - len(df)} linhas (target > p{pct*100:.1f} = {limite:.2f})")
    return df


def gerar_dataset(n: int = 1000) -> pd.DataFrame:
    """Gera o dataset sintetico."""
    rng = np.random.default_rng(SEED)
    df = pd.DataFrame(
        {
            "idade": rng.integers(18, 70, n),
            "salario": rng.integers(1500, 12000, n),
            "anos_experiencia": rng.integers(0, 30, n),
            "valor_real": rng.integers(1000, 5000, n),
        }
    )
    return df


def split_and_save(
    df: pd.DataFrame,
    output_dir: str = "data",
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> None:
    """Divide o DataFrame e salva train.csv, val.csv e test.csv."""
    assert train_ratio + val_ratio < 1.0, "train + val deve ser menor que 1"

    os.makedirs(output_dir, exist_ok=True)

    test_ratio = 1.0 - train_ratio - val_ratio
    df_train_val, df_test = train_test_split(df, test_size=test_ratio, random_state=SEED)

    val_ratio_adjusted = val_ratio / (train_ratio + val_ratio)
    df_train, df_val = train_test_split(df_train_val, test_size=val_ratio_adjusted, random_state=SEED)

    df_train.to_csv(os.path.join(output_dir, "train.csv"), index=False)
    df_val.to_csv(os.path.join(output_dir, "val.csv"), index=False)
    df_test.to_csv(os.path.join(output_dir, "test.csv"), index=False)

    total = len(df)
    print(f"\nDataset total : {total} amostras")
    print(f"  train.csv   : {len(df_train)} ({len(df_train)/total:.0%})")
    print(f"  val.csv     : {len(df_val)} ({len(df_val)/total:.0%})")
    print(f"  test.csv    : {len(df_test)} ({len(df_test)/total:.0%})")
    print(f"\nArquivos salvos em: {os.path.abspath(output_dir)}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Carrega um CSV e divide em train/val/test (padrao 60/20/20)."
    )
    parser.add_argument("--csv",         type=str,   default=None,           help="Caminho para o CSV (opcional)")
    parser.add_argument("--sep",         type=str,   default=",",            help="Separador do CSV (default: ',')")
    parser.add_argument("--encoding",    type=str,   default="utf-8",        help="Encoding do CSV (default: utf-8)")
    parser.add_argument("--target",      type=str,   default="freight_value",help="Coluna alvo para remocao de outliers (default: freight_value)")
    parser.add_argument("--outlier-pct", type=float, default=0.995,          help="Percentil para corte de outliers no target (default: 0.995, use 1.0 para desativar)")
    parser.add_argument("--n",           type=int,   default=1000,           help="Amostras sinteticas quando --csv nao e usado")
    parser.add_argument("--train",       type=float, default=0.60,           help="Proporcao de treino (default: 0.60)")
    parser.add_argument("--val",         type=float, default=0.20,           help="Proporcao de validacao (default: 0.20)")
    parser.add_argument("--output",      type=str,   default="data",         help="Diretorio de saida (default: data/)")
    args = parser.parse_args()

    if args.csv:
        df = carregar_csv(args.csv, sep=args.sep, encoding=args.encoding)
        print("\n-- Tratando nulos --")
        df = tratar_nulos(df)
        if args.target in df.columns:
            print("\n-- Removendo outliers --")
            df = remover_outliers(df, target=args.target, pct=args.outlier_pct)
    else:
        print("Nenhum --csv fornecido. Usando dataset sintetico.")
        df = gerar_dataset(n=args.n)

    split_and_save(df, output_dir=args.output, train_ratio=args.train, val_ratio=args.val)
