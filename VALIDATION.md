# Validation de la version 2.0.0 candidate

## Effectué dans l'environnement Linux de construction

- 17 tests automatisés réussis : migration du profil/modèle/comptes et planning à 10 h 30 ; refus des données privées dans la recherche web ; consentement cloud ; exclusion des modèles Ollama distants ; synthèses mail locales, y compris dans le briefing ; index/recherche ; confinement des fichiers de rapports ; validation des en-têtes EML ; octets envoyés identiques à la prévisualisation ; confirmation et nonce à usage unique ; restauration après échec du planning ; contrôle des liens et de l'émetteur OAuth.
- Trois exports DOCX de contrôle, avec une identité fictive différente de celle des exemples, rendus en PDF et inspectés visuellement. Marges conservées, un seul logo incorporé, aucune image de signature restante, champs variables remplacés.
- Compilation Python, analyse syntaxique JavaScript et Bash, cohérence des identifiants HTML, intégrité du ZIP et permissions des lanceurs.

## À valider sur macOS avant diffusion générale

- Installation complète depuis le Finder sur Apple Silicon et Intel, nouveau Mac puis mise à jour du kit V1 ; reprise après interruption réseau.
- Ouverture de la fenêtre Cocoa/WebKit, interactions, tour guidé, rendu adaptatif, dictée et synthèse vocale.
- Téléchargement du modèle, comportement réel d'OpenJarvis et recherches avec chaque fournisseur choisi.
- OAuth ChatGPT, rotation/révocation des jetons, Google Gmail/Calendar, Trousseau verrouillé ou autorisations d'entreprise.
- Lecture réelle IMAP/Gmail, SMTP vers une boîte de test après validation, launchd à l'heure voulue, restauration d'une sauvegarde.
- Conversion des anciens fichiers `.doc` et exports PDF avec LibreOffice macOS.

Aucun courrier réel n'a été envoyé. Aucun compte réel ni clé n'a été incorporé au paquet. Les fournisseurs et autorisations externes ont été simulés dans les tests de logique ; leur disponibilité n'est pas prouvée par ces tests.

L'installation et les applications ne sont pas signées/notariées Apple. Le fonctionnement « un clic » sans avertissement système nécessite une distribution signée et notariée avec un compte développeur Apple. La version livrée reste une candidate à tester sur le Mac de destination.
