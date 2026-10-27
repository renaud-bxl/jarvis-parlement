# Validation de JARVIS 3.0.2 candidate

## Vérifié dans l’environnement Linux de construction

- 56 tests unitaires réussis, dont les 17 tests de non-régression V2.
- Conversation : commandes françaises, reformulations via plan IA limité, choix de compte, sujet manquant, modèle Word requis, mémoire privée, blocage des recherches et plannings publics après données privées, annulation, confirmation à usage unique, refus de requêtes concurrentes.
- SMTP : validation des en-têtes et destinataires, octets identiques à la prévisualisation, confirmation native, annulation sans envoi.
- Mise à jour : comparaison de versions, refus d’une URL extérieure au dépôt, empreinte invalide, archive avec traversée de chemin ; ouverture de l’installateur validée avec un processus simulé.
- Audio réel : Piper 1.8.0 a synthétisé une phrase française avec Siwis (5,18 s) et Tom (6,55 s). Vosk small-fr 0.22 a retranscrit correctement, pour les deux voix : « bonjour je suis jarvis peux-tu lire mes mails et préparer une veille sur le logement à bruxelles ». Ce test sur audio synthétique ne mesure pas les accents, le bruit ambiant ou un microphone réel.
- Interface : contrôle visuel dans Chromium avec pont natif simulé ; accueil, commande mails, affichage de la réponse, confirmation de planning, panneau de mise à jour, sélection de voix, message d’erreur audio.
- Syntaxe Python, JavaScript et shell ; contenu ZIP et empreinte du paquet.
- Les tests V2 couvrent encore les exports des trois modèles DOCX, l’identité personnalisée, l’index local et la restauration du planning en cas d’erreur.

## Validation macOS automatisée

Le workflow GitHub Actions du commit 605073ac8273e9db34c5327c94f1fe92b52e0fdc (3.0.0) a réussi sur macos-latest : installation des dépendances complètes, imports natifs et interface OpenJarvis, 42 tests de régression, syntaxe et contrôle SHA-256. Résultat : https://github.com/renaud-bxl/jarvis-parlement/actions/runs/40588307642 . La version 3.0.1 ajoute deux tests de continuité de conversation ; le workflow est relancé à chaque publication. Ce runner ne teste ni une session utilisateur interactive ni un microphone réel.

## À valider sur un Mac et des comptes de test

- Installation complète sur Mac vierge et mise à jour V2 → V3, Apple Silicon et Intel ; lancement réel Cocoa/WebKit et permission microphone.
- Capture microphone, lecture afplay, arrêt pendant synthèse, changement de périphérique audio ; qualité des voix à l’écoute.
- Connexion ChatGPT réelle, éligibilité et autorisation du forfait, modèles retournés, renouvellement ; API OpenAI/Claude. Aucun jeton ni clé réel n’est fourni au paquet.
- Gmail/IMAP/Calendar réels et envoi SMTP à une boîte de test après confirmation. Aucun courrier réel n’a été envoyé pendant la construction.
- Déclenchement launchd, passage de veille du Mac, restauration d’une sauvegarde et installation d’une future version depuis le bouton intégré.

## Limites de distribution

Le paquet contient des sources Python/JS et un lanceur .app ; il est assemblé, pas compilé ni notarié sur un Mac. La signature et la notarisation Apple restent absentes. Un avertissement système peut apparaître. Les comptes externes sont simulés dans les tests de logique : un test réussi ne prouve pas la disponibilité de leur service ni les permissions d’un compte. Le ZIP reste une version candidate, pas une certification de fonctionnement sur toutes les machines.

## Correctif 3.0.2 : diagnostics fournisseurs

Douze nouveaux tests couvrent les erreurs de flux ChatGPT, HTTP, OAuth et API, la conservation du code de cause, la séparation des quotas et des limites de sortie, la fin de flux sans ligne vide finale, les réponses malformées, les causes inconnues et l’absence de secrets dans le diagnostic persisté. Les 56 tests passent localement. La CI macOS est relancée sur le commit publié.

Le message générique d’une ancienne version ne permet pas de reconstruire la cause réelle a posteriori. Reproduire l’échec avec 3.0.2 et consulter/copier le diagnostic. Aucun correctif de quota ou de compte personnel n’est revendiqué sans cette preuve.

## Correctif 3.0.3 : lecture vocale des courriers
61 tests locaux réussis, dont le nettoyage de l’exemple Markdown échappé, la conservation des libellés français, les annonces distinctes, l’isolation des courriers et l’absence d’appel IA si la boîte est vide. Chaque synthèse utilise Ollama sans recherche web. Le nettoyage s’applique à tous les appels vocaux, automatiques et manuels. L’écoute sur le Mac de l’utilisateur reste à vérifier.

## Correctif 3.0.4 : choix du modèle et test
65 tests locaux réussis. Le test transmet le fournisseur et le modèle actuellement sélectionnés sans modifier les réglages enregistrés. Sélection vide et fournisseur inconnu refusés ; le diagnostic conserve le modèle effectivement testé. Contrôle navigateur avec un connecteur simulé : huit options visibles, huitième modèle sélectionné et transmis sans enregistrement. Ce contrôle ne valide pas une génération avec le compte personnel de l’utilisateur.

## Correctif 3.0.5 : modèles retirés et clé saisie
69 tests locaux réussis. GPT-4o reste dans la liste quand l’API le renvoie. Les modèles arrêtés (notamment GPT-3.5 Turbo au 23 octobre 2026) sont écartés ; shutdown_date de l’API est pris en compte. Les variantes audio/image ne sont pas proposées pour le connecteur texte. Un ancien GPT-3.5 enregistré produit une explication avant toute requête. La clé encore présente dans le formulaire bloque chargement et test tant qu’elle n’est pas enregistrée, pour éviter l’utilisation silencieuse d’une ancienne clé.
Source des retraits : https://developers.openai.com/api/docs/deprecations (vérifiée le 27 octobre 2026).

## Version 3.0.6 : courriers
78 tests locaux réussis, dont HTML seul, retrait des scripts et ressources distantes, image CID intégrée, Reply-To et Message-ID, réponse avec références, ajout de fichiers à un courrier ou à un EML multipart existant, conservation des octets approuvés, limite du nombre de pièces et rejet d’injection d’en-tête. Correction également d’un rejet des destinataires lorsque Cc était vide.
Contrôle navigateur avec messages synthétiques : titres et tableau HTML rendus dans un iframe isolé, bouton Répondre, destinataire Reply-To et objet préremplis, compte SMTP distinct. Aucun mail réel envoyé lors de la validation ; transport et rendu WebKit sur le Mac utilisateur restent à confirmer.
