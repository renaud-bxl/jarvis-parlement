import fcntl
import json
import os
import plistlib
import shlex
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import BASE, CONFIG, HOME, initialize, settings
from services import schedule
backup=Path(sys.argv[1])
lock=(CONFIG/'desktop.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Ferme Jarvis avant de relancer l’installation.')
initialize()
# Existing V1 launchers remain usable, now opening the GUI for daily use.
old=(BASE/'current').resolve() if (BASE/'current').exists() else None
app=HOME/'Applications/Jarvis Parlement.app'
stage=HOME/'Applications'/('Jarvis Parlement.build-'+str(os.getpid())+'.app')
exe=stage/'Contents/MacOS';exe.mkdir(parents=True)
resources=stage/'Contents/Resources';resources.mkdir()
info={'CFBundleName':'Jarvis Parlement','CFBundleDisplayName':'Jarvis Parlement','CFBundleIdentifier':'net.compose.jarvis-parlement',
    'CFBundleVersion':'2.0.0','CFBundleShortVersionString':'2.0.0','CFBundleExecutable':'Jarvis','CFBundlePackageType':'APPL',
    'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0','CFBundleIconFile':'Jarvis.icns'}
(stage/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
if (ROOT/'assets/Jarvis.icns').exists():shutil.copy2(ROOT/'assets/Jarvis.icns',resources/'Jarvis.icns')
launcher=exe/'Jarvis'
launcher.write_text('''#!/bin/bash
umask 077
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
BASE="$HOME/Applications/Jarvis-Parlement/current"
mkdir -p "$HOME/.config/jarvis-parlement"
"$BASE/.venv/bin/python" "$BASE/scripts/desktop.py" >> "$HOME/.config/jarvis-parlement/application.log" 2>&1
result=$?
if [[ "$result" != 0 ]]; then
  /usr/bin/osascript -e 'display dialog "Jarvis ne démarre pas. Consulte le journal dans ~/.config/jarvis-parlement/application.log ou relance l’installateur." buttons {"OK"} default button "OK"'
fi
exit "$result"
''');launcher.chmod(0o755)
nextlink=BASE/('current-'+str(os.getpid()));nextlink.symlink_to(ROOT,target_is_directory=True)
try:
    os.replace(nextlink,BASE/'current')
    if app.exists():shutil.move(str(app),str(backup/'Jarvis Parlement.app'))
    os.replace(stage,app)
    if settings().get('schedule_enabled'):schedule(settings())
except Exception:
    if old:
        rollback=BASE/('rollback-'+str(os.getpid()));rollback.symlink_to(old,target_is_directory=True);os.replace(rollback,BASE/'current')
    else:(BASE/'current').unlink(missing_ok=True)
    for name in ['settings.json','accounts.json','parlement.md','chatgpt-accounts.json']:
        if (backup/name).exists():shutil.copy2(backup/name,CONFIG/name)
    import subprocess
    plist=HOME/'Library/LaunchAgents/net.compose.jarvis-parlement.briefing.plist'
    domain=f'gui/{os.getuid()}'
    if plist.exists():subprocess.run(['launchctl','bootout',domain,str(plist)],capture_output=True)
    if (backup/plist.name).exists():
        shutil.copy2(backup/plist.name,plist)
        subprocess.run(['launchctl','bootstrap',domain,str(plist)],capture_output=True)
    else:plist.unlink(missing_ok=True)
    if (backup/'Jarvis Parlement.app').exists():
        if app.exists():shutil.rmtree(app)
        shutil.move(str(backup/'Jarvis Parlement.app'),str(app))
    elif app.exists():shutil.rmtree(app)
    raise
for name in ['Lancer-Jarvis','Configurer-Jarvis']:
    script=BASE/(name+'.command')
    script.write_text('#!/bin/bash\nopen '+shlex.quote(str(app))+'\n');script.chmod(0o755)
# Other old command files pointed to the V1 app.py; route them to compatible desktop operations.
for name,action in [('Briefing-Jarvis','--briefing'),('Diagnostic-Jarvis','--check')]:
    script=BASE/(name+'.command');script.write_text('#!/bin/bash\n'+shlex.quote(str(ROOT/'.venv/bin/python'))+' '+shlex.quote(str(ROOT/'scripts/desktop.py'))+' '+action+'\n');script.chmod(0o755)
for name in ['Indexer-Documents','Retirer-Veille-Automatique']:
    script=BASE/(name+'.command');script.write_text('#!/bin/bash\nopen '+shlex.quote(str(app))+'\n');script.chmod(0o755)
desktop=HOME/'Desktop/Jarvis Parlement.app'
if desktop.parent.exists() and not desktop.exists():desktop.symlink_to(app,target_is_directory=True)
print('Application et planning activés.')
