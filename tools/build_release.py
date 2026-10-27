"""Build a transparent macOS .app installer without requiring a Mac compiler."""
import hashlib
import json
import plistlib
import shutil
import stat
import tempfile
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist';DIST.mkdir(exist_ok=True)
# Geometric icon drawn directly from primitives, no third-party image asset.
icon=Image.new('RGBA',(1024,1024),(0,0,0,0));d=ImageDraw.Draw(icon)
d.rounded_rectangle((55,55,969,969),radius=205,fill='#102e69')
d.arc((210,165,815,790),190,350,fill='#ffdc37',width=60)
d.rounded_rectangle((670,230,735,600),radius=25,fill='#ffdc37')
d.line((250,785,780,785),fill='#f3f5fa',width=26)
for x,h in [(305,180),(440,250),(575,180)]:d.rounded_rectangle((x,735-h,x+65,735),radius=10,fill='#f3f5fa')
(ROOT/'assets').mkdir(exist_ok=True)
icon.save(ROOT/'assets/Jarvis.icns')
with tempfile.TemporaryDirectory() as folder:
 stage=Path(folder);app=stage/'Installer Jarvis Parlement.app';contents=app/'Contents'
 exe=contents/'MacOS';exe.mkdir(parents=True);resources=contents/'Resources';resources.mkdir()
 payload=resources/'payload';payload.mkdir()
 for name in ['scripts','ui','installer','assets','starter-templates','config','prompts','tests']:
  shutil.copytree(ROOT/name,payload/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','upstream-install.sh'))
 for name in ['requirements.txt','LICENSE','README.md','NOTICE.md','VALIDATION.md','LICENSE-OpenJarvis-Apache-2.0.txt']:
  shutil.copy2(ROOT/name,payload/name)
 shutil.copy2(ROOT/'assets/Jarvis.icns',resources/'Jarvis.icns')
 info={'CFBundleName':'Installer Jarvis Parlement','CFBundleDisplayName':'Installer Jarvis Parlement',
 'CFBundleIdentifier':'net.compose.jarvis-parlement.installer','CFBundleExecutable':'Installer',
 'CFBundleVersion':'3.0.1','CFBundleShortVersionString':'3.0.1','CFBundlePackageType':'APPL',
 'CFBundleIconFile':'Jarvis.icns','LSMinimumSystemVersion':'14.0','NSHighResolutionCapable':True}
 (contents/'Info.plist').write_bytes(plistlib.dumps(info))
 launcher=exe/'Installer';launcher.write_text('''#!/bin/bash
set -euo pipefail
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
exec /usr/bin/osascript -l JavaScript "$RES/payload/installer/window.js" "$RES/payload"
''');launcher.chmod(0o755)
 manual='<!doctype html><html lang="fr"><meta charset="utf-8"><title>Jarvis Parlement — Mode d’emploi</title><style>body{font:17px/1.6 system-ui;max-width:900px;margin:50px auto;padding:0 25px;color:#172036}h2{margin-top:2em}table{border-collapse:collapse}td,th{border:1px solid #ccd3dc;padding:12px;text-align:left}code{background:#f0f3f7;padding:2px 5px}</style><body>'+ (ROOT/'ui/manual.html').read_text()+'</body></html>'
 (stage/'Mode-emploi-Jarvis.html').write_text(manual)
 (stage/'LIRE-AVANT-INSTALLATION.txt').write_text('JARVIS — PARLEMENT 3.0.1, version candidate\n\nOuvre Installer Jarvis Parlement.app, puis clique sur Installer.\nmacOS 14 minimum, Internet nécessaire. Ferme Jarvis avant une mise à jour.\n\nDistribution non signée/notariée Apple. Voir le mode d’emploi pour les autorisations macOS.\nLes comptes existants sont conservés, les dépendances manquantes sont installées.\nAucune identité parlementaire n’est imposée. Complète le profil au premier lancement.\n\nTests de logique et exports vérifiés ; installation native et comptes réels restent à valider sur Mac.\nLe code source est dans l’app : Afficher le contenu du paquet > Contents > Resources > payload.\n')
 archive=DIST/'Jarvis-Parlement-3.0.1-macOS.zip'
 with ZipFile(archive,'w',ZIP_DEFLATED) as z:
  for path in sorted(stage.rglob('*')):
   if path.is_file():z.write(path,path.relative_to(stage))
 digest=hashlib.sha256(archive.read_bytes()).hexdigest()
 (DIST/'latest.json').write_text(json.dumps({'version':'3.0.1','url':'https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/'+archive.name,'sha256':digest,'notes':'Jarvis visuel, conversation et voix françaises locales, mises à jour intégrées.'},ensure_ascii=False,indent=2)+'\n')
 (DIST/'SHA256SUMS').write_text(digest+'  '+archive.name+'\n')
 bootstrap='''#!/bin/bash
set -euo pipefail
umask 077
[[ "$(uname -s)" == Darwin ]] || { echo 'macOS requis.'; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo 'Lance cette commande sans sudo.'; exit 1; }
DEST="$(mktemp -d "$HOME/Downloads/Jarvis-Parlement-XXXXXX")"
URL='https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/Jarvis-Parlement-3.0.1-macOS.zip'
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$URL" -o "$DEST/Jarvis.zip"
ACTUAL="$(shasum -a 256 "$DEST/Jarvis.zip" | awk '{print $1}')"
[[ "$ACTUAL" == 'DIGEST' ]] || { echo 'Archive invalide : empreinte SHA-256 différente.'; exit 1; }
ditto -x -k "$DEST/Jarvis.zip" "$DEST"
open "$DEST/Installer Jarvis Parlement.app"
echo "Installateur ouvert. Le mode d’emploi se trouve dans $DEST"
'''.replace('DIGEST',digest)
 (ROOT/'install.sh').write_text(bootstrap);(ROOT/'install.sh').chmod(0o755)
 print(archive);print('SHA256 '+digest)
