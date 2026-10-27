# Composants et modèles

Jarvis Parlement est une application distincte d'OpenJarvis, OpenAI, Anthropic, Google, Ollama et des assemblées parlementaires. Elle n'est ni certifiée ni publiée par ces organisations.

OpenJarvis est distribué selon Apache 2.0 ; copie jointe dans `LICENSE-OpenJarvis-Apache-2.0.txt`. Les autres composants téléchargés conservent leurs licences respectives. LibreOffice est téléchargé depuis The Document Foundation, Ollama depuis son site officiel et uv depuis Astral.

Les modèles bruxellois sont adaptés de trois documents fournis pour ce projet. Les marques et logos institutionnels restent la propriété de leurs titulaires. La présence d'un logo ne constitue pas une validation institutionnelle. Les fichiers d'origine et la signature manuscrite sont exclus de cette distribution.

## Voix locales de la version 3

Piper 1.8.0 est installé séparément depuis PyPI et invoqué comme processus CLI : GPL-3.0, code source https://github.com/OHF-Voice/piper1-gpl .
Vosk est Apache-2.0 : https://github.com/alphacep/vosk-api . SoundDevice est MIT : https://github.com/spatialaudio/python-sounddevice .
Les modèles sont téléchargés directement chez leurs éditeurs, pas distribués dans l’archive de Jarvis :
- Siwis français, voix féminine : données SIWIS, University of Edinburgh, CC-BY-4.0. https://datashare.is.ed.ac.uk/handle/10283/2353 ; modèle https://huggingface.co/rhasspy/piper-voices/tree/main/fr/fr_FR/siwis/medium .
- Tom français, voix masculine : Tjiho, AGPL-3.0. Source/données https://git.bksp.space/Tjiho/French-tts-model-piper ; modèle https://huggingface.co/rhasspy/piper-voices/tree/main/fr/fr_FR/tom/medium .
- Vosk small French 0.22, Alpha Cephei, Apache-2.0 : https://alphacephei.com/vosk/models .
Les empreintes vérifiées sont dans config/voice-assets.json. Les licences des composants tiers restent applicables indépendamment de celle du code original de Jarvis.
