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

## 1️⃣ Interroger le banc  
*Déleguer une lecture ou une analyse.*

```powershell
python "C:/local-llm-docker/scripts/nexus_agent.py" `
    --tache "Analyser la complexité du fichier src/module.py" `
    --fichiers src/module.py `
    --modele gpt-oss-120b-cloud `
    --max-tokens 2000
```

*Sortie attendue* : le rapport d’analyse s’affiche, indique le temps d’exécution et le modèle utilisé.  

**Options utiles** : `--lot lot.json --parallele 3` (tâches simultanées), `--racine <chemin>` (autre répertoire), `--temperature <valeur>` (défaut 0.2). Au‑delà de 96 000 caractères, le texte est découpé et les réponses sont fusionnées automatiquement. En cas d’échec, bascule vers un modèle **GRATUIT** (jamais PAYE).

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
python "C:/local-llm-docker/scripts/nexus_valide.py"
```

*Sortie attendue* : code de retour 0 → rien à signaler, 1 → défaut trouvé, 2 → le banc n’a pu répondre (cas où un modèle PAYE pourrait être envisagé). Le script analyse le travail **non commité** par défaut.

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

## ⚠️ Ce qui peut mal se passer  

1. **Réponse vide** : le modèle a atteint son plafond de tokens. Augmentez `--max-tokens` plutôt que de conclure à une incapacité.  
2. **Temps de chargement long** : un modèle local « à froid » peut mettre jusqu’à deux minutes à se charger ; ce n’est pas une panne.  
3. **Hallucinations plausibles** : les modèles peuvent produire du code qui semble correct mais est faux. **Vérifiez toujours** chaque modification dans le code réel avant de l’adopter.

---  
Utilisez ces blocs tel quel, copiez‑collez dans votre terminal PowerShell et adaptez les chemins/arguments à votre projet. Aucun remplissage inutile : chaque commande est prête à l’emploi.
