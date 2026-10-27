#!/bin/bash
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
BASE="$HOME/Applications/Jarvis-Parlement"
CFG="$HOME/.config/jarvis-parlement"
STATE="${JARVIS_PROGRESS_FILE:-$CFG/install-progress.txt}"
LOCK="$CFG/install-v2.lock"
TMP=""
MOUNT=""
step() { printf '%s\n%s\n' "$1" "$2" > "$STATE"; printf '%s\n' "$2"; }
cleanup() {
  local code=$?
  if [[ -n "$MOUNT" ]]; then hdiutil detach "$MOUNT" -quiet >/dev/null 2>&1 || true; fi
  if [[ -n "$TMP" && -d "$TMP" ]]; then rm -rf "$TMP"; fi
  rmdir "$LOCK" >/dev/null 2>&1 || true
  if [[ "$code" != 0 ]]; then step -1 'Installation interrompue. Consulte le journal ; les données précédentes sont conservées.'; fi
}
[[ "$(uname -s)" == Darwin ]] || { echo 'macOS requis.'; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo 'Utilise le compte normal du Mac, sans sudo.'; exit 1; }
mkdir -p "$CFG" "$BASE/versions" "$BASE/backups"
if ! mkdir "$LOCK" 2>/dev/null; then step -1 "Une installation est déjà ouverte. En cas d’interruption, relance le Mac puis retire uniquement $LOCK"; exit 1; fi
trap cleanup EXIT
MAJOR="$(sw_vers -productVersion | cut -d. -f1)"
[[ "$MAJOR" -ge 14 ]] || { step -1 'Cette version nécessite macOS 14 Sonoma ou ultérieur.'; exit 1; }
TMP="$(mktemp -d -t jarvis-install)"
RELEASE="$BASE/versions/3.0.4-$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$RELEASE"
cp -R "$SOURCE/." "$RELEASE/"
step 5 'Détection et sauvegarde de l’installation existante…'
BACKUP="$BASE/backups/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$BACKUP"
mkdir -p "$BACKUP/launchers"
for FILE in "$BASE/"*.command; do
  if [[ -f "$FILE" ]]; then cp -p "$FILE" "$BACKUP/launchers/"; fi
done
for FILE in settings.json accounts.json parlement.md chatgpt-accounts.json; do
  if [[ -f "$CFG/$FILE" ]]; then cp -p "$CFG/$FILE" "$BACKUP/"; fi
done
if [[ -f "$HOME/Library/LaunchAgents/net.compose.jarvis-parlement.briefing.plist" ]]; then cp -p "$HOME/Library/LaunchAgents/net.compose.jarvis-parlement.briefing.plist" "$BACKUP/"; fi
if [[ -L "$BASE/current" ]]; then readlink "$BASE/current" > "$BACKUP/previous-release.txt"; fi
step 15 'Installation de Python et de l’environnement isolé…'
UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
  curl --fail --location --retry 3 --proto '=https' --tlsv1.2 https://astral.sh/uv/install.sh -o "$TMP/uv-install.sh"
  UV_NO_MODIFY_PATH=1 sh "$TMP/uv-install.sh"
  UV="$HOME/.local/bin/uv"
fi
"$UV" python install 3.12
"$UV" venv --python 3.12 "$RELEASE/.venv"
PY="$RELEASE/.venv/bin/python"
cp "$RELEASE/installer/rollback.py" "$BACKUP/rollback.py"
printf '#!/bin/bash\nexec %q %q %q\n' "$PY" "$BACKUP/rollback.py" "$BACKUP" > "$BACKUP/Restaurer cette version.command"
chmod 700 "$BACKUP/Restaurer cette version.command"
step 30 'Installation de l’interface, des moteurs IA, des mails et des exports…'
"$UV" pip install --python "$PY" -r "$RELEASE/requirements.txt"
"$UV" pip freeze --python "$PY" > "$RELEASE/installed-versions.txt"
step 55 'Recherche d’Ollama et des modèles déjà présents…'
OLLAMA="$(command -v ollama || true)"
if [[ -z "$OLLAMA" ]]; then
  for CANDIDATE in '/Applications/Ollama.app/Contents/Resources/ollama' "$HOME/Applications/Ollama.app/Contents/Resources/ollama"; do
    if [[ -x "$CANDIDATE" ]]; then OLLAMA="$CANDIDATE"; break; fi
  done
fi
if [[ -z "$OLLAMA" ]]; then
  curl --fail --location --retry 3 --proto '=https' --tlsv1.2 https://ollama.com/download/Ollama.dmg -o "$TMP/Ollama.dmg"
  MOUNT="$TMP/ollama-volume"; mkdir "$MOUNT"
  hdiutil attach "$TMP/Ollama.dmg" -nobrowse -quiet -mountpoint "$MOUNT"
  [[ -d "$MOUNT/Ollama.app" ]] || { echo 'Application Ollama absente de l’image disque.'; exit 1; }
  ditto "$MOUNT/Ollama.app" "$HOME/Applications/Ollama.app"
  hdiutil detach "$MOUNT" -quiet; MOUNT=""
  OLLAMA="$HOME/Applications/Ollama.app/Contents/Resources/ollama"
fi
export JARVIS_OLLAMA_BINARY="$OLLAMA"
step 65 'Démarrage du moteur local et vérification du modèle…'
"$PY" "$RELEASE/installer/prepare_local.py"
step 75 'Vérification des exports Word et PDF…'
if [[ "${JARVIS_INSTALL_LIBREOFFICE:-1}" == 1 && ! -x /Applications/LibreOffice.app/Contents/MacOS/soffice && ! -x "$HOME/Applications/LibreOffice.app/Contents/MacOS/soffice" ]]; then
  ARCH="$(uname -m)"; [[ "$ARCH" != arm64 ]] || ARCH=aarch64
  LO_URL="https://download.documentfoundation.org/libreoffice/stable/26.8.1/mac/$ARCH/LibreOffice_26.8.1_MacOS_${ARCH}.dmg"
  if curl --fail --location --retry 2 --proto '=https' --tlsv1.2 "$LO_URL" -o "$TMP/LibreOffice.dmg"; then
    MOUNT="$TMP/libreoffice-volume"; mkdir "$MOUNT"
    if hdiutil attach "$TMP/LibreOffice.dmg" -nobrowse -quiet -mountpoint "$MOUNT"; then
      if [[ -d "$MOUNT/LibreOffice.app" ]]; then ditto "$MOUNT/LibreOffice.app" "$HOME/Applications/LibreOffice.app"; fi
      hdiutil detach "$MOUNT" -quiet; MOUNT=""
    fi
  else
    printf '%s\n' 'LibreOffice non téléchargé. Word reste disponible ; un lien d’installation PDF est fourni dans l’aide.' > "$RELEASE/install-warning.txt"
  fi
fi
step 85 'Validation des composants et reprise des réglages…'
if ! "$PY" "$RELEASE/scripts/desktop.py" --check; then
  for FILE in settings.json accounts.json parlement.md chatgpt-accounts.json; do
    if [[ -f "$BACKUP/$FILE" ]]; then cp -p "$BACKUP/$FILE" "$CFG/$FILE"; fi
  done
  exit 1
fi
"$PY" "$RELEASE/installer/activate.py" "$BACKUP"
step 100 'Installation terminée. Ouvre Jarvis pour choisir ton profil et tes connexions.'
