#!/usr/bin/env python3
import argparse
import datetime
import email
import getpass
import imaplib
import os
import re
import sys
from email.header import decode_header, make_header

SUBJECT_PATTERN = re.compile(r"Cadastro Portal Fake -\s*(\d{11})", re.IGNORECASE)


# Retorna True se a mensagem foi recebida na data atual.
def email_is_today(msg: email.message.Message) -> bool:
    date_header = msg.get("Date")
    if not date_header:
        return False

    try:
        msg_dt = email.utils.parsedate_to_datetime(date_header)
    except Exception:
        return False

    if msg_dt is None:
        return False

    if msg_dt.tzinfo is not None:
        msg_dt = msg_dt.astimezone().date()
    else:
        msg_dt = msg_dt.date()

    return msg_dt == datetime.date.today()


# Carrega variáveis de ambiente a partir de um arquivo .env, se existir.
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


# Decodifica strings MIME do cabeçalho para texto legível.
def decode_mime_words(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


# Conecta ao servidor IMAP e faz login com as credenciais fornecidas.
def connect_imap(host: str, username: str, password: str, use_ssl: bool = True, port: int | None = None) -> imaplib.IMAP4:
    if use_ssl:
        imap = imaplib.IMAP4_SSL(host, port or 993)
    else:
        imap = imaplib.IMAP4(host, port or 143)
    imap.login(username, password)
    return imap


# Busca IDs de mensagens não vistas, opcionalmente filtrando por assunto e data.
def search_unseen_messages(imap: imaplib.IMAP4, mailbox: str = "INBOX", subject_phrase: str | None = None, since_date: datetime.date | None = None) -> list[str]:
    status, _ = imap.select(mailbox)
    if status != "OK":
        raise RuntimeError(f"Não foi possível selecionar a caixa '{mailbox}'")

    search_terms = ["UNSEEN"]
    if subject_phrase:
        search_terms.extend(["SUBJECT", f'"{subject_phrase}"'])
    if since_date:
        search_terms.extend(["SINCE", since_date.strftime("%d-%b-%Y")])

    status, data = imap.search(None, *search_terms)
    if status != "OK":
        raise RuntimeError("Falha ao buscar mensagens não vistas")

    message_ids = data[0].split()
    return [mid.decode("utf-8") for mid in message_ids]


# Baixa anexos da mensagem para uma pasta específica baseada no CPF.
def download_attachments(msg: email.message.Message, output_dir: str, cpf: str) -> list[str]:
    saved_files = []
    cpf_dir = os.path.join(output_dir, cpf)
    os.makedirs(cpf_dir, exist_ok=True)

    for part in msg.walk():
        content_disposition = part.get("Content-Disposition", "")
        if not content_disposition:
            continue

        dispositions = content_disposition.strip().split(";")
        if dispositions[0].lower() not in {"attachment", "inline"}:
            continue

        filename = part.get_filename()
        if not filename:
            continue

        filename = decode_mime_words(filename)
        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        file_path = os.path.join(cpf_dir, filename)
        with open(file_path, "wb") as f:
            f.write(payload)

        saved_files.append(file_path)

    return saved_files


# Processa as mensagens encontradas, filtra por data e assunto, e salva anexos.
def process_messages(imap: imaplib.IMAP4, message_ids: list[str], output_dir: str, mailbox: str = "INBOX") -> None:
    if not message_ids:
        print("Nenhuma mensagem não vista encontrada.")
        return

    for msg_id in message_ids:
        status, data = imap.fetch(msg_id, "RFC822")
        if status != "OK" or not data or data[0] is None:
            print(f"Falha ao buscar mensagem {msg_id}")
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        if not email_is_today(msg):
            print(f"Ignorando mensagem {msg_id} porque não é do dia corrente.")
            continue

        subject = decode_mime_words(msg.get("Subject", ""))
        match = SUBJECT_PATTERN.search(subject)

        if not match:
            print(f"Ignorando mensagem {msg_id} com assunto '{subject}'")
            continue

        cpf = match.group(1)
        print(f"Processando mensagem {msg_id} - CPF: {cpf} - Assunto: {subject}")

        saved_files = download_attachments(msg, output_dir, cpf)
        if saved_files:
            for file_path in saved_files:
                print(f"  Anexo salvo: {file_path}")
        else:
            print("  Nenhum anexo encontrado nesta mensagem.")

        imap.store(msg_id, "+FLAGS", "\\Seen")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Busca solicitações não vistas no e-mail e baixa anexos de mensagens com assunto 'Cadastro Portal Fake - {CPF}'."
    )
    parser.add_argument("--host", help="Servidor IMAP, por exemplo imap.gmail.com. Se não passado, usa EMAIL_HOST.")
    parser.add_argument("--user", help="Usuário de e-mail. Se não fornecido, usa EMAIL_USER ou solicitará interativo.")
    parser.add_argument("--password", help="Senha do e-mail. Se não fornecida, usa EMAIL_PASSWORD ou solicitará interativo.")
    parser.add_argument("--mailbox", default=None, help="Caixa de entrada IMAP a ser verificada. Se não passado, usa EMAIL_MAILBOX ou INBOX.")
    parser.add_argument("--output-dir", default=None, help="Pasta onde os anexos serão salvos. Se não passada, usa EMAIL_OUTPUT_DIR ou downloads.")
    parser.add_argument("--no-ssl", action="store_true", help="Não usar SSL para conexão IMAP")
    parser.add_argument("--port", type=int, default=None, help="Porta IMAP opcional. Se não passada, usa EMAIL_PORT ou padrão.")
    return parser.parse_args()


# Lê configurações, conecta ao IMAP, busca mensagens e processa anexos.
def main() -> int:
    load_dotenv()
    args = parse_args()
    output_dir = args.output_dir or os.getenv("EMAIL_OUTPUT_DIR", "downloads")
    os.makedirs(output_dir, exist_ok=True)

    host = args.host or os.getenv("EMAIL_HOST")
    mailbox = args.mailbox or os.getenv("EMAIL_MAILBOX", "INBOX")
    username = args.user or os.getenv("EMAIL_USER")
    password = args.password or os.getenv("EMAIL_PASSWORD")
    port = args.port

    if not port:
        env_port = os.getenv("EMAIL_PORT")
        if env_port and env_port.isdigit():
            port = int(env_port)

    if not username:
        username = input("Usuário de e-mail: ").strip()
    if not password:
        password = getpass.getpass("Senha do e-mail: ")

    if not host:
        print("Servidor IMAP é obrigatório. Defina --host ou EMAIL_HOST no .env.")
        return 1
    if not username or not password:
        print("Usuário e senha são obrigatórios para autenticar no servidor IMAP.")
        return 1

    no_ssl = args.no_ssl or os.getenv("EMAIL_NO_SSL", "false").lower() in {"1", "true", "yes", "on"}
    use_ssl = not no_ssl

    try:
        imap = connect_imap(host, username, password, use_ssl=use_ssl, port=port)
    except Exception as error:
        print(f"Erro ao conectar ao servidor IMAP: {error}")
        return 1

    try:
        today = datetime.date.today()
        message_ids = search_unseen_messages(imap, mailbox, subject_phrase="Cadastro Portal Fake -", since_date=today)
        process_messages(imap, message_ids, output_dir, mailbox)
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
