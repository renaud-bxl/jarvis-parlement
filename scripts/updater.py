"""Public release check. No shell from network; pinned archive hash, safe extraction."""
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from common import HOME
from voice import checked_download
VERSION='3.0.5'
MANIFEST='https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/latest.json'
PREFIX='https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/'


def version(value):
    if not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}',str(value)):raise ValueError('Version invalide.')
    return tuple(map(int,value.split('.')))


def check():
    try:
        with urllib.request.urlopen(MANIFEST,timeout=12) as response:
            payload=response.read(32001)
            if len(payload)>32000:raise ValueError('Manifeste trop volumineux.')
            m=json.loads(payload)
    except Exception:raise ValueError('Vérification des mises à jour indisponible. Réessaie avec une connexion Internet.') from None
    newer=version(m.get('version',''))>version(VERSION)
    if m.get('url')!=PREFIX+'Jarvis-Parlement-'+m['version']+'-macOS.zip':raise ValueError('Adresse de mise à jour non autorisée.')
    if not re.fullmatch('[a-f0-9]{64}',m.get('sha256','')):raise ValueError('Empreinte de mise à jour invalide.')
    return {'current':VERSION,'available':newer,'version':m['version'],'notes':str(m.get('notes',''))[:4000], 'url':m['url'],'sha256':m['sha256']}


def install():
    m=check()
    if not m['available']:return {'text':'Tu utilises déjà la dernière version publiée.'}
    downloads=HOME/'Downloads';downloads.mkdir(exist_ok=True)
    dest=Path(tempfile.mkdtemp(prefix='Jarvis-Update-',dir=downloads));archive=dest/'release.zip'
    checked_download(m['url'],archive,m['sha256'],limit=150*1024*1024)
    with zipfile.ZipFile(archive) as z:
        if sum(x.file_size for x in z.infolist())>300*1024*1024:raise ValueError('Archive trop volumineuse.')
        for item in z.infolist():
            p=Path(item.filename)
            if p.is_absolute() or '..' in p.parts or ((item.external_attr>>16)&0o170000)==0o120000:raise ValueError('Archive non sûre.')
        z.extractall(dest)
        for item in z.infolist():
            if item.external_attr>>16 & 0o111:(dest/item.filename).chmod(0o755)
    app=dest/'Installer Jarvis Parlement.app'
    if not (app/'Contents/MacOS/Installer').is_file():raise ValueError('Installateur absent de l’archive.')
    subprocess.run(['open',str(app)],check=True)
    return {'text':'Installateur vérifié et ouvert. Quitte Jarvis, puis clique sur Installer dans sa fenêtre. Tes comptes, modèles et documents sont conservés.'}
