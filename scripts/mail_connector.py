#!/usr/bin/env python3
"""Multi-comptes Gmail lecture seule, IMAP TLS et SMTP avec validation."""
import argparse
import base64
import email
import getpass
import imaplib
import json
import os
import re
import smtplib
import ssl
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from email.utils import getaddresses
from pathlib import Path
import keyring

CFG = Path.home() / '.config/jarvis-parlement/accounts.json'
SERVICE = 'jarvis-parlement'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def load():
    return json.loads(CFG.read_text()) if CFG.exists() else {}

def save(accounts):
    CFG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(CFG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(accounts, f, indent=2)
    CFG.chmod(0o600)

def secret(account, kind):
    value = keyring.get_password(SERVICE, account + ':' + kind)
    if value is None:
        raise ValueError('Secret absent : relancer add ou gmail-auth.')
    return value

def body(msg):
    part = msg.get_body(preferencelist=('plain',))
    return part.get_content()[:20000] if part else '[Sans texte brut]'

def gmail_client(account):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    c = Credentials.from_authorized_user_info(
        json.loads(secret(account, 'oauth')), SCOPES)
    if not c.valid:
        if not c.refresh_token:
            raise ValueError('Reconnexion Google requise.')
        c.refresh(Request())
        keyring.set_password(SERVICE, account + ':oauth', c.to_json())
    return build('gmail', 'v1', credentials=c, cache_discovery=False)

def read_mail(account, cfg, limit):
    if cfg['type'] == 'gmail':
        svc = gmail_client(account)
        rows = svc.users().messages().list(
            userId='me', maxResults=limit).execute().get('messages', [])
        for row in rows:
            raw = svc.users().messages().get(
                userId='me', id=row['id'], format='raw').execute()['raw']
            msg = BytesParser(policy=policy.default).parsebytes(
                base64.urlsafe_b64decode(raw))
            print(json.dumps({'account': account, 'id': row['id'],
                'from': str(msg['From']), 'subject': str(msg['Subject']),
                'date': str(msg['Date']), 'body': body(msg)}, ensure_ascii=False))
    else:
        with imaplib.IMAP4_SSL(cfg['imap_host'], cfg['imap_port'],
                ssl_context=ssl.create_default_context(), timeout=30) as m:
            m.login(cfg['imap_user'], secret(account, 'imap'))
            status, _ = m.select('INBOX', readonly=True)
            if status != 'OK':
                raise ValueError('INBOX inaccessible.')
            status, ids = m.uid('search', None, 'ALL')
            if status != 'OK':
                raise ValueError('Recherche IMAP impossible.')
            for uid in ids[0].split()[-limit:]:
                status, data = m.uid('fetch', uid, '(BODY.PEEK[])')
                if status != 'OK':
                    raise ValueError('Lecture IMAP impossible.')
                raw = next(x[1] for x in data if isinstance(x, tuple))
                msg = BytesParser(policy=policy.default).parsebytes(raw)
                print(json.dumps({'account': account, 'uid': uid.decode(),
                    'from': str(msg['From']), 'subject': str(msg['Subject']),
                    'date': str(msg['Date']), 'body': body(msg)}, ensure_ascii=False))

def send_mail(account, cfg, filename):
    if cfg['type'] != 'imap':
        raise ValueError('Ce module Gmail est en lecture seule.')
    # Lire une seule fois : le contenu approuvé est celui transmis.
    raw = Path(filename).read_bytes()
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    if msg.is_multipart() or msg.get_content_type() != 'text/plain':
        raise ValueError('V1 : e-mail texte brut sans pièce jointe uniquement.')
    if any(msg.get_all(h) for h in ('Bcc', 'Resent-To', 'Resent-Cc', 'Resent-Bcc')):
        raise ValueError('Bcc et Resent non pris en charge.')
    senders = getaddresses(msg.get_all('From', []))
    if len(senders) != 1 or senders[0][1].lower() != cfg['address'].lower():
        raise ValueError('From différent du compte sélectionné.')
    dest = [v for _, v in getaddresses(
        msg.get_all('To', []) + msg.get_all('Cc', []))]
    if not dest or any(not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', v) for v in dest):
        raise ValueError('Destinataires invalides.')
    if msg.get_all('Sender') or msg.get_all('Return-Path'):
        raise ValueError('En-têtes Sender/Return-Path non pris en charge.')
    if any(len(msg.get_all(h, [])) > 1 for h in ('From', 'To', 'Cc', 'Subject')):
        raise ValueError('En-têtes dupliqués non pris en charge.')
    wire = EmailMessage(policy=policy.SMTP)
    for h in ('From', 'To', 'Cc', 'Subject', 'Reply-To', 'In-Reply-To', 'References'):
        if msg[h] is not None:
            wire[h] = str(msg[h])
    wire['Date'] = formatdate(localtime=True)
    wire['Message-ID'] = make_msgid()
    wire.set_content(msg.get_content(), charset='utf-8', cte='quoted-printable')
    raw = wire.as_bytes()
    print('COMPTE :', account, '\nENVELOPPE :', ', '.join(dest))
    print(wire.as_string())
    if input('\nTaper ENVOYER pour valider ce message : ') != 'ENVOYER':
        print('Annulé.'); return
    ctx = ssl.create_default_context()
    if cfg['smtp_port'] == 465:
        smtp = smtplib.SMTP_SSL(cfg['smtp_host'], 465, context=ctx, timeout=30)
    else:
        smtp = smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=30)
        smtp.ehlo(); smtp.starttls(context=ctx); smtp.ehlo()
    with smtp:
        smtp.login(cfg['smtp_user'], secret(account, 'smtp'))
        refused = smtp.sendmail(cfg['address'], dest, raw)
    print('Refus partiels :' if refused else 'Accepté par le serveur SMTP.', refused or '')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['add', 'gmail-auth', 'read', 'send'])
    p.add_argument('account')
    p.add_argument('--client', help='Fichier OAuth Desktop Google')
    p.add_argument('--file', help='Message .eml UTF-8')
    p.add_argument('--limit', type=int, default=5)
    a = p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', a.account):
        p.error('Identifiant : lettres, chiffres, _ et - uniquement.')
    accounts = load()
    if a.action == 'add':
        if a.account in accounts:
            p.error('Compte existant : choisir un autre identifiant.')
        c = {'type': 'imap', 'address': input('Adresse e-mail : ').strip()}
        for kind, default in [('imap', 993), ('smtp', 587)]:
            c[kind + '_host'] = input(kind.upper() + ' serveur : ').strip()
            port = int(input(f'Port [{default}] : ') or default)
            if (kind == 'imap' and port != 993) or (kind == 'smtp' and port not in (465, 587)):
                p.error('V1 : IMAP 993 ; SMTP 465 ou 587.')
            c[kind + '_port'] = port
            c[kind + '_user'] = input('Identifiant : ').strip() or c['address']
            keyring.set_password(SERVICE, a.account + ':' + kind,
                getpass.getpass('Mot de passe applicatif : '))
        accounts[a.account] = c; save(accounts)
    elif a.action == 'gmail-auth':
        if not a.client:
            p.error('--client requis.')
        if a.account in accounts and accounts[a.account]['type'] != 'gmail':
            p.error('Cet identifiant appartient à un compte IMAP.')
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        flow = InstalledAppFlow.from_client_secrets_file(a.client, SCOPES)
        c = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        svc = build('gmail', 'v1', credentials=c, cache_discovery=False)
        address = svc.users().getProfile(userId='me').execute()['emailAddress']
        keyring.set_password(SERVICE, a.account + ':oauth', c.to_json())
        accounts[a.account] = {'type': 'gmail', 'address': address}; save(accounts)
        print('Connecté :', address)
    else:
        if a.account not in accounts:
            p.error('Compte inconnu.')
        if a.action == 'read':
            if not 1 <= a.limit <= 50:
                p.error('--limit entre 1 et 50.')
            read_mail(a.account, accounts[a.account], a.limit)
        else:
            if not a.file:
                p.error('--file requis.')
            send_mail(a.account, accounts[a.account], a.file)

if __name__ == '__main__':
    main()
