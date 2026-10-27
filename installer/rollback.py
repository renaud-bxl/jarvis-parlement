"""Restore one migration backup after explicit local confirmation."""
import fcntl
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

def restore(backup):
    home=Path.home();base=home/'Applications/Jarvis-Parlement';cfg=home/'.config/jarvis-parlement'
    lock=(cfg/'desktop.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Ferme Jarvis avant la restauration.')
    previous=backup/'previous-release.txt'
    if not previous.exists():raise SystemExit('Aucune version précédente dans cette sauvegarde. Les données sont conservées.')
    old=Path(previous.read_text().strip())
    if not old.is_absolute():old=base/old
    if not old.is_dir():raise SystemExit('La version précédente est introuvable.')
    answer=subprocess.run(['osascript','-e','display dialog "Restaurer cette version et ses réglages ? Les rapports et le Trousseau sont conservés." buttons {"Annuler", "Restaurer"} default button "Annuler"'],capture_output=True)
    if answer.returncode or b'Restaurer' not in answer.stdout:return
    plist=home/'Library/LaunchAgents/net.compose.jarvis-parlement.briefing.plist'
    domain=f'gui/{os.getuid()}'
    if plist.exists():subprocess.run(['launchctl','bootout',domain,str(plist)],capture_output=True)
    link=base/('restoring-'+str(os.getpid()));link.symlink_to(old,target_is_directory=True);os.replace(link,base/'current')
    for name in ['settings.json','accounts.json','parlement.md','chatgpt-accounts.json']:
        if (backup/name).exists():shutil.copy2(backup/name,cfg/name)
    if (backup/plist.name).exists():
        shutil.copy2(backup/plist.name,plist)
        subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True,capture_output=True)
    else:plist.unlink(missing_ok=True)
    app=home/'Applications/Jarvis Parlement.app'
    if (backup/app.name).exists():
        if app.exists():shutil.move(str(app),str(backup/('Version-remplacee-'+str(os.getpid())+'.app')))
        shutil.copytree(backup/app.name,app,symlinks=True)
    for source in (backup/'launchers').glob('*.command'):shutil.copy2(source,base/source.name)
    if not (old/'scripts/desktop.py').exists() and not (backup/app.name).exists() and app.exists():
        launcher=app/'Contents/MacOS/Jarvis'
        launcher.write_text('#!/bin/bash\nexec /usr/bin/open '+shlex.quote(str(base/'Lancer-Jarvis.command'))+'\n')
        launcher.chmod(0o755)
    print('Version et réglages restaurés. Les documents restent disponibles.')
    if (old/'scripts/desktop.py').exists():subprocess.run(['open',str(app)])
    elif (base/'Lancer-Jarvis.command').exists():subprocess.run(['open',str(base/'Lancer-Jarvis.command')])

if __name__=='__main__':restore(Path(sys.argv[1]).resolve())
