# PLAN MAÎTRE — 2026-09-01

> Demandé par l'opérateur : *« tu fais un plan complet, tu utilises les ia locales
> pour code ou embeddings ou le cloud, tu peux mixer. mais d'abord le grand plan
> pour t'y retrouver. ensuite tu enchaînes les déploiements massifs via cloud et
> local. »*
>
> Ce document est **l'arbitrage** — la seule chose que l'orchestrateur produise
> lui-même (§0). Tout ce qu'il ordonne se délègue.

---

## 0. LA RÈGLE QUI ORDONNE TOUT LE RESTE

Un chantier n'est pas clos quand il est expliqué. Il est clos quand **un contrôle
échoue si la règle est enfreinte** (§0.2.1). Chaque tâche ci-dessous porte donc sa
colonne « ce qui la ferme », et aucune ne se ferme sur un paragraphe.

Et le cycle à trois temps (§0.7.1) s'applique à chacune :

    1. AUDIT        un tiers
    2. CORRECTION   un tiers, jamais le même
    3. AUDIT DE LA CORRECTION   un tiers, jamais l'auteur du 2   ← celui qu'on saute

**Le maillon 3 est disponible et il fonctionne** : la session `sovereign-ai-system-e0`
a joué ce rôle ce soir sur `controle_secrets_documentes` et a rendu un verdict
CONFORME assorti d'une réserve que ni le banc ni moi n'avions vue. C'est la
ressource la plus rare de tout ce plan — un auditeur qui n'a écrit ni le
diagnostic ni le patch, et qui mesure au lieu de raisonner.

---

## 1. ÉTAT MESURÉ CE SOIR — ce sur quoi le plan s'appuie

### 1.1 Sécurité : la campagne complète, 124 épreuves, 0 échec mécanique

| Famille | Ce qu'elle prouve | Résultat |
| --- | --- | --- |
| `policy` | aucun repli ne réduit la confidentialité | 23 replis, tous vers le local, 0 vers l'extérieur |
| `fuite` | pas de `local → cloud` | 5/5 |
| `reverse` | les chemins interdits échouent proprement | 15/15 |
| `verrou` `isolation` `lecture` `shell` `shellps` `quote` `cibles` `plan` `accord` `couverture` `vitrine` | gardes et ACL | 0 échec |
| détecteur de secrets | forward **et** reverse | 4 détectés / 3 silences corrects |

Deux gardes ont mordu **pendant** la campagne : l'ACL a refusé la lecture de
`.env`, et `nexus_agent` a refusé de joindre `.env.example` au banc. Aucun port
n'est publié hors de `127.0.0.1` (11435 et 4000).

### 1.2 Un défaut bloquant, corrigé et prouvé dans les trois temps

`nexus_conformite.py` exigeait `REDIS_PASSWORD` en BLOQUANT alors que la variable
avait été retirée de `.env.example` : **toute installation neuve suivant la
procédure documentée échouait au démarrage**, sur un secret qui ne protège rien
(Redis tourne sans mot de passe — décision assumée de l'opérateur — et n'est
publié sur aucun port de l'hôte). Quatre chemins en dépendaient :
`start.ps1:201`, `Update-NexusModels.ps1:198`, `nexus_vitrine.py:260`,
`nexus_valide.py:191`.

    AUDIT        gpt-oss-120b-cloud
    CORRECTION   deepseek-v4-pro-0813-cloud
    AUDIT 3      qwen3.5-397b-cloud (raisonné) PUIS sovereign-ai-system-e0 (mesuré)

Fermé par un contrôle neuf, `controle_secrets_documentes`, qui échoue si un
secret exigé n'est pas documenté dans `.env.example` — donc le défaut ne
reviendra pas avec le **prochain** secret. Prouvé capable de rougir par un tiers,
et prouvé ne divulguant aucune valeur.

### 1.3 Les ressources, mesurées et non recopiées

| Ressource | Mesure | Où |
| --- | --- | --- |
| corpus documentaire | **33 771 fichiers** — 5810 txt, 4886 html, 3436 js, 2245 json, 1834 notebooks, 452 pdf, 1480 mp4, 231 md | `D:/EA MT5 .../docs` |
| dépôt SAS | **40 310 .md**, 11 215 .py, 10 135 .json, 1 922 .js | `D:/SAS/sovereign-ai-system/v1.104/...` |
| modèles locaux résidents | **53** | `ollama list` |
| catalogue cloud accessible | **19 modèles** | console Ollama |
| index documentaire du dépôt | 166 507 symboles Python + 24 073 annexes | `nexus_doc.py` |

**Ces deux corpus n'ont jamais été exploités.** C'est le plus grand écart entre
ce dont dispose la plateforme et ce qu'elle emploie.

---

## 2. LES CINQ CHANTIERS, PAR ORDRE

L'ordre n'est pas arbitraire : **C1 conditionne tout le reste**, parce qu'un banc
dont les rendus vides se lisent comme des succès rend toute délégation massive
non fiable. Déployer massivement avant de fermer C1, c'est industrialiser un
canal qui ment.

---

### C1 — LE CANAL DE RETOUR — *prioritaire absolu*

**La classe de défaut, énoncée par sovereign et vérifiée** : dans chaque cas, le
mécanisme fonctionne et c'est le **retour** qui manque. Un outil dont le silence
ressemble à un feu vert coûte plus cher qu'un outil qui échoue bruyamment.

La mesure qui donne son enjeu au chantier — `nexus_compare`, consigne triviale
« écris les entiers de 1 à 60 », `max_tokens: 300` :

| Modèle | Temps | Jetons | Rendu |
| --- | --- | --- | --- |
| `gpt-oss-120b-cloud` | 1.2 s | 407 | **VIDE** après retrait du raisonnement |
| `mistral-large-3-675b-cloud` | 2.2 s | 215 | complet et exact — **le seul** |
| `glm-5.3-flash-cloud` | 1.3 s | 357 | tronqué à 26 nombres |
| `qwen3-8b-local` | 52.9 s | 357 | **VIDE** après retrait du raisonnement |

**Trois sur quatre échouent sur ce qu'un script de trois lignes fait.** Et le
point qui renverse l'intuition : le seuil **ne dépend pas de la difficulté**.
Le même `gpt-oss-120b-cloud` rend vide sur « 1 à 60 » avec 300 jetons, et produit
sans faute un fichier Python de 360 lignes avec 7000. Ce n'est pas « la tâche
était trop dure », c'est « le budget était trop petit pour que le raisonnement
laisse la place ».

| # | Tâche | Ce qui la ferme |
| --- | --- | --- |
| **C1.1** | Exposer `max_tokens` dans le schéma MCP de `nexus_summarize` et `nexus_context` | une épreuve qui appelle l'outil avec un budget explicite et vérifie qu'il est honoré |
| **C1.2** | **Distinguer trois états dans tout rendu** : complet / tronqué / **vide par épuisement du budget en raisonnement**. `nexus_compare` sait déjà les distinguer — `summarize` et `context` non | une épreuve qui force chacun des trois états et vérifie que le libellé diffère |
| **C1.3** | Plancher ou avertissement sous le seuil où les modèles à raisonnement étendu rendent vide. Le message existe déjà côté script (« plafond insuffisant : demande 4000 jetons ») mais pas côté MCP | une épreuve qui demande un budget sous le plancher et exige l'avertissement |
| **C1.4** | Rendre le **partiel** plutôt qu'une section vide : une réponse coupée est exploitable, une section vide se lit « rien à signaler » | une épreuve sur un rendu tronqué qui exige un contenu non vide |
| **C1.5** | `nexus_garde_agent` : écrire le motif sur **stderr** avant de sortir en 2, en gardant le JSON sur stdout | une épreuve qui capture stderr et exige le motif |
| **C1.6** | Libellé « Aucun fragment pertinent » de `nexus_context` : se lit comme un verdict sur le contenu, signifie « je n'ai rien produit » | une épreuve sur un corpus non vide qui exige un libellé non ambigu |
| **C1.7** | `--sortie` écrit un JSON dans un fichier nommé `.md`. Ajouter `--sortie-brute` qui écrit le champ `texte` seul | une épreuve qui vérifie que le fichier produit est directement exploitable |
| **C1.8** | Le saut de ligne final est perdu systématiquement → `W292` sur chaque fichier appliqué | une épreuve qui applique un rendu et passe `ruff` sans `W292` |

> C1.1 seul **ne suffit pas** : l'appelant qui découvre `max_tokens` le règlera au
> plus juste pour économiser, et c'est exactement le geste qui produit le vide.
> C1.2 et C1.3 sont ce qui rend C1.1 utile.

---

### C2 — LES GARDES : PORTÉE ET CÂBLAGE

**Mesuré des deux côtés** (ici et depuis le dépôt SAS) :

    C:/Users/dibac/.claude/settings.json      nexus_garde_agent  ARMÉ GLOBALEMENT
    <local-llm-docker>/.claude/settings.json  nexus_garde_agent + nexus_garde_shell
    <dépôt SAS>/.claude/settings*.json        nexus_garde_shell  ABSENT PARTOUT

`nexus_garde_agent` juge les sessions des autres dépôts — sovereign s'est fait
refuser un dépêche ce soir. `nexus_garde_shell` ne juge que sa propre maison.
Or **la mutilation de commandes shell frappe tous les dépôts**, pas seulement
celui qui héberge le garde.

| # | Tâche | Ce qui la ferme |
| --- | --- | --- |
| **C2.1** | **DÉCISION OPÉRATEUR REQUISE** — déclarer `nexus_garde_shell` dans le settings global. C'est le fichier de configuration de l'opérateur, la portée d'un garde sur tous ses dépôts est sa décision, et un pair ne peut pas l'autoriser | un contrôle qui compare la portée déclarée à la portée voulue |
| **C2.2** | **CORRIGÉ : `nexus_garde_isolation.py` EST armé globalement** — je ne l'avais cherché que dans le settings du projet. Reste vrai : `nexus_armer_hook.py`, seul outil qui le référence, est orphelin (`nexus_cablage` le signale, code 1) | ~~le cliquet repasse à 0 orphelin~~ — **condition refusée par l'audit tiers** : elle se satisfait aussi bien en RETIRANT le script qu'en le câblant. La bonne condition est : *un hook ou un contrôle appelle réellement `nexus_armer_hook.py`* |
| **C2.3** | Chemin absolu en dur `C:/local-llm-docker/...` dans `nexus_armer_hook.py:123`. **Nuance** : un hook global DOIT porter un chemin absolu ; le défaut est de le **graver** au lieu de le dériver de `__file__` à l'écriture | une épreuve qui lance l'armeur depuis un autre répertoire et vérifie le chemin écrit |
| **C2.4** | **Protocole de refus divergent** : `garde_shell` fait `exit(0)` + `hookEventName` ; `garde_agent` fait `exit(2)` **sans** ce champ, et son commentaire affirme qu'un `exit(0)` « ne bloquait rien ». L'un des deux se trompe | une épreuve qui, sur un garde ARMÉ, vérifie séparément (a) la commande ne s'exécute pas (b) le motif arrive |
| **C2.5** | Aucun contrôle ne vérifie la **présence** de `.env.example` — donc le supprimer désarme `controle_secrets_documentes` en silence (IGNORE, ni vert ni rouge). Réserve levée par sovereign | un contrôle qui échoue si `.env.example` disparaît |

> C2.4 ne se mesure que sur un garde **effectivement armé**. L'épreuve de
> sovereign a été déclarée **nulle** par son propre auteur : la commande est
> passée parce qu'aucun hook ne la jugeait, pas parce que l'`exit(0)` serait
> inerte. Une épreuve qui ne mesure pas ce qu'on croit est pire qu'une épreuve
> absente.

---

### C3 — LE REGISTRE DES MODÈLES : UN QUATRIÈME ÉTAT

Le contrat distingue (§6) *installé* ≠ *déclaré* ≠ *exposé*. Le catalogue Ollama
Cloud est un **quatrième état que le contrat ne nommait pas** : un modèle peut
être autorisé par l'abonnement sans apparaître dans `ollama list`.

    ollama cloud search   →  Error: unknown command "cloud"    (mesuré)
    ollama list           →  53 modèles locaux + 3 refs cloud   (mesuré)
    console Ollama        →  19 modèles cloud accessibles       (mesuré)

Source complète et ses autocorrections : `rituels/VERBATIM_2026-09-01_CATALOGUE_OLLAMA.md`.

| # | Tâche | Ce qui la ferme |
| --- | --- | --- |
| **C3.1** | **Trancher `qwen3.5-397b-cloud`.** Le dépôt le déclare (`litellm_config.yaml:984`) et route dessus ; la source doute de son existence. Soit il répond, soit **un routeur pointe dans le vide depuis un temps inconnu**. Une seule requête réelle tranche | l'épreuve d'habilitation existante (§105.3) couvre le cas si elle est jouée sur cet alias |
| **C3.2** | Éprouver un par un les identifiants `*:cloud` de la seconde passe avant toute écriture dans le YAML (§39 : ne jamais inventer un modèle — la source s'est déjà trompée une fois) | `Test-NexusConfig.ps1` refuse toute référence pendante |
| **C3.3** | Nommer le quatrième état dans le contrat §6 et le rendre interrogeable | un contrôle qui compare catalogue cloud, déclaré et exposé |
| **C3.4** | Matrice de capacités Local × Cloud × Anthropic — mais **par mesure**, pas par classement recopié : §76 impose DISCOVERED → REGISTERED → HEALTHY → BENCHMARKED → CANARY → PRODUCTION | un modèle n'entre en pool que sur relevé, jamais sur réputation |

---

### C4 — LE PLAN LOCAL EST INMESURABLE AUJOURD'HUI

`nexus_profile` : *« Offload GPU : non — inférence en RAM système »*, iGPU 2,1 Go.
`qwen3-8b-local` (5,2 Go, l'un des plus petits) met **52,9 s** là où le cloud met
1,2 à 2,2 s — 24 à 44 fois plus lent.

**Mais cette mesure ne vaut rien telle quelle**, et sovereign l'a dit lui-même :
aucun modèle n'était chaud, donc une part inconnue de ces 52,9 s est le
chargement des poids — et **rien ne permet de la séparer**, puisque aucun outil
ne précharge. C'est exactement l'erreur que le contrat corrige au §107.3 : le
chargement imputé au modèle le condamne à tort.

| # | Tâche | Ce qui la ferme |
| --- | --- | --- |
| **C4.1** | `nexus_preload` — charger un alias et rendre la main, pour que le coût soit payé **une fois, explicitement**, avant une série d'appels. `nexus_models` annonce « aucun modèle chaud » sans offrir de quoi en chauffer un | une épreuve : préchargement, puis mesure, puis comparaison à froid |
| **C4.2** | Régler `OLLAMA_KEEP_ALIVE` et `OLLAMA_MAX_LOADED_MODELS` **avant** de re-dériver le pool. §107.0 : la borne du pool et le réglage du moteur sont **une seule décision**, pas deux. *Un contrôle existe déjà* — `nexus_conformite.py:736` signale en AVERTISSEMENT que la variable n'est pas définie et que le moteur applique son défaut de trois | le pool se re-dérive automatiquement du réglage mesuré |
| **C4.3** | Re-mesurer le débit local, **après** C4.1 et C4.2. Tant que `nexus_preload` n'existe pas, ni cette session ni sovereign ne peut mesurer le débit réel du plan local | le relevé porte deux colonnes séparées : chargement et débit |

> **Ordre corrigé après audit tiers** : la re-mesure dépendait des réglages du
> moteur alors qu'elle était listée avant eux. Les deux ont été interverties.
> Enjeu chiffré du préchargement, trouvé par `nexus_search` dans
> `server.js:947` — même appel, trois passes : **180,3 s à froid, puis 2,90 s,
> puis 0,26 s**. Un rapport de 60 à 700 entre un modèle froid et un modèle chaud.

---

### C5 — LES DEUX CORPUS JAMAIS EXPLOITÉS

**33 771 fichiers** de documentation et **40 310 .md** dans le dépôt SAS, jamais
employés. C'est le plus grand écart entre ce dont la plateforme dispose et ce
qu'elle emploie, et c'est ici que « mixer local et cloud » prend son sens.

Le partage naturel, et il découle des mesures ci-dessus :

| Étage | Plan | Pourquoi celui-là |
| --- | --- | --- |
| indexation, embeddings | **local** | volume énorme, aucune latence critique, données privées, coût nul, et `nomic-embed-text` / `bge-m3` / `all-minilm` sont déjà résidents |
| tri, classification, extraction | **local** petits modèles | tâches courtes où le chargement domine — donc à faire par lots, après C4.1 |
| synthèse, analyse croisée | **cloud** | parallélise sans contention, répond en 2–3 s, couvert par l'abonnement |
| arbitrage de ce qui entre dans le dépôt | **ici** | seul point non délégable |

| # | Tâche | Ce qui la ferme |
| --- | --- | --- |
| **C5.1** | Indexer les deux corpus par embeddings **locaux** (`nexus_index_build`), par lots, **par copie** et jamais en place (§0.4 : lecture seule sur les voisins) | l'index existe, se recherche, et un contrôle vérifie qu'aucune écriture n'a visé les dépôts voisins |
| **C5.2** | Cartographier ce que contiennent réellement les 452 PDF, 1834 notebooks et 5810 txt — délégué au banc, jamais lu ici | une carte interrogeable, pas un résumé dans un contexte facturé |
| **C5.3** | Extraire les métaheuristiques mesurées du corpus MQL5 (§0 : piste de recherche permanente) vers le problème de température, seul vrai terrain métaheuristique du dépôt (§106.2 — la sélection de pool, elle, a été **rejetée sur mesure** : optimum exact en 0,00 s) | une implémentation éprouvée sur banc, avec budget d'évaluation fixé |

---

## 3. LE PROTOCOLE D'EXÉCUTION — comment les déploiements massifs s'enchaînent

**Par lots parallèles délégués**, jamais à la main :

    python scripts/nexus_agent.py --lot lot.json --sortie rendus.jsonl --parallele N
    python scripts/nexus_appliquer.py rendus.jsonl <nom-tache> <fichier-cible>

Quatre règles apprises **ce soir, en usage** :

1. **Croiser les familles.** Le lanceur avertit lui-même quand il ne l'a pas fait :
   *« 2 alias → 1 famille distincte, le croisement n'a pas eu lieu »*.
2. **Le budget de sortie d'abord.** Un `max_tokens` trop serré ne tronque pas :
   il rend **vide** sans erreur. Prévoir large, et lire l'avertissement de plafond.
3. **La contrainte de forme en tête ET en pied.** Patron mesuré par sovereign :
   une consigne qui ouvre sur un bilan appelle un bilan — le banc a rendu un
   rapport de 1348 jetons au lieu du fichier attendu. Reformulée avec « ta
   première ligne est exactement ceci, ta dernière exactement cela », le rendu
   suivant était complet du premier coup.
4. **Le patch, jamais le fichier entier.** `kimi-k2.7-code` a escaladé de 4000 à
   9000 jetons en tentant de tout réécrire, et a échoué deux fois ;
   `deepseek-v4-pro` a rendu deux blocs ancrés en 16 s.

Et le piège de mesure de la soirée, **trois occurrences, trois canaux, même
forme** — *ce qu'on lit n'est pas ce qu'on croit mesurer* :

* un code de sortie lu derrière un pipe est celui de `tail`, pas du script — j'ai
  cru un instant qu'un cliquet annonçait « 1 RÉGRESSION » en sortant en 0 ;
* une commande non bloquée par un garde **absent** se lit comme un garde inerte ;
* un `.pyc` périmé fait passer au vert une contre-épreuve — d'où la purge du
  cache bytecode avant toute mesure d'inversion.

---

## 4. CE QUI REQUIERT L'OPÉRATEUR, ET RIEN D'AUTRE

Tout le reste s'exécute sans arbitrage. Ces deux points ne le peuvent pas :

1. **C2.1** — déclarer `nexus_garde_shell` dans le settings **global**. C'est le
   fichier de configuration de l'opérateur ; la portée d'un garde sur l'ensemble
   de ses dépôts est sa décision. Un pair ne peut pas l'autoriser, et je ne la
   prends pas seul.
2. **C3.2** — quels modèles cloud entrent au registre. Élargir le registre engage
   ce qui sort de la machine (§35, §64) : c'est une décision de souveraineté.

---

## 5. FILE — état à l'ouverture

    C1  canal de retour        8 tâches   ← prioritaire, conditionne les déploiements massifs
    C2  gardes                 5 tâches   dont 1 en attente d'arbitrage opérateur
    C3  registre modèles       4 tâches   dont C3.1 : un routeur pointe peut-être dans le vide
    C4  plan local             3 tâches   C4.1 débloque toute mesure locale
    C5  corpus                 3 tâches   74 000 fichiers jamais exploités

    Cockpit : 531 sujets non affichés — à réconcilier avec cette file,
    non à recopier.

**Rien n'est clos tant qu'un contrôle ne rougit pas quand la règle est enfreinte.**
