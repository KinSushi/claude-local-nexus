# Manuel d’utilisation de Nexus

## Contexte rapide
- **Installation** : `C:\local-llm-docker`  
- **Passerelle LiteLLM** : `http://localhost:4000`  
- **60 alias de modèles** répartis en trois catégories  

| Catégorie | Exemple d’alias | Coût | Particularités |
|-----------|-----------------|------|-----------------|
| **LOCAL** | `codestral-22b-local`, `glm-4.7-flash-local`, `gpt-oss-20b-local` | Gratuit, **tout** reste sur la machine | Modèles ≥ 30 Mds param → expire après 900 s ; ne jamais les employer |
| **CLOUD** | `ollama-claude-2-cloud`, `ollama-gpt-4-cloud` | Gratuit sous abonnement | Les données **sortent** vers `ollama.com` ; OK pour code public, jamais pour secrets |
| **PAYE**  | `claude-*` | Facturation au jeton | **Jamais** utilisé ; la plateforme existe pour l’éviter |

Les outils fonctionnent depuis **n’importe quel projet** ; les chemins relatifs sont résolus depuis le répertoire courant.

Deux niveaux de réemploi. **Scripts** (sections ci-dessous) : chemin absolu + pile Docker de cette installation démarrée (`docker compose up -d` depuis `C:/local-llm-docker`), rien d’autre. **Outils MCP** (`nexus_ask` et les autres, côté Claude Code) : exigent un `.mcp.json` propre au projet appelant -- celui de cette installation référence le serveur via `${CLAUDE_PROJECT_DIR}`, relatif au projet courant, donc le copier tel quel ailleurs pointerait vers le mauvais serveur :

```json
{ "mcpServers": { "nexus-local": {
  "command": "node",
  "args": ["C:/local-llm-docker/tools/nexus-mcp/server.js"],
  "env": { "NEXUS_LITELLM_URL": "http://127.0.0.1:4000" }
} } }
```

à placer à la racine du projet appelant. La passerelle est un service partagé : plusieurs projets peuvent l’utiliser en même temps.

---

## 0️⃣ La commande `nexus`
*Si vous ne devez retenir qu'une chose, retenez celle-ci.*

Une commande unique, disponible depuis **n'importe quel répertoire**, qui
évite d'avoir à retenir les chemins absolus :

| Commande | Ce qu'elle fait |
|---|---|
| `nexus` | Monte la pile : moteur Ollama, conformité, conteneurs, passerelle. **~46 s** |
| `nexus check` | Vérifie le runtime : local, cloud et les trois routeurs |
| `nexus status` | Contrôle de conformité, sans rien démarrer |
| `nexus stop` | Arrête la pile |
| `nexus mcp` | Écrit `.mcp.json` dans le projet courant, pour y avoir `nexus_ask` & co. |
| `nexus ask "consigne" f1 f2` | Interroge le banc gratuit |
| `nexus valide --base main` | Valide **le projet courant**, sans agent ni coût |
| `nexus help` | Rappelle tout ceci |

**Vous n'avez normalement rien à lancer.** Une tâche planifiée monte la pile
à l'ouverture de votre session Windows, 120 s après — le délai laisse à
Docker Desktop le temps de démarrer. Le compte rendu est écrit dans
`logs/demarrage.log` : c'est là qu'on regarde si un démarrage a échoué.

`nexus` reste utile après un `nexus stop`, après une modification de
configuration, ou quand le démarrage automatique n'a pas fait son office.

### Installation de ces deux commodités

```powershell
.\scripts\Install-NexusCommande.ps1     # la commande `nexus` (profil PowerShell)
.\scripts\Register-NexusDemarrage.ps1   # le démarrage à l'ouverture de session
```

Chacune se retire avec `-Remove`. Les sections suivantes donnent la forme
longue, à chemin absolu, qui fonctionne sans rien installer.

---

## 1️⃣ Interroger le banc  
*Déleguer une lecture ou une analyse.*

```powershell
python "C:/local-llm-docker/scripts/nexus_agent.py" `
    --tache "Analyser la complexité du fichier src/module.py" `
    --fichiers src/module.py `
    --max-tokens 2000
```

`--modele` est facultatif. Sans lui, la requête part sur `adaptive-router`,
qui arbitre entre le local et le cloud Ollama — gratuits tous les deux, et
sans jamais atteindre un alias facturé. Deux mesures pour choisir en
connaissance de cause : son pool compte 42 candidats distincts dont **18
locaux**, parmi lesquels deux qui peuvent tenir la ligne jusqu'au délai de
900 s ; le 30 août 2026, un repli sur `qwen3-coder:30b` a rendu en **597 s**
là où la même tâche prenait **13 s** en cloud. Ce pool suit l'inventaire
local, qui n'a **aucun plafond** — 39 modèles installés ce jour-là, 33
exposés par la passerelle. Quand la latence prime sur la confidentialité, demander
`--modele adaptive-router-cloud` : 19 candidats, aucun local.

*Sortie attendue* : le rapport d’analyse s’affiche, indique le temps d’exécution et le modèle utilisé.  

**Options utiles** : `--lot lot.json --parallele 3` (tâches simultanées), `--racine <chemin>` (autre répertoire), `--temperature <valeur>` (défaut 0.2). Au‑delà de 96 000 caractères, le texte est découpé et les réponses sont fusionnées automatiquement. En cas d’échec, bascule vers un modèle **GRATUIT** (jamais PAYE).

---

## 1️⃣bis Les compétences
*Une consigne système réutilisable, désignée par son nom.*

Les fichiers vivent dans `competences/` à la racine de la plateforme : un
fichier `.txt` par compétence, une règle par ligne.

| Nom | Ce qu'elle impose |
|---|---|
| `relire-code` | ne pas affirmer l'existence d'une API sans l'avoir vue ; éprouver les cas limites ; dire « je n'ai pas pu vérifier » plutôt que combler |
| `arbitrer` | vérifier chaque prémisse ; ne jamais produire un chiffre non fourni ; rendre INDETERMINE plutôt que deviner ; énoncer la contrepartie |
| `repondre-court` | le résultat d'abord, pas de préambule ni de résumé final, sans sacrifier une nuance nécessaire |

```powershell
python "C:/local-llm-docker/scripts/nexus_agent.py" `
    --tache "Y a-t-il un défaut dans ce code ?" --fichiers src/module.ps1 `
    --competence relire-code
```

`--systeme` l'emporte si tu fournis les deux : il est plus spécifique. En
mode `--lot`, la compétence s'applique aux tâches qui ne portent pas déjà
leur propre clef `systeme` ; celles qui en ont une ne sont jamais écrasées.
Un nom inconnu affiche la liste des noms disponibles et rend le code 1.

Les compétences appartiennent à la **plateforme** : un projet tiers qui
appelle le script en hérite sans rien installer. Pour en ajouter une, dépose
un fichier `.txt` dans `competences/` — aucun code à modifier.

Ce que cela vaut, mesuré. Sur un piège réel — un découpage PowerShell
`$Reste[1..($Reste.Count-1)]` qui, sur un tableau d'un seul élément, renvoie
les indices 1 puis 0 — le modèle **sans** compétence affirme « erreur index
out of range », ce qui est faux ; **avec** `relire-code`, il écrit « je n'ai
pas pu vérifier le comportement exact sans exécution ». L'aveu remplace
l'invention. Aucun des deux ne trouve le vrai comportement : une consigne
système réduit un type d'erreur, elle ne rend pas le modèle plus capable.

---

## 2️⃣ Faire corriger un fichier  
*Le banc produit, l’outil applique.*

```powershell
python "C:/local-llm-docker/scripts/nexus_patch.py" `
    --cible src/module.py `
    --consigne brief.md
```

*Sortie attendue* : le fichier original est sauvegardé, la version corrigée est écrite, la syntaxe est vérifiée et un message indique « Correction appliquée » ou « Restauré » en cas d’erreur.  

Options : `--simuler` (affiche les changements sans écrire), `--fonctions` (pour fichiers très gros en `.py` : ne demande que les fonctions changées, appliquées via `nexus_fonctions.py`), `--triplets` (mode historique à ancres exactes, fragile au‑beyond d'environ 600 lignes, même limite que le mode par défaut), refus si plus de 40 % des lignes sont perdues.

---

## 3️⃣ Valider sans rien dépenser  
*Détection de régressions.*

```powershell
nexus valide
# ou, sans la commande courte :
python "C:/local-llm-docker/scripts/nexus_valide.py"
```

*Sortie attendue* : code de retour 0 → rien à signaler, 1 → défaut trouvé, 2 → le banc n’a pu répondre (cas où un modèle PAYE pourrait être envisagé). Le script analyse le travail **non commité** par défaut.

La validation porte sur le **projet courant**, pas sur la plateforme : la
racine est prise dans `NEXUS_WORK_ROOT`, sinon `CLAUDE_PROJECT_DIR`, sinon le
dépôt git contenant le répertoire d'où vous appelez.

Le verdict vient du banc gratuit, et **il n'est pas déterministe** : sur
quatre passages d'un même diff, trois ont conclu à l'absence de régression et
un à l'inverse. Un passage est un signal, pas une preuve — sur un point qui
compte, relancez.

---

## 4️⃣ Traiter plusieurs fichiers d’un coup  
*Audit + correction + vérification en parallèle.*

```powershell
python "C:/local-llm-docker/scripts/nexus_essaim.py" `
    --cibles a.py b.py c.ps1 `
    --plans deux `
    --parallele 4
```

*Sortie attendue* : chaque cible est traitée, un résumé indique le nombre de fichiers corrigés et les éventuels échecs. `--plans deux` lance simultanément le cloud et le local ; les secrets restent toujours en **LOCAL**.

---

## Combien d’essaims lancer ?  

| Scénario | Essaims | Temps total | Gain |
|----------|--------|------------|------|
| 6 cibles, 2 lots | 1 | 293 s | – |
| 6 cibles, 2 lots | 3 | 226 s | **1,30×** |
| 9 cibles, 3 lots | 1 | 465 s | – |
| 9 cibles, 3 lots | 3 | 398 s | **1,17×** |

**Règle pratique basée sur les mesures**  
- **Mode CLOUD** : jusqu’à **3 essaims**, le temps d’exécution reste celui d’un **seul** appel — le parallélisme y est donc gratuit, trois cibles coûtent le temps d’une. Au‑delà, le temps augmente ; le gain se dégrade (ex. 6 appels → ratio 1,35).  
- **Mode BIPLAN ou LOCAL** : le **plan local** plafonne déjà dès le **2ᵉ appel simultané** (ratio ≈ 1,36) et n’obtient plus d’accélération supplémentaire avec plus d’essaims (3 appels → ratio ≈ 1,37).  
- Le critère de choix n’est donc pas le nombre d’essaims mais le **plan** : pour la vitesse pure, utilisez le cloud avec ≤ 3 essaims ; pour la confidentialité, acceptez le plafond local et ne cherchez pas à le contourner par la concurrence.

**Goulot d’étranglement**  
Les mesures montrent que le facteur limitant est **la machine locale** (CPU, mémoire, I/O). Ni le compte Ollama Cloud ni la passerelle LiteLLM ne constituent le goulot. Aucun échec n’a été observé, donc aucune limite de quota n’est atteinte.

---

## ⚡ Gros corpus : ce que coute chaque stratégie

Au-delà de 96 000 caractères, le texte est découpé en fenêtres analysées
séparément (MAP), puis fusionnées (REDUCE). Les fenêtres étant indépendantes,
elles peuvent partir sur plusieurs plans à la fois.

Mesures du 30 août 2026, même corpus de 221 334 caractères, même délai par
fenêtre :

| Stratégie | Durée | Commentaire |
|---|---|---|
| Cloud seul | **191 s** | référence |
| Plan local seul | **687 s** | 3,6× plus lent |
| Part fixe 3:2 entre les plans | **268 s** | +40 % — le lot attend le plan lent |
| **File commune** | **192 s** | cloud 3 fenêtres, local 1 |

C'est la file commune qui est employée. Chaque ouvrier prend la fenêtre
suivante dès qu'il est libre : le plan rapide en traite naturellement
davantage. Connaissant 191 et 687, le partage optimal tournait autour de
78 % au cloud ; la file en a donné 75 %, **sans qu'aucun ratio ne lui soit
soufflé**.

Deux conséquences pratiques :

- **Rien à régler.** Un ratio écrit dans le code vieillirait à chaque
  changement de machine, de modèle ou de charge. Une file s'ajuste seule.
- **Un plan qui tombe ne bloque rien.** L'autre vide la file sans qu'aucune
  règle ne l'ait prévu, et les fenêtres perdues sont relancées une fois sur
  les plans restants.

Le délai par fenêtre vaut **180 s**, contre 900 s pour un appel isolé
(`NEXUS_MAP_TIMEOUT` pour le changer). La logique s'inverse entre les deux :
seul, mieux vaut attendre qu'échouer ; dans un MAP, le résultat n'arrive
qu'à la dernière fenêtre, donc une traînarde immobilise tout le lot.

En mode `local_seul`, aucune fenêtre ne part en cloud : répartir un corpus
sensible serait une fuite, pas une optimisation.

---

## 5️⃣ Couvrir tout un dépôt sans lister les fichiers à la main
*Découverte automatique + plusieurs essaims concurrents.*

```powershell
python "C:/local-llm-docker/scripts/nexus_ruche.py" `
    --essaims 2 `
    --taille-lot 3 `
    --plans cloud
```

*Sortie attendue* : découvre les cibles éligibles du dépôt (`scripts/*.py`, `scripts/*.ps1`, `*.ps1` racine, `tools/nexus-mcp/*.js`), les traite par lots concurrents via `nexus_essaim.py`, et affiche un rapport avec la durée réelle, le nombre de cibles abouties/en échec, et la cause précise de chaque échec.

**Options utiles** : `--max-cibles N` (plafonne le volume traité par cette exécution -- sans lui, une invocation couvre tout le dépôt découvert, quels que soient `--essaims`/`--taille-lot`, qui ne bornent que la concurrence) ; `--tout-refaire` (ignore le journal `.nexus/ruche-etat.json` et retraite tout) ; `--simuler` (aucun sousprocessus, aucun coût). Une cible déjà « ok » dans le journal est sautée à l'exécution suivante : plusieurs invocations successives couvrent progressivement le dépôt.

---

## 📊 Mesurer ce que cela rapporte  
```powershell
python "C:/local-llm-docker/scripts/nexus_savings.py" `
    --jours 7
```
Affiche la part de travail déléguée et le coût évité. **À lancer dès le premier jour** d’un nouveau projet ; sans mesure initiale, on ne sait jamais si le dispositif tient ses promesses.

---

## 📋 Choisir le plan  

| Situation | Plan recommandé |
|----------|----------------|
| Code **public** (exemple : bibliothèque open‑source) | **CLOUD** (modèles gratuits, données publiques) |
| Code contenant **secrets** ou données clients | **LOCAL** (tout reste sur la machine) |
| Tâche nécessitant un **modèle haut de gamme** (ex. génération de design complexe) | **CLOUD** (modèles les plus performants parmi les gratuits) |

Le critère principal est **l’exposition des données**, pas la puissance brute.

---

## 🔒 Quand une cible sensible echoue

Une cible dont le nom porte un indice de secret — `preserve`, `secret`,
`env`, `cle`, `key`, `auth` — est traitee sur le plan **local**, et
desormais **verrouillee** sur ce plan : si le modèle local expire, le repli
gratuit ne bascule plus vers le cloud. La tâche échoue.

C'est voulu. Avant ce verrou, la même cible était servie par
`gpt-oss-120b-cloud` : les données sortaient de la machine, et rien ne le
signalait. Mesure comparative du 30 août 2026, sur `nexus_preserve.py` :

| | Modèle servi | Résultat |
|---|---|---|
| Avant | `gpt-oss-120b-cloud` | `ok` — les données sont sorties |
| Après | `codestral-22b-local` | `echec` — « tous les replis gratuits ont echoue » |

La contrepartie est réelle : la cible n'est plus traitée du tout. Les deux
replis locaux ont expiré en HTTP 408. Le plan local est fragile, et le
verrou rend cette fragilité visible au lieu de la compenser par une sortie
de données. Un échec se voit ; une fuite non.

Si la cible n'est en réalité pas sensible, renommez-la ou passez
`--plans cloud` explicitement.

---

## ⚠️ Ce qui peut mal se passer  

1. **Réponse vide** : le modèle a atteint son plafond de tokens. Augmentez `--max-tokens` plutôt que de conclure à une incapacité.  
2. **Temps de chargement long** : un modèle local « à froid » peut mettre jusqu’à deux minutes à se charger ; ce n’est pas une panne.  
3. **Hallucinations plausibles** : les modèles peuvent produire du code qui semble correct mais est faux. **Vérifiez toujours** chaque modification dans le code réel avant de l’adopter.

---  
Utilisez ces blocs tel quel, copiez‑collez dans votre terminal PowerShell et adaptez les chemins/arguments à votre projet. Aucun remplissage inutile : chaque commande est prête à l’emploi.
