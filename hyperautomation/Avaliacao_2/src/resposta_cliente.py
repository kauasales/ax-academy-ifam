#!/usr/bin/env python3
import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Iterable


REQUIRED_DOC_TEMPLATES = [
    "Ficha_Cadastro_{cpf}.pdf",
    "Documento_Foto_{cpf}.pdf",
    "Comprovante_Residencia_{cpf}.pdf",
]


# Retorna a lista de nomes de arquivos obrigatórios para um `cpf`.
def required_document_names(cpf: str) -> list[str]:
    return [template.format(cpf=cpf) for template in REQUIRED_DOC_TEMPLATES]


# Extrai os nomes de anexos presentes na mensagem (sem baixar), retornando lista de nomes.
def extract_attachment_names(msg) -> list[str]:
    attachments = []
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

        filename = os.path.basename(filename)
        attachments.append(filename)

    return attachments


# Compara os anexos da mensagem com os nomes obrigatórios e retorna os faltantes.
def find_missing_documents(msg, cpf: str) -> list[str]:
    present = set(extract_attachment_names(msg))
    required = set(required_document_names(cpf))
    missing = sorted(required - present)
    return missing


# Monta o corpo da mensagem a ser enviada quando faltarem documentos.
def build_incomplete_message(missing_documents: Iterable[str]) -> str:
    missing_list = ", ".join(missing_documents)
    return (
        "Documentação incompleta, favor reenviar os documentos já enviados e o(s) documento(s) faltante(s).\n\n"
        f"Documentos(s) faltante(s): {missing_list}"
    )


# Nova função para mensagens de erro genéricas
def build_validation_error_message(reason: str) -> str:
    return (
        "Houve um problema na validação da sua documentação.\n\n"
        f"Motivo: {reason}\n\n"
        "Por favor, verifique o(s) arquivo(s) mencionado(s) acima e reenvie todos os documentos necessários."
    )


# Gera um `EmailMessage` de resposta informando os documentos faltantes.
def create_reply_message(original_msg, from_address: str, to_address: str, missing_documents: Iterable[str]) -> EmailMessage:
    subject = original_msg.get("Subject", "")
    if subject and subject.lower().startswith("re:"):
        reply_subject = subject
    else:
        reply_subject = f"Re: {subject}" if subject else "Documentação incompleta"

    body = build_incomplete_message(missing_documents)
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = reply_subject
    message.set_content(body)

    message_id = original_msg.get("Message-ID")
    if message_id:
        message["In-Reply-To"] = message_id
        message["References"] = message_id

    return message


# Gera um `EmailMessage` de resposta informando um erro genérico na validação.
def create_notification_message(from_address: str, to_address: str, subject: str, body: str, in_reply_to: str = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to

    return message


# Determina o destinatário da resposta usando `Reply-To` ou `From` da mensagem original.
def get_reply_recipient(original_msg) -> str | None:
    reply_to = original_msg.get("Reply-To")
    if reply_to:
        _, address = parseaddr(reply_to)
        if address:
            return address

    from_header = original_msg.get("From", "")
    _, address = parseaddr(from_header)
    return address or None


# Envia uma mensagem via SMTP usando as credenciais fornecidas.
def send_email_message(smtp_host: str, smtp_port: int, username: str, password: str, message: EmailMessage, use_tls: bool = True) -> None:
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)

