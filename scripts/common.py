import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONFIG = HOME / '.config/jarvis-parlement'
WORK = HOME / 'Documents/Jarvis-Parlementaire'
BASE = HOME / 'Applications/Jarvis-Parlement'
REPORTS = WORK / '08-Rapports'
SERVICE = 'jarvis-parlement'
DEFAULTS = {'provider': 'ollama', 'model': '', 'local_model':'', 'themes':
    'mobilité, logement, sécurité, urbanisme, patrimoine, finances',
    'voice': False, 'voice_model':'siwis', 'include_mail_in_briefing': False,
    'include_calendar_in_briefing': False, 'briefing_time': '10:30',
    'schedule_enabled': False, 'cloud_private_data': False,
    'full_name':'', 'role':'', 'institution':'', 'language':'fr', 'collaborator':'', 'tour_seen':False}


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    import tempfile
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def settings():
    return {**DEFAULTS, **read_json(CONFIG / 'settings.json', {})}


def initialize():
    os.umask(0o077)
    CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ['00-Instructions','01-Actualites','02-Questions-Parlementaires',
        '03-Projets-Ordonnances','04-Documents-Officiels','05-Communiques',
        '06-Dossiers-Thematiques','07-Correspondances','08-Rapports','09-Archives']:
        (WORK / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    prompt = CONFIG / 'parlement.md'
    if not prompt.exists():
        prompt.write_text((ROOT / 'prompts/parlement.md').read_text()); prompt.chmod(0o600)
    # Conserver le planning déjà enregistré par la V1.
    cfg = settings()
    if not cfg.get('local_model') and cfg.get('provider')=='ollama':cfg['local_model']=cfg.get('model','')
    plist = HOME / 'Library/LaunchAgents/net.compose.jarvis-parlement.briefing.plist'
    if 'schedule_enabled' not in read_json(CONFIG / 'settings.json', {}) and plist.exists():
        import plistlib
        try:
            value = plistlib.loads(plist.read_bytes()).get('StartCalendarInterval', {})
            cfg['briefing_time'] = f"{value['Hour']:02}:{value['Minute']:02}"
            cfg['schedule_enabled'] = True
        except (KeyError, ValueError): pass
    atomic_json(CONFIG / 'settings.json', cfg)
    import templates
    templates.seed()
