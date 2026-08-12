#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
import pdfplumber


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Carrega as variáveis de ambiente do arquivo .env se existir."""
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, encoding="utf-8") as dotenv_file:
        for line in dotenv_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def extrair_texto_por_colunas(pdf_path: Path) -> str:
    """
    Extrai as palavras do PDF agrupando-as por colunas (esquerda e direita)
    e ordenando verticalmente para manter a sequência rótulo -> valor de cada lado.
    """
    linhas_finais = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue

                x_mid = page.width * 0.48  # Ponto divisor aproximado das colunas

                words_left = [w for w in words if w["x0"] < x_mid]
                words_right = [w for w in words if w["x0"] >= x_mid]

                def agrupar_por_linhas(lista_palavras):
                    if not lista_palavras:
                        return []
                    lista_ordenada = sorted(lista_palavras, key=lambda w: (round(w["top"] / 4) * 4, w["x0"]))
                    linhas = []
                    linha_atual = []
                    last_top = None

                    for word in lista_ordenada:
                        rounded_top = round(word["top"] / 4) * 4
                        if last_top is None or rounded_top == last_top:
                            linha_atual.append(word["text"])
                        else:
                            linhas.append(" ".join(linha_atual))
                            linha_atual = [word["text"]]
                        last_top = rounded_top

                    if linha_atual:
                        linhas.append(" ".join(linha_atual))
                    return linhas

                linhas_finais.extend(agrupar_por_linhas(words_left))
                linhas_finais.extend(agrupar_por_linhas(words_right))

        return "\n".join(linhas_finais)
    except Exception as e:
        print(f"Erro ao ler o arquivo PDF {pdf_path}: {e}")
        return ""


def parse_ficha_cadastro(texto: str) -> dict:
    """
    Mapeia os campos da ficha de cadastro filtrando rótulos, subtextos e instruções.
    """
    padroes_ignorar = [
        r"^FICHA DE CADASTRO$",
        r"Por favor, preencha todos os campos",
    ]

    campos_mapeamento = [
        ("nome_completo", r"NOME COMPLETO"),
        ("cpf", r"CPF"),
        ("data_nascimento", r"DATA DE NASCIMENTO"),
        ("endereco_completo", r"ENDEREÇO COMPLETO"),
        ("email", r"E-MAIL"),
        ("telefone_whatsapp", r"TELEFONE\s*/?\s*WHATSAPP"),
    ]

    linhas_processadas = []
    for raw_line in texto.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = re.sub(r"\s*\(\s*DD/MM/AAAA\s*\)", "", line, flags=re.IGNORECASE).strip()

        if any(re.search(p, line, re.IGNORECASE) for p in padroes_ignorar):
            continue

        linhas_processadas.append(line)

    dados = {}

    for chave, label_pattern in campos_mapeamento:
        valor_encontrado = None

        for i, line in enumerate(linhas_processadas):
            if re.search(rf"\b{label_pattern}\b", line, re.IGNORECASE):
                resto = re.sub(rf".*?\b{label_pattern}\b\s*[:\-]?\s*", "", line, flags=re.IGNORECASE).strip()
                
                is_another_label = any(
                    re.search(rf"\b{p}\b", resto, re.IGNORECASE) for _, p in campos_mapeamento
                )
                if resto and not is_another_label:
                    valor_encontrado = resto
                    break

                if i + 1 < len(linhas_processadas):
                    next_line = linhas_processadas[i + 1].strip()
                    is_next_another_label = any(
                        re.search(rf"\b{p}\b", next_line, re.IGNORECASE) for _, p in campos_mapeamento
                    )
                    if not is_next_another_label:
                        valor_encontrado = next_line
                        break

        dados[chave] = valor_encontrado

    return dados


def processar_diretorio_docs(docs_ok_dir: str, json_data_dir: str) -> None:
    """Percorre as pastas de CPF, agrupa os dados de todos em uma lista e salva num único arquivo data.json."""
    docs_path = Path(docs_ok_dir)
    json_path = Path(json_data_dir)

    if not docs_path.exists():
        print(f"Diretório de origem inexistente: {docs_path.resolve()}")
        return

    json_path.mkdir(parents=True, exist_ok=True)
    lista_cadastros = []

    for pasta_cpf in sorted(docs_path.iterdir(), key=lambda x: x.name):
        if not pasta_cpf.is_dir():
            continue

        cpf_pasta = pasta_cpf.name
        pdf_ficha = pasta_cpf / f"Ficha_Cadastro_{cpf_pasta}.pdf"

        if not pdf_ficha.is_file():
            fichas = list(pasta_cpf.glob("Ficha_Cadastro_*.pdf"))
            if fichas:
                pdf_ficha = fichas[0]
            else:
                print(f"[AVISO] Ficha de cadastro não encontrada na pasta: {pasta_cpf.name}")
                continue

        texto_pdf = extrair_texto_por_colunas(pdf_ficha)
        if not texto_pdf:
            print(f"[AVISO] Não foi possível extrair texto do arquivo: {pdf_ficha.name}")
            continue

        dados_extraidos = parse_ficha_cadastro(texto_pdf)
        lista_cadastros.append(dados_extraidos)
        print(f"[OK] Dados extraídos do CPF {cpf_pasta}")

    # Salva a lista completa de cadastros no arquivo data.json
    arquivo_json_unico = json_path / "data.json"
    with open(arquivo_json_unico, "w", encoding="utf-8") as f:
        json.dump(lista_cadastros, f, ensure_ascii=False, indent=4)

    print(f"\nProcessamento concluído. {len(lista_cadastros)} registros salvos em {arquivo_json_unico}")


def main() -> int:
    load_dotenv()

    docs_ok_dir = os.getenv("DOCS_OK_DIR", "docs_ok")
    json_data_dir = os.getenv("JSON_DATA_DIR", "json_data")

    print(f"Lendo pastas de: {docs_ok_dir}")
    print(f"Gerando arquivo: {Path(json_data_dir) / 'data.json'}\n")

    processar_diretorio_docs(docs_ok_dir, json_data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())