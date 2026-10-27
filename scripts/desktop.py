#!/usr/bin/env python3
"""Fenêtre native WebKit, sans serveur applicatif accessible sur le réseau."""
import fcntl
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from common import CONFIG, HOME, REPORTS, ROOT, SERVICE, WORK, initialize, read_json, settings
import services
import providers
from assistant import Assistant
from voice import Voice
import updater


def safe_url(value):
    url = urlsplit(str(value))
    if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
        raise ValueError('Lien web invalide.')
    return str(value)


def mail_preview(data):
    from email.message import EmailMessage
    from email.utils import getaddresses, formatdate, make_msgid
    import re
    account = services.accounts().get(data.get('account'))
    if not account or account['type'] != 'imap':
        raise ValueError('L’envoi nécessite un compte SMTP. Gmail OAuth est en lecture seule.')
    if data.get('file'):
        from email import policy
        from email.parser import BytesParser
        raw=services.decode_file(data['file'])
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        if msg.defects: raise ValueError('Le fichier .eml est mal formé.')
        if any(msg.get_all(h) for h in ['Bcc','Sender','Return-Path']) or any(h.lower().startswith('resent-') for h in msg.keys()):
            raise ValueError('En-têtes Bcc, Resent, Sender ou Return-Path non pris en charge. Nettoie le fichier avant envoi.')
        if any(len(msg.get_all(h,[]))>1 for h in ['From','To','Cc','Subject']): raise ValueError('En-têtes dupliqués.')
        senders=getaddresses(msg.get_all('From',[]))
        if len(senders)!=1 or senders[0][1].lower()!=account['address'].lower(): raise ValueError('L’expéditeur du .eml doit correspondre au compte SMTP sélectionné.')
        recipients=[a for _,a in getaddresses(msg.get_all('To',[])+msg.get_all('Cc',[]))]
        if not recipients or any(not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',a) for a in recipients): raise ValueError('Destinataires .eml invalides.')
        part=msg.get_body(preferencelist=('plain',))
        body=part.get_content() if part else '[Pas de version texte. Ouvre le .eml dans Mail avant de valider.]'
        attachments=[p.get_filename() or 'Pièce jointe sans nom' for p in msg.iter_attachments()]
        fields={'to':str(msg.get('To','')),'cc':str(msg.get('Cc','')),'subject':str(msg.get('Subject','')),
            'body':str(body)[:50000]+('\n\nPièces jointes : '+', '.join(attachments) if attachments else '')}
        return account.copy(),recipients,raw,fields
    fields = {k: str(data.get(k, '')).strip() for k in ['to','cc','subject','body']}
    if any('\r' in fields[k] or '\n' in fields[k] for k in ['to','cc','subject']):
        raise ValueError('En-tête invalide.')
    recipients = [addr for _, addr in getaddresses([fields['to'],fields['cc']])]
    if not fields['to'] or not recipients or any(not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', a) for a in recipients):
        raise ValueError('Destinataire invalide.')
    if not fields['subject'] or not fields['body'] or len(fields['body']) > 100000:
        raise ValueError('Objet et message requis ; message limité à 100 000 caractères.')
    msg = EmailMessage()
    msg['From'] = account['address']; msg['To'] = fields['to']
    if fields['cc']: msg['Cc'] = fields['cc']
    msg['Subject'] = fields['subject']; msg['Date'] = formatdate(localtime=True); msg['Message-ID'] = make_msgid()
    msg.set_content(fields['body'])
    return account.copy(), recipients, msg.as_bytes(), fields


def smtp_send(pending):
    import smtplib, ssl, keyring
    account, recipients, raw, fields, name = pending
    password = keyring.get_password(SERVICE, name + ':smtp')
    if not password: raise ValueError('Mot de passe SMTP absent.')
    context = ssl.create_default_context()
    connection = (smtplib.SMTP_SSL(account['smtp_host'], account['smtp_port'], context=context, timeout=30)
        if account['smtp_port'] == 465 else smtplib.SMTP(account['smtp_host'], account['smtp_port'], timeout=30))
    with connection as smtp:
        if account['smtp_port'] != 465: smtp.ehlo(); smtp.starttls(context=context); smtp.ehlo()
        smtp.login(account['smtp_user'], password)
        refused = smtp.sendmail(account['address'], recipients, raw)
    return {'text': 'Accepté par le serveur SMTP.' if not refused else 'Envoi partiel : certains destinataires ont été refusés. Vérifie avant de renvoyer.'}


class Api:
    def __init__(self):
        self._window = None
        self.assistant = Assistant()
        self.voice = Voice()
        self._speech = None
        self._pending = {}
        self._mutex = threading.RLock()

    def call(self, action, data=None):
        data = data or {}
        try:
            if not isinstance(data, dict): raise ValueError('Requête invalide.')
            result = self._dispatch(action, data)
            return {'ok': True, 'data': result}
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}
        except Exception as exc:
            # Never include provider responses, credentials, message bodies or callback URLs.
            return {'ok': False, 'error': 'Opération impossible (' + type(exc).__name__ + '). Vérifie les paramètres et le diagnostic.'}

    def _dispatch(self, action, data):
        if action == 'assistant': return self.assistant.turn(data)
        if action == 'assistant_reset': return self.assistant.reset()
        if action == 'assistant_confirm': return self.assistant.confirm(data)
        if action == 'voice_state': return self.voice.state()
        if action == 'voice_install': return self.voice.install()
        if action == 'voice_listen':
            with self._mutex: return self.voice.listen()
        if action == 'voice_stop':
            with self._mutex: return self.voice.stop()
        if action == 'update_check': return updater.check()
        if action == 'update_install': return updater.install()
        functions = {'chat': services.chat, 'briefing': services.briefing,
            'mail_summary': services.mail_summary, 'calendar': services.calendar_events,
            'google_connect': services.google_connect, 'imap_connect': services.imap_connect,
            'index_documents': services.index_documents, 'search_documents': services.search_documents,
            'diagnosis': services.diagnosis}
        if action in functions: return functions[action](data)
        if action in ('save_settings','api_key'):
            with self._mutex: return getattr(services, action)(data)
        if action.startswith('chatgpt_'):
            import chatgpt_auth
            handlers = {'chatgpt_connect': chatgpt_auth.connect, 'chatgpt_select': chatgpt_auth.select,
                'chatgpt_disconnect': chatgpt_auth.disconnect}
            if action in handlers: return handlers[action](data)
        if action.startswith('template_'):
            import templates
            handlers={'template_import':templates.import_template,'template_configure':templates.configure,
                'template_activate':templates.activate}
            if action in handlers:
                with self._mutex: return handlers[action](data)
            if action=='template_catalog': return templates.catalog()
            if action=='template_preview':
                result=services.save_result({'text':'Exemple de texte généré. Vérifie les marges, la police, les en-têtes et les pieds de page.\n\n1. Première question parlementaire.\n2. Deuxième question parlementaire.','template_id':data.get('id')},'Aperçu du modèle')
                return result
        if action == 'state':
            import chatgpt_auth
            import templates
            return {'settings': settings(), 'accounts': services.accounts(),
                'chatgpt': chatgpt_auth.status(), 'version':updater.VERSION, 'reports':self._reports(),
                'templates':templates.catalog(),
                'sources':read_json(ROOT/'config/sources.json',{})}
        if action == 'models': return {'models': providers.models(data.get('provider'))}
        if action == 'test_ai':
            result = providers.complete('Réponds uniquement : Jarvis est prêt.', settings(), system='Réponds en français.')
            if result.get('handoff'): raise ValueError('Le transfert manuel ne possède pas de connexion automatique à tester.')
            return result
        if action == 'unschedule':
            return services.save_settings({'schedule_enabled':False})
        if action == 'manual':
            return {'html':(ROOT/'ui/manual.html').read_text()}
        if action == 'pull_model':
            import re
            model = str(data.get('model','')).strip()
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,120}', model): raise ValueError('Nom de modèle invalide.')
            providers.ensure_ollama()
            providers.request_json('http://127.0.0.1:11434/api/pull', {'model':model,'stream':False}, timeout=7200)
            return {'text':'Modèle téléchargé. Recharge les modèles puis sélectionne-le.'}
        if action == 'mail_read': return {'messages':services.mail_read(data.get('account',''))}
        if action == 'mail_preview':
            account, recipients, raw, fields = mail_preview(data)
            nonce = uuid4().hex
            with self._mutex:
                self._pending.clear()
                self._pending[nonce] = (account,recipients,raw,fields,data['account'])
            return {'nonce':nonce,'from':account['address'],**fields}
        if action == 'mail_send':
            with self._mutex: pending = self._pending.pop(data.get('nonce'), None)
            if not pending: raise ValueError('Prévisualisation expirée. Recommence la vérification.')
            if not self._window or not self._window.create_confirmation_dialog('Confirmer l’envoi',
                    'Envoyer « '+pending[3]['subject']+' » à '+', '.join(pending[1])+' ?'):
                return {'text':'Envoi annulé.'}
            return smtp_send(pending)
        if action == 'reports': return {'reports': self._reports()}
        if action == 'report_read': return read_json(services.report_file(data['name']),{})
        if action == 'report_open':
            subprocess.run(['open',str(services.report_file(data['name']))],check=True)
            return {'text':'Document ouvert.'}
        if action == 'folder':
            subprocess.run(['open',str(WORK)],check=True); return {'text':'Dossier ouvert.'}
        if action == 'external_url':
            import webbrowser
            webbrowser.open(safe_url(data.get('url'))); return {}
        if action == 'handoff':
            app = {'chatgpt_app':'ChatGPT','claude_app':'Claude'}.get(data.get('app'))
            if not app: raise ValueError('Application inconnue.')
            text = str(data.get('prompt',''))[:160000]
            subprocess.run(['pbcopy'],input=text,text=True,check=True)
            result = subprocess.run(['open','-a',app],capture_output=True)
            if result.returncode: raise ValueError('Demande copiée. Application '+app+' introuvable ; ouvre-la manuellement.')
            return {'text':'Demande copiée. Colle-la dans '+app+', puis rapporte la réponse dans Jarvis.'}
        if action == 'import_answer':
            return services.save_result({'text':str(data.get('text',''))[:100000], 'private':True}, 'Réponse importée — à vérifier')
        if action == 'speak':
            with self._mutex: return self.voice.speak(data)
        if action == 'stop_speech': return self.voice.stop()
        raise ValueError('Action inconnue.')

    def _stop_speech(self):
        self.voice.stop()

    def _reports(self):
        results=[]
        for path in sorted(REPORTS.glob('*.json'),reverse=True)[:100]:
            if path.is_symlink(): continue
            try:
                item=read_json(path,{})
                results.append({'name':path.name,'title':item.get('title',path.stem),'created':item.get('created','')})
            except (ValueError,OSError): pass
        return results


def main():
    initialize()
    if '--briefing' in sys.argv:
        try: services.briefing(); print('Briefing enregistré.')
        except Exception as exc: print('Briefing non généré : '+type(exc).__name__); return 1
        return 0
    if '--check' in sys.argv:
        import webview, keyring, jwt, docx, reportlab, pdfplumber, google_auth_oauthlib
        import openjarvis
        from inspect import signature
        if 'engine_key' not in signature(openjarvis.Jarvis).parameters: raise RuntimeError('SDK OpenJarvis incompatible.')
        print('Modules et interface prêts.'); return 0
    lock=(CONFIG/'desktop.lock').open('a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        subprocess.run(['osascript','-e','display dialog "Jarvis est déjà ouvert. Consulte son icône dans le Dock." buttons {"OK"} default button "OK"'])
        return 0
    import webview
    from AppKit import NSApplication, NSImage
    from Foundation import NSBundle
    NSBundle.mainBundle().infoDictionary()['NSMicrophoneUsageDescription'] = 'Jarvis transcrit votre voix localement quand vous activez le microphone.'
    app=NSApplication.sharedApplication()
    icon=ROOT/'assets/Jarvis.icns'
    if icon.exists(): app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(icon)))
    api=Api()
    window=webview.create_window('Jarvis · Parlement',str(ROOT/'ui/index.html'),js_api=api,
        width=1280,height=850,min_size=(920,620),background_color='#0b1220',text_select=True)
    api._window=window
    window.events.closed += api._stop_speech
    webview.start(debug=False,gui='cocoa',private_mode=True)
    return 0


if __name__ == '__main__': sys.exit(main())
