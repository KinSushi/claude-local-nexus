# Historique du projet

> Journal des décisions et de ce qui les a motivées. On y consigne aussi
> les erreurs : un historique qui ne garde que les succès ne prévient de
> rien.
>
> État courant : [STATE.md](STATE.md) · Sujets ouverts : [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD)

---

## 2026-08-29 — Refonte : pont abonnement ↔ local, garde-fous, mise à jour automatique

### Point de départ

Objectif exprimé : associer la puissance locale et l'abonnement Claude,
avec pour cible ~93 % d'économie sur l'abonnement, la capacité de s'en
passer entièrement, et une plateforme multi-tâche et multimodale sans
plafond de contexte.

### La contrainte qui a tout structuré

Vérification faite sur la documentation Anthropic :

- `ANTHROPIC_BASE_URL` **seule** ne remplace pas l'abonnement claude.ai ;
  c'est `ANTHROPIC_AUTH_TOKEN` qui le remplace, et bascule la facturation
  au token sur les crédits API.
- Anthropic ne prend pas en charge le routage de Claude Code vers des
  modèles **non-Claude** à travers une passerelle.

Conséquence : `Set-ClaudeModel.ps1`, qui posait les deux variables en mode
« automatique », **consommait des crédits API en annonçant utiliser
l'abonnement**. La combinaison ne pouvait donc pas passer par le plan
d'authentification.

Architecture retenue : Claude Code reste sur l'abonnement et orchestre ;
la passerelle devient un banc de modèles appelés comme **outils MCP**.

### Défauts préexistants trouvés par la validation

Le validateur écrit pour l'occasion a révélé ce qu'une lecture manuelle
avait manqué :

- 11 alias Ollama Cloud référencés par les routeurs, jamais déclarés ;
- 5 modèles de vision retombant sur un modèle textuel — une image envoyée
  à un modèle aveugle ne produit pas une erreur, elle produit une réponse
  fausse ;
- 8 cycles dans le graphe de fallback ;
- un générateur non idempotent, qui avait accumulé sept lignes de
  commentaire identiques ;
- un cache sémantique actif sur toutes les requêtes, y compris les appels
  d'outils, où deux prompts « proches » n'ont pas la même réponse correcte.

Décision : **les graphes de fallback ne sont plus écrits à la main**. Ils
sont dérivés de l'inventaire déclaré, donc acycliques par construction et
incapables de franchir une frontière de modalité ou de fournisseur.

### Mesures qui ont changé des décisions

| Mesure | Conséquence |
|---|---|
| `nomic-embed-text` classe la phrase sans rapport (0,555) **au-dessus** de la paraphrase (0,520) en français | Modèle d'embedding par défaut remplacé par `qwen3-embedding:8b` (0,875 / 0,417) |
| 6 modèles cloud exécutables sur 19 publiés, puis 9 une heure plus tard | Un `402` écarte, un `429`/timeout **conserve** : un quota épuisé ne prouve rien sur les droits |
| `glm-4.7-flash` à 65 536 de contexte occupe 23 Go (`ollama ps`) | Dimensionnement du profil de relève, et argument chiffré pour sortir de Docker |
| Le conteneur Ollama plafonne à 32 Go sur 61,6 Go de machine | 29 Go inaccessibles à l'inférence ; `llama3.3:70b` sélectionné par le routeur alors qu'il ne peut pas tourner |
| Volume Docker : 541 Go pour 155 Go libres sur C: | Migration impossible d'un bloc — d'où un plan par étapes |

### Erreurs commises pendant la séance

- **Premiers tests « réels » validés sur le cache Redis** (0,0 s de latence).
  Corrigé : opérandes tirées au hasard et cache neutralisé — les temps
  mesurés sont passés à 6–66 s, c'est-à-dire à la réalité.
- **Prétention fausse dans le serveur MCP** : il annonçait rapporter le
  modèle retenu, mais rapportait le nom du routeur. Le bon en-tête est
  `x-litellm-adaptive-router-model`.
- **Faille d'indexation** : rien n'interdisait explicitement d'indexer
  `.env`. Les extraits remontant vers l'orchestrateur, un secret aurait
  fui. Interdiction déclarée et testée.
- **Corruption de la configuration** : l'ancien `update_cloud_models.ps1`
  lancé pour être testé a dupliqué tout le fichier. Restauré depuis
  sauvegarde ; les deux anciens scripts sont désormais bloqués par un
  garde-fou.
- **Régression introduite puis attrapée** : confusion entre l'origine d'un
  bloc et son éligibilité au pool, qui redéclarait un alias en double. Le
  discriminant fiable est la **position entre marqueurs**, pas une marque
  posée dans le contenu.

### Livré

- Serveur MCP `nexus-local`, huit outils, sans dépendance npm.
- Configuration mi-générée mi-manuelle, délimitée par marqueurs `AUTOGEN`,
  générateur idempotent.
- Validation bloquante avant tout redémarrage.
- Garde-fou matériel : `ACCEPT` / `DEGRADED` / `REJECT` selon CPU, GPU,
  RAM et disque mesurés.
- Contexte distribué : map-reduce local pour dépasser toute fenêtre.
- Profil de relève à 64K, pour se passer de l'abonnement.
- Mise à jour automatique quotidienne, pool cloud et inventaire local sans
  plafond.
- Suite de tests forward / reverse / policy / code, dont l'idempotence et
  l'absence de fuite transitive.

### Décidé sans action

**Docker comme extension mémoire est un mirage** : la VM WSL2 prélève sa
mémoire sur celle de la machine, donc deux moteurs partitionnent 62 Go, ils
n'en créent pas 94. Le double moteur reste utile pour la résidence
simultanée de modèles et pour la continuité de service pendant la
migration — pas pour la capacité.

### Seconde moitié de séance — limites matérielles et autonomie

**Le plafond Docker, mesuré.** Le conteneur Ollama dispose de 32 Go sur une
machine de 61,6 Go : WSL2 applique son défaut de 50 %, aucun `.wslconfig`
n'existant. Vingt-neuf gigaoctets sont donc hors d'atteinte de l'inférence.
Le routeur avait sélectionné `llama3.3:70b` (42 Go), qui ne peut pas tourner.

D'où le **garde-fou matériel** : la machine est mesurée, et son verdict
s'impose — `ACCEPT`, `DEGRADED`, `REJECT` — au moment de déclarer un modèle,
de le verser dans un pool, de l'employer comme cible de repli, et de le
télécharger.

**Les health checks tournaient en boucle.** Les journaux montraient des
cycles de 60 s pour un intervalle de 30 s : la sonde ne s'arrêtait jamais et
chargeait les modèles en permanence. Sur un hôte CPU, elle volait la machine
au travail réel. Intervalle porté à 900 s. C'était aussi 93 % du trafic
enregistré, ce qui faussait toute mesure d'économie.

**Doctrine de repli, corrigée.** La règle « aucun franchissement de
fournisseur » supprimait le repli utile. Remplacée par une règle
asymétrique : vers le local toujours, vers l'extérieur jamais.

**Autonomie.** Profil `releve-locale` à 64K — dimensionné sur une mesure,
23 Go relevés par `ollama ps`. `Start-Claude.ps1` relance la session sur ce
profil quand un motif de quota apparaît. Le contexte distribué
(`nexus_context`) dépasse toute fenêtre par découpage et réduction.

**Usage réel des outils.** Trois relectures déléguées à coût nul, sur
30 000 tokens qui auraient été prélevés sur l'abonnement. Elles ont trouvé
quatre défauts réels — transport HTTP figé, clé vide envoyée en Bearer,
image sans plafond de taille, cosinus sans garde — et trois faux positifs.
Le rendement vient du tri.

### Audits croisés — quatre agents, périmètres disjoints

Quatre audits ont été conduits en worktrees isolés : sécurité, robustesse du
serveur MCP, correction de la chaîne génération/validation, qualité perçue du
dépôt. Ils ont trouvé nettement plus que l'inspection directe, et surtout des
défauts d'une autre nature.

**La fuite Langfuse.** `success_callback` s'appliquait à toutes les requêtes,
les 40 modèles locaux compris, sans masquage : chaque prompt et chaque
réponse partaient vers cloud.langfuse.com pendant que les outils annonçaient
« aucune donnée ne quitte la machine ». C'est le défaut le plus grave de
toute la refonte, et il était antérieur à celle-ci — mais les outils bâtis
par-dessus le rendaient mensonger.

**Deux échecs ouverts.** Les routeurs étaient exclus du calcul des domaines :
un modèle cloud glissé dans le pool `adaptive-router-local` passait la
validation *et* le test de fuite transitive — démontré en exécutant le
validateur sur une configuration piégée. Et `installed_models()` renvoyait un
dictionnaire vide quand Docker était arrêté, donc tous les modèles pesaient
0 Go, donc tous passaient en ACCEPT : générateur et validateur échouaient
ouverts, ensemble.

**L'indexation sortait du dépôt.** `nexus_index_build` acceptait une racine
absolue : le répertoire personnel était indexable, `.ssh` et `.aws` compris,
et `nexus_search` en restituait le contenu verbatim.

**Le README mentait sur ses propres chiffres** — « 41 alias local / 9 cloud »
pour 40 et 6. Un dépôt qui proclame « rien n'est supposé, tout est mesuré »
ne peut pas se tromper sur un comptage que ses propres outils produisent.

Sur l'ensemble, plusieurs signalements ont été **écartés après vérification** :
une boucle infinie impossible (le plancher de `windowChars` l'interdit), un
compteur d'appels en vol mal analysé, un `||` jugé dangereux qui fait ce
qu'il doit. Le rendement d'un audit vient du tri, pas de l'acceptation.

**Erreur commise** : j'ai retiré `SKILLS.txt` en le jugeant sur sa forme —
c'était une source d'inspiration voulue. Restauré, avec une réserve explicite
sur ses chiffres et ses liens.

### Suite

Migration du moteur hors de Docker, par étapes et réversible jusqu'à la
dernière. Voir la section 1 du cockpit, et
[`RESTE-A-FAIRE.md`](RESTE-A-FAIRE.md) pour les 27 correctifs identifiés
et non encore appliqués.
