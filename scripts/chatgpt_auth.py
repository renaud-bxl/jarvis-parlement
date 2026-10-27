"""Official Sign in with ChatGPT for personal local apps; no desktop token scraping."""
import base64
import fcntl
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from diagnostics import failure
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4
from common import CONFIG, SERVICE, atomic_json, read_json

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
TOKEN_URL = ISSUER + '/api/accounts/oauth/token'
REQUIRED = {'chatgpt.tokens.use.direct', 'resource.invoke'}
_lock = threading.Lock()


def _json(url, data=None):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
        headers={'Content-Type': 'application/x-www-form-urlencoded'} if data else {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:body=json.loads(exc.read(65536))
        except (ValueError,OSError):body={}
        raise failure('ChatGPT','authorization',body,status=exc.code,request_id=exc.headers.get('x-request-id')) from None
    except TimeoutError:
        raise failure('ChatGPT','authorization',fallback='request_timeout') from None
    except (urllib.error.URLError,OSError):
        raise failure('ChatGPT','authorization',fallback='network_error') from None
    except ValueError:
        raise failure('ChatGPT','authorization',fallback='invalid_stream') from None



def _trusted_endpoint(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'auth.openai.com' or p.username or p.password:
        raise ValueError('Endpoint OAuth inattendu.')
    return url


def _records():
    return read_json(CONFIG / 'chatgpt-accounts.json', {'active': '', 'accounts': {}})


def status():
    records = _records()
    return {'active': records['active'], 'accounts': records['accounts']}


def _tokens(client_id):
    import keyring
    raw = keyring.get_password(SERVICE, 'chatgpt:' + client_id)
    return json.loads(raw) if raw else {}


def _store(client_id, tokens):
    import keyring
    keyring.set_password(SERVICE, 'chatgpt:' + client_id, json.dumps(tokens))


def validate_identity(tokens, client_id, nonce, previous=None):
    import jwt
    discovery = _json(ISSUER + '/.well-known/openid-configuration')
    jwks = jwt.PyJWKClient(_trusted_endpoint(discovery['jwks_uri']), timeout=20)
    encoded = tokens['id_token']
    key = jwks.get_signing_key_from_jwt(encoded)
    claims = jwt.decode(encoded, key.key, algorithms=['RS256'], audience=client_id,
        issuer=ISSUER, options={'require': ['exp', 'iss', 'aud', 'sub', 'nonce']})
    if not secrets.compare_digest(str(claims['nonce']), nonce):
        raise ValueError('Validation de la connexion ChatGPT échouée (nonce).')
    if previous and claims['sub'] != previous['subject']:
        raise ValueError('Ce compte ne correspond pas au compte sélectionné.')
    if not REQUIRED.issubset(set(tokens.get('scope', '').split())):
        raise ValueError('L’autorisation d’utiliser le forfait ChatGPT n’a pas été accordée.')
    if not tokens.get('access_token') or tokens.get('token_type', '').lower() != 'bearer':
        raise ValueError('Autorisation ChatGPT incomplète.')
    return claims


def connect(data):
    # Keep concurrent login attempts separate; accept only one per application process.
    if not _lock.acquire(blocking=False):
        raise ValueError('Une connexion ChatGPT est déjà en cours.')
    try:
        return _connect(data)
    finally:
        _lock.release()


def _connect(data):
    records = _records()
    selected = data.get('client_id', '')
    previous = records['accounts'].get(selected)
    if selected and not previous:
        raise ValueError('Compte ChatGPT inconnu.')
    host_path = CONFIG / 'chatgpt-host.json'
    host = read_json(host_path, {})
    if not host.get('id'):
        host = {'id': 'urn:uuid:' + str(uuid4())}
        atomic_json(host_path, host)
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    callback = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parts = urllib.parse.urlsplit(self.path)
            params = urllib.parse.parse_qs(parts.query)
            valid = (parts.path == '/auth/callback' and len(params.get('state', [])) == 1
                and secrets.compare_digest(params['state'][0], state))
            if not valid:
                self.send_error(400, 'Invalid callback'); return
            callback.update({k: v[0] for k, v in params.items() if len(v) == 1})
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write('Autorisation reçue. Reviens dans Jarvis pour vérifier la connexion.'.encode())

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
        params = {'client_id': selected or 'dynamic_agent_client',
            'ext_agent_host_id': host['id'], 'response_type': 'code', 'redirect_uri': redirect,
            'scope': 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct',
            'resource': RESOURCE, 'state': state, 'nonce': nonce, 'code_challenge_method': 'S256',
            'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')}
        if not selected:
            params['agent_name_hint'] = 'Jarvis Parlement'
        else:
            old = _tokens(selected)
            if old.get('id_token'): params['id_token_hint'] = old['id_token']
        webbrowser.open(ISSUER + '/api/accounts/authorize?' + urllib.parse.urlencode(params))
        deadline = time.monotonic() + 300
        while not callback and time.monotonic() < deadline:
            server.handle_request()
    if not callback:
        raise ValueError('Connexion expirée après 5 minutes. Réessaie.')
    if callback.get('error'):
        raise ValueError('Connexion ou utilisation du forfait refusée. Vérifie l’éligibilité dans ChatGPT.')
    client = callback.get('client_id') or selected
    if not client or client == 'dynamic_agent_client' or (selected and client != selected):
        raise ValueError('Identifiant de connexion ChatGPT invalide.')
    if not callback.get('code'): raise ValueError('Code OAuth absent.')
    tokens = _json(TOKEN_URL, {'grant_type': 'authorization_code', 'client_id': client,
        'code': callback['code'], 'code_verifier': verifier, 'redirect_uri': redirect, 'resource': RESOURCE})
    claims = validate_identity(tokens, client, nonce, previous)
    tokens['expires_at'] = time.time() + int(tokens.get('expires_in', 3600))
    _store(client, tokens)
    records['accounts'][client] = {'subject': claims['sub'], 'email': claims.get('email', ''),
        'label': claims.get('email', 'ChatGPT') + ' · ' + client[-6:], 'connected': True}
    records['active'] = client
    atomic_json(CONFIG / 'chatgpt-accounts.json', records)
    return {'text': 'Compte ChatGPT connecté. Charge les modèles puis enregistre ton choix.'}


def select(data):
    records = _records(); client = data.get('client_id')
    if client not in records['accounts']: raise ValueError('Compte inconnu.')
    records['active'] = client
    atomic_json(CONFIG / 'chatgpt-accounts.json', records)
    return {'text': 'Compte ChatGPT sélectionné. Recharge ses modèles.'}


def access_token():
    # Lock across GUI and launchd to avoid refresh-token rotation races.
    with _lock, (CONFIG / 'chatgpt-refresh.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        client = _records()['active']
        if not client: raise ValueError('Connecte ton compte ChatGPT dans Paramètres > IA.')
        tokens = _tokens(client)
        if tokens.get('expires_at', 0) <= time.time() + 60:
            if not tokens.get('refresh_token'): raise ValueError('Reconnecte ton compte ChatGPT.')
            renewed = _json(TOKEN_URL, {'grant_type': 'refresh_token', 'client_id': client,
                'refresh_token': tokens['refresh_token'], 'resource': RESOURCE})
            if not renewed.get('access_token') or not renewed.get('refresh_token'):
                raise ValueError('Renouvellement ChatGPT incomplet. Reconnecte ton compte.')
            tokens.update(renewed)
            if not REQUIRED.issubset(set(tokens.get('scope', '').split())):
                raise ValueError('Autorisation ChatGPT révoquée. Reconnecte le compte.')
            tokens['expires_at'] = time.time() + int(renewed.get('expires_in', 3600))
            _store(client, tokens)
        return tokens['access_token']


def disconnect(data):
    import keyring
    records = _records(); client = data.get('client_id') or records['active']
    if client not in records['accounts']: raise ValueError('Compte inconnu.')
    warning = ''
    with _lock, (CONFIG / 'chatgpt-refresh.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        tokens = _tokens(client)
        if tokens.get('refresh_token'):
            try:
                discovery = _json(ISSUER + '/.well-known/openid-configuration')
                _json(_trusted_endpoint(discovery['revocation_endpoint']), {'token': tokens['refresh_token'],
                    'token_type_hint': 'refresh_token', 'client_id': client})
            except Exception:
                warning = ' Révocation distante non confirmée : retire aussi Jarvis dans les réglages ChatGPT.'
        if tokens: keyring.delete_password(SERVICE, 'chatgpt:' + client)
        records['accounts'][client]['connected'] = False
        atomic_json(CONFIG / 'chatgpt-accounts.json', records)
    return {'text': 'Session locale déconnectée.' + warning}


def response(payload):
    request = urllib.request.Request(RESOURCE + '/responses', data=json.dumps({**payload,
        'stream': True, 'store': False}).encode(), headers={'Content-Type': 'application/json',
        'Accept':'text/event-stream', 'Authorization': 'Bearer ' + access_token()})
    request_id=None
    def process(lines):
        raw='\n'.join(lines)
        if raw.strip()=='[DONE]':return None
        try:event=json.loads(raw)
        except (ValueError,TypeError):raise failure('ChatGPT','generation',fallback='invalid_stream',request_id=request_id,model=payload.get('model')) from None
        if not isinstance(event,dict):raise failure('ChatGPT','generation',fallback='invalid_stream',request_id=request_id,model=payload.get('model'))
        kind=event.get('type')
        if kind=='response.completed':
            result=event.get('response')
            if not isinstance(result,dict):raise failure('ChatGPT','generation',fallback='invalid_stream',request_id=request_id,model=payload.get('model'))
            return result
        if kind in ('error','response.failed','response.incomplete'):
            raise failure('ChatGPT','generation',event,request_id=request_id,model=payload.get('model'),event=kind)
    try:
        with urllib.request.urlopen(request, timeout=300) as reply:
            request_id=reply.headers.get('x-request-id')
            pending=[]
            for raw in reply:
                try:line=raw.decode('utf-8').rstrip('\r\n')
                except UnicodeError:raise failure('ChatGPT','generation',fallback='invalid_stream',request_id=request_id,model=payload.get('model')) from None
                if line.startswith('data:'):pending.append(line[5:].lstrip())
                elif not line and pending:
                    result=process(pending);pending=[]
                    if result is not None:return result
            if pending:
                result=process(pending)
                if result is not None:return result
    except urllib.error.HTTPError as exc:
        try:body=json.loads(exc.read(65536))
        except (ValueError,OSError):body={}
        raise failure('ChatGPT','generation',body,status=exc.code,request_id=exc.headers.get('x-request-id'),model=payload.get('model')) from None
    except TimeoutError:
        raise failure('ChatGPT','generation',fallback='request_timeout',request_id=request_id,model=payload.get('model')) from None
    except (urllib.error.URLError,OSError):
        raise failure('ChatGPT','generation',fallback='network_error',request_id=request_id,model=payload.get('model')) from None
    raise failure('ChatGPT','generation',fallback='stream_interrupted',request_id=request_id,model=payload.get('model'))
