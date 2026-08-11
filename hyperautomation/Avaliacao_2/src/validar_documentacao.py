#!/usr/bin/env python3
import argparse
import os
import re
import shutil
from pathlib import Path

import pdfplumber


REQUIRED_DOCUMENTS = [
    "Ficha_Cadastro_{cpf}.pdf",
    "Documento_Foto_{cpf}.pdf",
    "Comprovante_Residencia_{cpf}.pdf",
]


def load_dotenv(dotenv_path: str = ".env") -> None:
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


def _to_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _is_valid_cpf(cpf: str) -> bool:
    cpf = _to_digits(cpf)
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False

    def calc_digit(digits: str, multiplier: int) -> int:
        total = sum(int(digit) * weight for digit, weight in zip(digits, range(multiplier, 1, -1)))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    d1 = calc_digit(cpf[:9], 10)
    d2 = calc_digit(cpf[:9] + str(d1), 11)
    return cpf[-2:] == f"{d1}{d2}"


def _extract_cpf_from_pdf(pdf_path: str | os.PathLike[str]) -> str | None:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            text_parts = []
            for page in pdf.pages:
                extracted = page.extract_text() or ""
                text_parts.append(extracted)
            content = "\n".join(text_parts)
    except Exception:
        return None

    if not content:
        return None

    # Captura o valor numérico (com ou sem pontuação) logo após a palavra CPF, 
    # seja na mesma linha (ex: CPF: 09090909) ou na linha de baixo.
    pattern = r"(?i)\bCPF\b\s*[:\-]?\s*\n?\s*([\d\.\-]+)"
    match = re.search(pattern, content)
    
    if match:
        raw_cpf = match.group(1)
        digits = _to_digits(raw_cpf)
        if digits:
            return digits

    return None


def _required_document_names(cpf: str) -> list[str]:
    return [template.format(cpf=cpf) for template in REQUIRED_DOCUMENTS]


def validar_documentos_cpf(cpf_dir: str | os.PathLike[str]) -> tuple[bool, str | None]:
    cpf_dir = Path(cpf_dir)
    cpf = cpf_dir.name
    if not cpf_dir.is_dir():
        return False, f"Diretório inexistente: {cpf_dir}"

    required = set(_required_document_names(cpf))
    files = {p.name for p in cpf_dir.iterdir() if p.is_file()}
    missing = sorted(required - files)
    if missing:
        return False, f"Arquivos faltando para CPF {cpf}: {', '.join(missing)}"

    for filename in sorted(required):
        file_path = cpf_dir / filename
        if not file_path.is_file():
            return False, f"Arquivo ausente: {file_path}"

        try:
            with pdfplumber.open(str(file_path)) as pdf:
                if len(pdf.pages) == 0:
                    return False, f"Arquivo PDF sem páginas: {file_path}"
        except Exception as exc:
            return False, f"Arquivo corrompido ou inválido: {file_path} ({exc})"

    ficha_path = cpf_dir / f"Ficha_Cadastro_{cpf}.pdf"
    extracted_cpf = _extract_cpf_from_pdf(ficha_path)
    if not extracted_cpf:
        return False, f"CPF não encontrado na ficha do CPF {cpf}"

    if extracted_cpf != cpf:
        return False, f"CPF da ficha ({extracted_cpf}) não bate com o diretório ({cpf})"

    if not _is_valid_cpf(extracted_cpf):
        return False, f"CPF da ficha inválido: {extracted_cpf}"

    return True, None


def processar_documentos_salvos(output_dir: str | os.PathLike[str], docs_ok_dir: str | os.PathLike[str]) -> dict:
    output_dir = Path(output_dir)
    docs_ok_dir = Path(docs_ok_dir)

    if not output_dir.exists():
        return {"movidos": [], "nao_movidos": []}

    os.makedirs(docs_ok_dir, exist_ok=True)

    movidos: list[str] = []
    nao_movidos: list[str] = []

    for item in sorted(output_dir.iterdir(), key=lambda x: x.name):
        if not item.is_dir():
            continue

        ok, reason = validar_documentos_cpf(item)
        if ok:
            target_dir = docs_ok_dir / item.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(item), str(target_dir))
            movidos.append(item.name)
            print(f"[OK] Documento do CPF {item.name} movido para {target_dir}")
        else:
            nao_movidos.append(item.name)
            print(f"[NÃO MOVIDO] CPF {item.name}: {reason}")

    return {"movidos": movidos, "nao_movidos": nao_movidos}


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Valida documentos salvos em EMAIL_OUTPUT_DIR e move os válidos para DOCS_OK_DIR.")
    parser.add_argument("--output-dir", default=None, help="Diretório com as pastas por CPF. Se não informado, usa EMAIL_OUTPUT_DIR.")
    parser.add_argument("--docs-ok-dir", default=None, help="Diretório de destino para arquivos válidos. Se não informado, usa DOCS_OK_DIR.")
    args = parser.parse_args()

    output_dir = args.output_dir or os.getenv("EMAIL_OUTPUT_DIR", "downloads")
    docs_ok_dir = args.docs_ok_dir or os.getenv("DOCS_OK_DIR", "docs_ok")

    result = processar_documentos_salvos(output_dir, docs_ok_dir)
    print(f"Movidos: {result['movidos']}")
    print(f"Não movidos: {result['nao_movidos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
