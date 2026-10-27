"""OpenAI text model filtering. Shutdown dates: official docs, checked 2026-10-27.
https://developers.openai.com/api/docs/deprecations
The API shutdown_date field takes precedence over the fallback catalogue.
"""
from datetime import date
RETIRED={m:'2026-10-23' for m in ('gpt-3.5-turbo','gpt-3.5-turbo-0125','gpt-4','gpt-4-0613','gpt-4-turbo','gpt-4-turbo-2024-04-09','gpt-4-1106-preview','gpt-4.1-nano','gpt-4.1-nano-2025-04-14','gpt-4o-2024-05-13','o1','o1-pro','o3-mini','o3-mini-2025-01-31','o4-mini','o4-mini-2025-04-16')}

def shutdown(model):
    return RETIRED.get(model) or ('2026-10-23' if model.startswith('gpt-3.5-') else None)

def available_text_models(entries, today=None):
    today=today or date.today().isoformat()
    result=[]
    for entry in entries:
        model=entry.get('id','')
        if not isinstance(model,str) or not model.startswith(('gpt-','o3','o4')):continue
        if any(part in model for part in ('audio','realtime','transcribe','tts','image','instruct','search-preview','completions')):continue
        stop=entry.get('shutdown_date') or shutdown(model)
        try: expired=bool(stop and date.fromisoformat(stop)<=date.fromisoformat(today))
        except (TypeError,ValueError): expired=False
        if not expired:result.append(model)
    return sorted(set(result))
