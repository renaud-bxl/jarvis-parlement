"""Moteurs automatiques et transfert manuel vers les apps de bureau."""
import json
import shutil
import subprocess
import urllib.error
import urllib.request
import time
from common import CONFIG, ROOT, SERVICE

PROVIDERS = ('ollama', 'chatgpt', 'openai', 'anthropic', 'chatgpt_app', 'claude_app')


def secret(provider):
    import keyring
    value = keyring.get_password(SERVICE, 'api:' + provider)
    if not value: raise ValueError('Ajoute la clé de ce fournisseur dans Paramètres > IA.')
    return value


def safe_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return {400:'Requête ou modèle incompatible. Vérifie le modèle et l’option recherche web.',
            401:'Clé API invalide ou expirée.',403:'Accès refusé par le fournisseur.',
            404:'Modèle ou ressource introuvable.',429:'Quota, crédit ou limite de débit du fournisseur atteint.'}.get(
                exc.code, 'Erreur du fournisseur (HTTP ' + str(exc.code) + ').')
    return 'Le service ne répond pas. Vérifie la connexion, le modèle et le diagnostic.'


def request_json(url, payload=None, headers=None, timeout=180):
    request = urllib.request.Request(url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type':'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(safe_error(exc)) from None


def ensure_ollama():
    try:
        request_json('http://127.0.0.1:11434/api/tags', timeout=2); return
    except ValueError: pass
    binary = shutil.which('ollama')
    if not binary:
        from pathlib import Path
        for candidate in [Path('/Applications/Ollama.app/Contents/Resources/ollama'),
                Path.home()/'Applications/Ollama.app/Contents/Resources/ollama']:
            if candidate.exists(): binary = str(candidate); break
    if not binary: raise ValueError('Ollama absent. Relance l’installateur.')
    with (CONFIG / 'ollama.log').open('ab') as log:
        subprocess.Popen([binary, 'serve'], stdout=log, stderr=log, start_new_session=True)
    for _ in range(30):
        time.sleep(0.5)
        try:
            request_json('http://127.0.0.1:11434/api/tags', timeout=2); return
        except ValueError: pass
    raise ValueError('Ollama ne démarre pas. Consulte le diagnostic.')


def models(provider):
    if provider == 'chatgpt':
        from chatgpt_auth import access_token
        result = request_json('https://api.openai.com/v1/models', headers={'Authorization':'Bearer '+access_token()})
        return [m['slug'] for m in result.get('models',[]) if m.get('visibility') == 'list']
    if provider == 'ollama':
        ensure_ollama()
        return [m['name'] for m in request_json('http://127.0.0.1:11434/api/tags').get('models', [])
                if not m.get('remote_host') and not m.get('remote_model') and 'cloud' not in m['name'].lower()]
    if provider == 'openai':
        result = request_json('https://api.openai.com/v1/models',
            headers={'Authorization':'Bearer ' + secret(provider)})
        return sorted(m['id'] for m in result.get('data', []) if m['id'].startswith(('gpt-', 'o3', 'o4')))
    if provider == 'anthropic':
        result = request_json('https://api.anthropic.com/v1/models',
            headers={'x-api-key':secret(provider), 'anthropic-version':'2023-06-01'})
        return [m['id'] for m in result.get('data', [])]
    return []


def complete(prompt, cfg, web=False, private=False, system=''):
    provider, model = cfg['provider'], cfg.get('model', '')
    if provider not in PROVIDERS: raise ValueError('Fournisseur inconnu.')
    if private and provider in ('chatgpt','openai','anthropic') and not cfg.get('cloud_private_data'):
        raise ValueError('Données privées : utilise Ollama ou autorise explicitement leur traitement cloud dans Paramètres.')
    if provider.endswith('_app'):
        return {'handoff':True, 'prompt':system+'\n\n'+prompt, 'app':provider,
            'text':'Transfert manuel : copie la demande, ouvre l’application, puis colle la réponse dans Jarvis.'}
    if not model: raise ValueError('Choisis un modèle dans Paramètres > IA.')
    if provider == 'ollama':
        ensure_ollama()
        details=request_json('http://127.0.0.1:11434/api/show',{'model':model})
        if details.get('remote_host') or details.get('remote_model') or 'cloud' in model.lower():
            raise ValueError('Choisis un modèle exécuté localement. Les modèles Ollama cloud ne sont pas autorisés ici.')
        if web:
            from openjarvis import Jarvis
            j = Jarvis(engine_key='ollama', model=model)
            try:
                full = j.ask_full(system+'\n\n'+prompt, agent='orchestrator',
                    tools=['web_search','think'], context=False, temperature=0.2)
            finally:
                j.close()
            calls = full.get('tool_results', [])
            # Never present an ungrounded model answer as a live search.
            if 'web_search' not in json.dumps(calls, default=str):
                raise ValueError('Le modèle local n’a pas effectué de recherche web. Essaie un modèle compatible avec les outils ou un fournisseur cloud.')
            return {'text':full['content'], 'sources':[], 'provider':provider, 'model':model}
        result = request_json('http://127.0.0.1:11434/api/chat', {
            'model':model, 'stream':False,
            'messages':[{'role':'system','content':system}, {'role':'user','content':prompt}]}, timeout=900)
        return {'text':result['message']['content'],'sources':[], 'provider':provider,'model':model}
    if provider in ('openai','chatgpt'):
        payload = {'model':model,'instructions':system,'input':prompt,'store':False}
        if web: payload.update(tools=[{'type':'web_search'}], tool_choice='required')
        if provider == 'chatgpt':
            from chatgpt_auth import response
            payload['input'] = [{'role':'user','content':prompt}]
            result = response(payload)
        else:
            result = request_json('https://api.openai.com/v1/responses',payload,
                {'Authorization':'Bearer '+secret(provider)},timeout=300)
        if result.get('status') not in ('completed',None):
            raise ValueError('Réponse OpenAI incomplète. Réduis la demande ou vérifie le modèle.')
        text, sources = [], []
        for output in result.get('output',[]):
            for block in output.get('content',[]):
                if block.get('type') == 'output_text':
                    text.append(block['text'])
                    for cite in block.get('annotations',[]):
                        if cite.get('type') == 'url_citation':
                            sources.append({'title':cite.get('title','Source'), 'url':cite['url']})
        if not text: raise ValueError('Le fournisseur n’a retourné aucun texte exploitable.')
        return {'text':'\n'.join(text),'sources':sources,'provider':provider,'model':model}
    payload = {'model':model,'system':system,'max_tokens':6000,
               'messages':[{'role':'user','content':prompt}]}
    if web: payload['tools']=[{'type':'web_search_20250305','name':'web_search','max_uses':5}]
    headers = {'x-api-key':secret(provider), 'anthropic-version':'2023-06-01'}
    result = request_json('https://api.anthropic.com/v1/messages',payload,headers,timeout=300)
    continuations = 0
    while result.get('stop_reason') == 'pause_turn' and continuations < 2:
        payload['messages'].append({'role':'assistant','content':result['content']})
        result = request_json('https://api.anthropic.com/v1/messages',payload,headers,timeout=300)
        continuations += 1
    if result.get('stop_reason') == 'pause_turn':
        raise ValueError('Recherche Claude trop longue. Précise la demande puis réessaie.')
    text, sources = [], []
    if web and not any(b.get('type') == 'server_tool_use' and b.get('name') == 'web_search'
            for msg in payload['messages'] + [{'content':result.get('content',[])}]
            for b in (msg['content'] if isinstance(msg['content'],list) else [])):
        raise ValueError('Claude n’a pas effectué de recherche web. Vérifie le modèle et l’activation de la recherche sur ton compte API.')
    for block in result.get('content',[]):
        if block.get('type') == 'text':
            text.append(block['text'])
            for cite in block.get('citations',[]):
                if cite.get('url'): sources.append({'title':cite.get('title','Source'),'url':cite['url']})
    if not text: raise ValueError('Claude n’a retourné aucun texte exploitable.')
    if result.get('stop_reason') == 'max_tokens': text.append('\n[Réponse tronquée : demande une suite.]')
    return {'text':'\n'.join(text),'sources':sources,'provider':provider,'model':model}
