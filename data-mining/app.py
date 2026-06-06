import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import joblib
import random

# Funções do inference.py adaptadas
TARGET = "freight_value"

def carregar_dados_e_modelo(data_dir="data", weights_dir="weights"):
    """Carrega o dataset de teste e os artefatos do modelo"""
    meta = joblib.load(os.path.join(weights_dir, "meta.joblib"))
    prep_meta = joblib.load(os.path.join(weights_dir, "prep_meta.joblib"))
    
    df_test = pd.read_csv(os.path.join(data_dir, "test.csv"))
    features = prep_meta["num_cols"] + prep_meta["cat_cols"]
    
    return df_test, features, prep_meta, meta

def aplicar_preprocessamento_parcial(X_test, weights_dir, prep_meta):
    """Aplica pre-processamento para uma amostra dos dados"""
    scaler = joblib.load(os.path.join(weights_dir, "scaler.joblib"))
    encoder = joblib.load(os.path.join(weights_dir, "encoder.joblib"))
    
    num_cols = prep_meta["num_cols"]
    cat_cols = prep_meta["cat_cols"]
    medianas = prep_meta["medianas"]
    
    X_test_num = X_test[num_cols].fillna(pd.Series(medianas))
    X_test_cat = X_test[cat_cols].fillna("unknown")
    
    num_sc = scaler.transform(X_test_num)
    cat_enc = encoder.transform(X_test_cat)
    
    X_sc = np.hstack([num_sc, cat_enc])
    return X_sc

def executar_inferencia(model_name, weights_dir, X_test_sc, X_test_original, y_test):
    """Executa inferência no modelo"""
    weight_path = os.path.join(weights_dir, f"{model_name}.joblib")
    model = joblib.load(weight_path)
    y_pred = model.predict(X_test_sc)
    
    resultado = X_test_original.copy().reset_index(drop=True)
    resultado["valor_previsto"] = y_pred
    
    if y_test is not None:
        resultado["valor_real"] = y_test.values
        resultado["erro_abs"] = np.abs(resultado["valor_real"] - resultado["valor_previsto"])
    
    return resultado

def metricas_gerais(resultado):
    """Calcula métricas do modelo"""
    y_true = resultado["valor_real"]
    y_pred = resultado["valor_previsto"]
    
    from sklearn.metrics import mean_squared_error, r2_score
    mse = mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    
    return {"r2": round(r2, 4), "mse": round(mse, 4)}

# Configuração da página
st.set_page_config(
    page_title="Sistema de Predição ML",
    layout="wide"
)

st.title("Sistema de Predição com Machine Learning")

@st.cache_data
def carregar_dataset_completo():
    """Carrega o dataset completo de teste"""
    try:
        df_test, features, prep_meta, meta = carregar_dados_e_modelo()
        return df_test, features, prep_meta, meta
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None, None, None

def executar_modelo(percentual_teste):
    """Executa modelo com percentual específico do dataset de teste"""
    df_test, features, prep_meta, meta = carregar_dataset_completo()
    
    if df_test is None:
        return None, None
    
    X_completo = df_test[features]
    y_completo = df_test[TARGET] if TARGET in df_test.columns else None
    
    tamanho_amostra = int(len(X_completo) * (percentual_teste / 100))
    indices_amostra = np.random.choice(len(X_completo), tamanho_amostra, replace=False)
    
    X_amostra = X_completo.iloc[indices_amostra]
    y_amostra = y_completo.iloc[indices_amostra] if y_completo is not None else None
    
    X_sc = aplicar_preprocessamento_parcial(X_amostra, "weights", prep_meta)
    resultado = executar_inferencia("voting_ensemble", "weights", X_sc, X_amostra, y_amostra)
    metricas = metricas_gerais(resultado)
    
    return resultado, metricas["r2"]

# Carregar dados iniciais
df_test, features, prep_meta, meta = carregar_dataset_completo()

# Definição das Tabs Principais (Sem emojis)
aba1, aba2, aba3, aba4 = st.tabs([
    "Dataset",
    "Configuracao",
    "Rodar Modelo",
    "Resultados"
])

# --- ABA 1: DATASET ---
with aba1:
    if df_test is not None:
        sub_aba1_1, sub_aba1_2, sub_aba1_3 = st.tabs([
            "Resumo Estatistico", 
            "Visualizacao Interativa", 
            "Dicionario de Variaveis"
        ])
        
        with sub_aba1_1:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total de Registros (Linhas)", value=f"{df_test.shape[0]:,}".replace(",", "."))
            with col2:
                st.metric(label="Atributos (Colunas)", value=df_test.shape[1])
            with col3:
                st.metric(label="Variavel Alvo (Target)", value=TARGET)
        
        with sub_aba1_2:
            st.caption("Exploracao das primeiras 100 linhas do conjunto de teste.")
            st.dataframe(df_test.head(100), use_container_width=True)
            
        with sub_aba1_3:
            st.markdown("""
            Para alimentar o modelo Voting Ensemble, as variaveis originais foram mapeadas e divididas 
            entre numericas e categoricas. Cada tipo passa por um tratamento de dados especifico antes da inferencia.
            """)
            
            feat_col1, feat_col2 = st.columns(2)
            with feat_col1:
                st.markdown(f"### Features Numericas ({len(prep_meta['num_cols'])})")
                st.markdown("*Preenchimento de nulos pela mediana e normalizacao com StandardScaler.*")
                num_tags = " ".join([f"`{col}`" for col in prep_meta['num_cols']])
                st.write(num_tags)
                
            with feat_col2:
                st.markdown(f"### Features Categoricas ({len(prep_meta['cat_cols'])})")
                st.markdown("*Valores ausentes recebem 'unknown' e passam por OneHotEncoder ou TargetEncoder.*")
                cat_tags = " ".join([f"`{col}`" for col in prep_meta['cat_cols']])
                st.write(cat_tags)
                
            st.info("Nota de Engenharia de Dados: O pipeline garante que nenhum valor nulo chegue ao modelo final, prevenindo quebras em tempo de execucao.")
    else:
        st.error("Dataset nao encontrado. Verifique se o arquivo 'data/test.csv' existe.")

# --- ABA 2: CONFIGURAÇÃO ---
with aba2:
    sub_aba2_1, sub_aba2_2 = st.tabs(["Parametros", "Composicao do Modelo"])
    
    with sub_aba2_1:
        percentual = st.slider(
            "Percentual do Dataset de Teste para Previsao",
            min_value=10,
            max_value=100,
            value=80,
            help="Selecione qual percentual dos dados de teste sera usado para fazer previsoes"
        )
        modelo = st.selectbox("Modelo", ["Voting Ensemble"])
        
    with sub_aba2_2:
        st.info(
            f"**Configuracao atual selecionada:**\n\n"
            f"• Modelo: {modelo}\n"
            f"• Percentual do teste: {percentual}%\n"
            f"• Amostra de teste: {int(df_test.shape[0] * percentual / 100) if df_test is not None else 0} registros\n\n"
            f"**Algoritmos integrados no Ensemble:**\n"
            f"• ExtraTreesRegressor\n"
            f"• GradientBoostingRegressor\n"
            f"• RandomForestRegressor"
        )

# --- ABA 3: RODAR MODELO ---
with aba3:
    if df_test is None:
        st.error("Dataset nao encontrado. Verifique se o arquivo 'data/test.csv' existe.")
    else:
        st.markdown("### Pronto para executar o pipeline?")
        st.write("Clique no botao abaixo para processar os dados configurados e gerar os resultados de inferencia.")
        
        if st.button("Rodar Pipeline do Modelo", use_container_width=True, type="primary"):
            with st.spinner("Executando inferencias..."):
                resultado, r2 = executar_modelo(percentual)
                
                if resultado is not None:
                    st.session_state["resultado"] = resultado
                    st.session_state["r2"] = r2
                    st.success(f"Modelo executado com sucesso! Previsoes geradas para {len(resultado)} registros. Prossiga para a aba de Resultados.")
                else:
                    st.error("Erro na execucao do modelo.")

# --- ABA 4: RESULTADOS ---
with aba4:
    if "resultado" not in st.session_state:
        st.warning("Nenhum resultado disponivel. Execute o pipeline na aba 'Rodar Modelo' primeiro.")
    else:
        resultado = st.session_state["resultado"]
        r2 = st.session_state["r2"]
        
        # Sub-abas Principais de Resultados (Sem emojis)
        sub_aba4_1, sub_aba4_2, sub_aba4_3 = st.tabs([
            "Metricas e Dados Gerais", 
            "Analise Grafica", 
            "Extremos (Melhores e Piores)"
        ])
        
        with sub_aba4_1:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("R2 Score", f"{r2:.4f}")
            with col2:
                erro_medio = resultado["erro_abs"].mean()
                st.metric("Erro Absoluto Medio", f"{erro_medio:.2f}")
                
            st.markdown("#### Tabela Completa (Real vs Previsto)")
            # Modificação: adicionada coluna de erro absoluto
            st.dataframe(resultado[["valor_real", "valor_previsto", "erro_abs"]], use_container_width=True)
            
        with sub_aba4_2:
            # Sub-abas internas para os Graficos
            aba_grafico_1, aba_grafico_2 = st.tabs([
                "Dispersao (Real vs Previsto)", 
                "Analise de Casos Extremos"
            ])
            
            with aba_grafico_1:
                # Altura reduzida de 5 para 4.2 para evitar cortes na tela
                fig, ax = plt.subplots(figsize=(9, 4.2))
                ax.scatter(resultado["valor_real"], resultado["valor_previsto"], alpha=0.6)
                
                minimo = min(resultado["valor_real"].min(), resultado["valor_previsto"].min())
                maximo = max(resultado["valor_real"].max(), resultado["valor_previsto"].max())
                
                ax.plot([minimo, maximo], [minimo, maximo], 'r--', alpha=0.5, label="Previsao Perfeita")
                ax.set_xlabel("Valor Real", fontsize=11)
                ax.set_ylabel("Valor Previsto", fontsize=11)
                ax.set_title("Comparacao Geral: Valor Real vs Valor Previsto", fontsize=12)
                ax.legend()
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                
            with aba_grafico_2:
                idx_melhor = resultado["erro_abs"].idxmin()
                idx_pior = resultado["erro_abs"].idxmax()
                
                # Altura reduzida de 5.5 para 4.2 e largura ajustada
                fig2, axes = plt.subplots(1, 2, figsize=(11, 4.2))
                fig2.suptitle('Analise de Exemplos — Conjunto de Teste', fontsize=12, fontweight='bold')

                for ax, idx, titulo, cor in [
                    (axes[0], idx_melhor, 'Exemplo 1 — Melhor Previsao', '#2ecc71'),
                    (axes[1], idx_pior,   'Exemplo 2 — Maior Erro',      '#e74c3c')
                ]:
                    real = resultado.loc[idx, "valor_real"]
                    prev = resultado.loc[idx, "valor_previsto"]

                    bars = ax.bar(['Real', 'Previsto'], [real, prev],
                                  color=['#2c3e50', cor], edgecolor='white', linewidth=1.5, width=0.4)
                    ax.set_title(titulo, fontweight='bold', fontsize=10)
                    ax.set_ylabel('freight_value (R$)')
                    ax.set_ylim(0, max(real, prev) * 1.3)

                    for bar, val in zip(bars, [real, prev]):
                        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                                f'R$ {val:.2f}', ha='center', fontweight='bold', fontsize=9)

                    erro = abs(real - prev)
                    porcentagem_erro = (erro / real * 100) if real != 0 else 0.0
                    ax.annotate(f'Erro: R$ {erro:.2f}\n({porcentagem_erro:.1f}%)',
                                xy=(0.5, 0.82), xycoords='axes fraction', ha='center', fontsize=9,
                                bbox=dict(boxstyle='round,pad=0.3', facecolor=cor, alpha=0.3))

                plt.tight_layout()
                st.pyplot(fig2)
                
        with sub_aba4_3:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Top 10 Melhores Previsoes")
                melhores = resultado.nsmallest(10, "erro_abs")
                # Modificação: adicionada coluna de erro absoluto
                st.dataframe(melhores[["valor_real", "valor_previsto", "erro_abs"]], use_container_width=True)
            
            with col2:
                st.markdown("#### Top 10 Maiores Erros")
                maiores_erros = resultado.nlargest(10, "erro_abs")
                # Modificação: adicionada coluna de erro absoluto
                st.dataframe(maiores_erros[["valor_real", "valor_previsto", "erro_abs"]], use_container_width=True)