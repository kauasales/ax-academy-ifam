#!/usr/bin/env python3
import os
import getpass
import datetime
import importlib.util
import sys

BUSCA_PATH = os.path.join(os.path.dirname(__file__), "busca_solicitação.py")
spec = importlib.util.spec_from_file_location("busca_solicitação", BUSCA_PATH)
busca = importlib.util.module_from_spec(spec)
# Ensure the src directory is on sys.path so sibling modules can be imported normally
sys.path.insert(0, os.path.dirname(__file__))
spec.loader.exec_module(busca)


# Monta o dicionário de configuração SMTP usado para envio de e-mails.
def build_smtp_config(username: str, password: str) -> dict:
    return {
        "host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
        "username": username,
        "password": password,
        "use_tls": os.getenv("EMAIL_SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"},
    }


# Função principal (controlador): carrega config, conecta IMAP e delega processamento a `busca_solicitação`.
def main() -> int:
    busca.load_dotenv()
    args = busca.parse_args()
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

    smtp_config = build_smtp_config(username, password)

    no_ssl = args.no_ssl or os.getenv("EMAIL_NO_SSL", "false").lower() in {"1", "true", "yes", "on"}
    use_ssl = not no_ssl

    try:
        imap = busca.connect_imap(host, username, password, use_ssl=use_ssl, port=port)
    except Exception as error:
        print(f"Erro ao conectar ao servidor IMAP: {error}")
        return 1

    try:
        today = datetime.date.today()
        message_ids = busca.search_unseen_messages(imap, mailbox, subject_phrase="Cadastro Portal Fake -", since_date=today)
        if not message_ids:
            print("Nenhuma mensagem encontrada.")
        else:
            busca.process_messages(imap, message_ids, output_dir, smtp_config, mailbox)
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
