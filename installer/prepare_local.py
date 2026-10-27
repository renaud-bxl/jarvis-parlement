import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import CONFIG, atomic_json, read_json
binary=os.environ['JARVIS_OLLAMA_BINARY']
def available():
    try:
        with urlopen('http://127.0.0.1:11434/api/tags',timeout=3) as reply:
            return [m['name'] for m in json.load(reply).get('models',[])
                if not m.get('remote_host') and not m.get('remote_model') and 'cloud' not in m['name'].lower()]
    except Exception: return None
models=available()
if models is None:
    with (CONFIG/'ollama.log').open('ab') as log:
        subprocess.Popen([binary,'serve'],stdout=log,stderr=log,start_new_session=True)
    for _ in range(40):
        time.sleep(.5);models=available()
        if models is not None:break
if models is None:
    print('Ollama ne répond pas encore. Le diagnostic permettra de réessayer.');sys.exit(0)
cfg=read_json(CONFIG/'settings.json',{})
if not cfg.get('local_model') and models:cfg['local_model']=models[0]
if cfg.get('provider','ollama')=='ollama' and not cfg.get('model') and models:cfg['model']=models[0]
if not models:
    code=subprocess.run([binary,'pull','qwen3.5:2b']).returncode
    if code: print('Téléchargement du modèle non terminé. Réessaie depuis Configuration > IA.')
    else:
        cfg['local_model']='qwen3.5:2b'
        if cfg.get('provider','ollama')=='ollama':cfg['model']='qwen3.5:2b'
atomic_json(CONFIG/'settings.json',cfg)
