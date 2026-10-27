#!/bin/bash
set -euo pipefail
umask 077
[[ "$(uname -s)" == Darwin ]] || { echo 'macOS requis.'; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo 'Lance cette commande sans sudo.'; exit 1; }
DEST="$(mktemp -d "$HOME/Downloads/Jarvis-Parlement-XXXXXX")"
URL='https://raw.githubusercontent.com/renaud-bxl/jarvis-parlement/main/dist/Jarvis-Parlement-3.0.3-macOS.zip'
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$URL" -o "$DEST/Jarvis.zip"
ACTUAL="$(shasum -a 256 "$DEST/Jarvis.zip" | awk '{print $1}')"
[[ "$ACTUAL" == '5d3bacc46868c258d2b1e8c3d46f3d294993972b4c7e14a4fd4d0e5229c3d639' ]] || { echo 'Archive invalide : empreinte SHA-256 différente.'; exit 1; }
ditto -x -k "$DEST/Jarvis.zip" "$DEST"
open "$DEST/Installer Jarvis Parlement.app"
echo "Installateur ouvert. Le mode d’emploi se trouve dans $DEST"
