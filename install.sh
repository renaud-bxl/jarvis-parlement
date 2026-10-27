#!/bin/bash
set -euo pipefail
umask 077
[[ "$(uname -s)" == Darwin ]] || { echo 'macOS requis.'; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo 'Lance cette commande sans sudo.'; exit 1; }
DEST="$(mktemp -d "$HOME/Downloads/Jarvis-Parlement-XXXXXX")"
URL='https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/Jarvis-Parlement-3.0.1-macOS.zip'
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$URL" -o "$DEST/Jarvis.zip"
ACTUAL="$(shasum -a 256 "$DEST/Jarvis.zip" | awk '{print $1}')"
[[ "$ACTUAL" == '3582e425d96f23c3e24a4119ed92c1a49f54eb517f86ac883337870026f133e5' ]] || { echo 'Archive invalide : empreinte SHA-256 différente.'; exit 1; }
ditto -x -k "$DEST/Jarvis.zip" "$DEST"
open "$DEST/Installer Jarvis Parlement.app"
echo "Installateur ouvert. Le mode d’emploi se trouve dans $DEST"
