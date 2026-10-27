"""Actionable provider errors; never persist prompts, tokens or raw response bodies."""
import re
from datetime import datetime, timezone
from common import CONFIG, atomic_json, read_json

class ProviderError(ValueError):
    def __init__(self, diagnostic):
        self.diagnostic=diagnostic
        super().__init__(diagnostic['cause']+' '+diagnostic['next_step']+' ['+diagnostic['code']+']')

CAUSES={
 'insufficient_quota':('Le fournisseur signale un quota ou un crédit insuffisant.','Vérifie les limites et les crédits du compte utilisé.'),
 'usage_limit_reached':('La limite d’usage autorisée a été atteinte.','Ouvre ChatGPT → Réglages → Usage et vérifie les limites accordées à Jarvis.'),
 'rate_limit_exceeded':('Le fournisseur limite le débit des demandes.','Patiente puis réessaie ; vérifie aussi les limites du compte.'),
 'model_not_found':('Le modèle demandé est introuvable ou inaccessible à ce compte.','Recharge les modèles de ce compte, choisis-en un puis enregistre les réglages.'),
 'unsupported_model':('Ce modèle ne prend pas en charge la demande.','Choisis un autre modèle dans la liste chargée pour ce compte.'),
 'invalid_api_key':('La clé fournie a été refusée.','Vérifie la clé du fournisseur dans Configuration.'),
 'invalid_token':('L’autorisation de connexion a été refusée.','Reconnecte le compte dans Configuration → IA.'),
 'invalid_grant':('Le renouvellement de la connexion a été refusé.','Reconnecte le compte dans Configuration → IA.'),
 'token_sharing_disabled':('L’usage du forfait par Jarvis n’est pas autorisé.','Reconnecte ChatGPT et autorise explicitement l’utilisation du forfait.'),
 'plan_usage_disabled':('L’usage du forfait par Jarvis n’est pas autorisé.','Reconnecte ChatGPT et autorise explicitement l’utilisation du forfait.'),
 'permission_denied':('Le compte ne dispose pas de l’autorisation demandée.','Vérifie les permissions de Jarvis et celles de ton espace de travail.'),
 'server_error':('Le fournisseur a signalé une erreur interne.','Réessaie plus tard. Si elle persiste, conserve l’identifiant de requête pour le support.'),
 'internal_server_error':('Le fournisseur a signalé une erreur interne.','Réessaie plus tard. Si elle persiste, conserve l’identifiant de requête pour le support.'),
 'max_output_tokens':('La génération a atteint sa limite de sortie et reste incomplète.','Réduis la demande ou demande une réponse plus courte.'),
 'content_filter':('La génération a été interrompue par un filtre du fournisseur.','Reformule la demande. Changer la connexion ne garantit pas son acceptation.'),
 'context_length_exceeded':('La demande dépasse la capacité de contexte du modèle.','Démarre une nouvelle conversation ou réduis le document.'),
 'invalid_request_error':('Le fournisseur a refusé le format ou un paramètre de la requête.','Ce refus peut venir du connecteur Jarvis. Copie le diagnostic pour le faire corriger.'),
 'unsupported_parameter':('Un paramètre envoyé par Jarvis n’est pas pris en charge.','Copie le diagnostic : le connecteur ou le modèle doit être ajusté.'),
 'stream_interrupted':('La connexion s’est terminée avant la réponse complète.','Réessaie après avoir vérifié Internet. Aucune réponse complète n’a été enregistrée.'),
 'invalid_stream':('Jarvis n’a pas pu décoder la réponse du fournisseur.','Copie le diagnostic : le flux reçu doit être vérifié dans le connecteur.'),
 'network_error':('La connexion réseau au fournisseur a échoué.','Vérifie Internet, le proxy ou le pare-feu, puis réessaie.'),
 'request_timeout':('Le délai de réponse du fournisseur a été dépassé.','Réessaie avec une demande plus courte ou un autre modèle.'),
}

def symbol(value):
    return value if isinstance(value,str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}',value) else ''


def failure(provider, stage, body=None, *, status=None, request_id=None, model=None, event=None, fallback=None):
    body=body if isinstance(body,dict) else {}
    response=body.get('response') if isinstance(body.get('response'),dict) else body
    error=response.get('error')
    error=error if isinstance(error,dict) else ({'code':error} if isinstance(error,str) else body)
    incomplete=response.get('incomplete_details') or {}
    reason=symbol(incomplete.get('reason')) if isinstance(incomplete,dict) else ''
    code=reason or symbol(error.get('code')) or symbol(error.get('type')) or fallback or ('http_'+str(status) if status else 'provider_error')
    explanation=CAUSES.get(code)
    if provider=='ChatGPT' and code=='invalid_api_key':explanation=CAUSES['invalid_token']
    if not explanation:
        explanation={401:('Le fournisseur a refusé l’authentification.','Reconnecte le compte ou vérifie la clé selon le fournisseur.'),
          403:('Le fournisseur refuse l’accès à cette ressource.','Vérifie les autorisations du compte et de ton organisation.'),
          404:('La ressource ou le modèle demandé est introuvable.','Recharge les modèles et vérifie le modèle enregistré.'),
          429:('Le fournisseur limite cette demande (HTTP 429).','Vérifie les quotas et les crédits, puis réessaie après un délai.'),
          400:CAUSES['invalid_request_error']}.get(status)
    if not explanation:
        explanation=CAUSES['server_error'] if status and status>=500 else ('Le fournisseur a signalé un échec dont Jarvis ne connaît pas encore la signification.','Copie le diagnostic avec le code reçu. La cause n’est pas déterminée ; ne change pas de forfait sur cette seule base.')
    d={'provider':provider,'stage':stage,'code':code,'cause':explanation[0],'next_step':explanation[1],
       'time':datetime.now(timezone.utc).isoformat()}
    if status is not None:d['http_status']=int(status)
    if isinstance(request_id,str) and re.fullmatch(r'(req_[A-Za-z0-9_-]{1,120}|[0-9a-fA-F-]{36})',request_id):d['request_id']=request_id
    if isinstance(model,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}',model):d['model']=model
    if event in ('error','response.failed','response.incomplete'):d['event']=event
    param=error.get('param')
    if param in ('model','input','instructions','tools','tool_choice','store','stream','max_output_tokens','temperature','reasoning'):d['parameter']=param
    return ProviderError(d)


def record(error):
    try:atomic_json(CONFIG/'last-provider-error.json',error.diagnostic)
    except OSError:pass


def last():return read_json(CONFIG/'last-provider-error.json',{})
