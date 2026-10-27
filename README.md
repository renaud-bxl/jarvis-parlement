# JARVIS – PARLEMENT

Application macOS pour préparer des recherches, interpellations, briefings, synthèses de courriers et documents parlementaires. Version 2.0.0 candidate, destinée à une première validation sur Mac.

## Installer

Décompresser `Jarvis-Parlement-2.0.0-macOS.zip`, puis ouvrir **Installer Jarvis Parlement.app**. L'installateur crée **Jarvis Parlement.app** dans `~/Applications`. Il détecte les composants présents, conserve les comptes et documents du kit V1, sauvegarde les réglages et reprend le planning existant, dont 10 h 30 lorsqu'il était configuré.

macOS 14 minimum, Apple Silicon ou Intel ; connexion Internet pendant l'installation. Plusieurs gigaoctets peuvent être nécessaires pour Python, Ollama, un modèle local et LibreOffice. Aucun `sudo`. La distribution n'est pas signée ni notariée Apple ; une autorisation d'ouverture peut être requise. Ne pas désactiver Gatekeeper.

L'installation graphique prend en charge les dépendances. Les autorisations Google/ChatGPT restent des actions personnelles dans le navigateur. Google nécessite un client OAuth de bureau fourni par l'utilisateur ou son organisation.

## Parcours

1. Recherche web et projet parlementaire.
2. Analyse d'un document local sans recherche web.
3. Briefing du jour et planning.
4. Lecture et synthèse locale des boîtes mail.
5. Prévisualisation d'un `.eml` et envoi SMTP après double validation.
6. Configuration et profil de rédaction.
7. Indexation locale.
8. Recherche textuelle dans l'index.
9. Diagnostic.
10. Connexion native Google Calendar en lecture seule.
11. Désactivation du briefing automatique.

L'application comprend aussi des templates par parlement, les rapports Word/PDF/texte, un tour guidé, un manuel complet, la lecture vocale macOS et le transfert manuel vers les applications ChatGPT/Claude installées.

## Identité et templates

Chaque installation commence avec une identité vide. Le nom complet du parlementaire est obligatoire avant rédaction. Sa fonction, son institution et sa langue complètent le profil ; le collaborateur est un champ distinct. Aucun mandat n'est attribué automatiquement.

Trois modèles bruxellois sont fournis avec des champs variables, sans les sujets, destinataires ni signatures manuscrites des exemples originaux. Aucun n'est actif par défaut. Les imports `.docx` et `.doc` permettent de définir une zone à remplacer. Le reste du document est conservé. Les modèles d'autres assemblées doivent être fournis et contrôlés par l'utilisateur. Voir le manuel pour les marqueurs reconnus et limites des zones de texte/tableaux.

## IA et confidentialité

- **Ollama local** : sans clé ; modèle existant conservé ou modèle de démarrage téléchargé. Les modèles Ollama cloud sont refusés.
- **Compte ChatGPT** : flux OAuth officiel « Continue with ChatGPT », pour les comptes éligibles. Aucun jeton n'est extrait de l'app installée.
- **OpenAI / Claude API** : clé personnelle au Trousseau macOS et facturation propre au fournisseur.
- **Apps ChatGPT / Claude** : copie et ouverture de l'app, puis import manuel de la réponse.

Les mails sont résumés localement même si les recherches utilisent une IA cloud. L'analyse de documents privés par une IA cloud exige l'option correspondante. Un document privé ou un historique privé bloque la recherche web. Les réponses de l'IA ne déclenchent aucun envoi de courrier.

Paramètres : `~/.config/jarvis-parlement`. Rapports : `~/Documents/Jarvis-Parlementaire`. Secrets : Trousseau macOS. Versions et sauvegardes : `~/Applications/Jarvis-Parlement`. Les index et rapports ne bénéficient pas d'un chiffrement applicatif supplémentaire.

## Documentation et validation

Le manuel se trouve dans l'application, rubrique **Mode d'emploi**, et dans `ui/manual.html`. `VALIDATION.md` distingue les vérifications effectuées de celles encore nécessaires sur un vrai Mac. Cette version n'a pas encore été validée de bout en bout avec des comptes réels sur macOS.

Tests portables :

```sh
python3 -m pip install python-docx
python3 -m unittest discover -s tests -v
```

Création du paquet :

```sh
python3 -m pip install Pillow
python3 tools/build_release.py
```

Le paquet contient le code Python et JavaScript lisible. Les versions réellement installées sont consignées dans `installed-versions.txt`. Le fichier `requirements.txt` fixe OpenJarvis et borne les principales dépendances ; il ne constitue pas un verrouillage transitif complet.

## Sources techniques

- https://open-jarvis.github.io/OpenJarvis/
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://docs.ollama.com/macos
- https://pywebview.flowrl.com/guide/installation.html
- https://developers.google.com/workspace/gmail/api/quickstart/python
- https://developers.google.com/workspace/calendar/api/quickstart/python

Voir `NOTICE.md` pour les composants tiers et les modèles institutionnels.
