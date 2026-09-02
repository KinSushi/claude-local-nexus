# Travailler sans abonnement — les commandes, mesurées

> Toutes les commandes de ce document ont été **lancées et vérifiées** avant d'y être
> inscrites. Le code de retour observé est indiqué. Rien n'est écrit de mémoire.
>
> Mesures du 2026-09-02, sur cette machine. Un chiffre figé ment le lendemain : re-mesurez.

---

## 1. La question à laquelle ce document répond

**Si l'abonnement Claude et l'abonnement Ollama Cloud s'arrêtent tous les deux, que
reste-t-il, et comment s'en sert-on ?**

| plan | dépend de | état si les deux abonnements tombent |
| --- | --- | --- |
| Claude | abonnement claude.ai | **mort** |
| Ollama Cloud | abonnement Ollama | **mort** |
| **Local** | **rien** | **intact — 55 modèles, moteur 0.33.2** |

---

## 2. La commande à lancer en premier

```powershell
python scripts/nexus_secours.py
```

**Code de retour observé : 0.** Elle répond en une trentaine de secondes et rend :

```
=== Etape 1 - Accessibilite du moteur ===
Moteur joignable, 1 modele(s) resident(s).

=== Etape 2 - Inventaire des modeles ===
Modeles installes: 55 ; Modeles residents: 1 (dont 1 capables de conversation)

=== Etape 3 - Test du point d'entree /v1/messages ===
Reponse valide recue en 2.98 secondes.
ANTHROPIC_BASE_URL="http://localhost:11434"
ANTHROPIC_AUTH_TOKEN="local"
```

**Elle ne modifie rien.** Elle diagnostique et affiche la configuration à poser — un outil de
secours qui modifie l'environnement pendant qu'on diagnostique aggrave la panne.

Options : `--model <alias>` pour choisir la cible, `--timeout <secondes>` pour allonger le
délai (un modèle non résident demande souvent plus d'une minute à démarrer).

### Le fait qui rend tout le reste possible

Le moteur d'inférence **expose lui-même** un point d'entrée conforme au protocole Anthropic :

```
POST http://localhost:11434/v1/messages   ->  HTTP 200 en 48.9 s
```

Pas de passerelle, pas de clé, pas d'abonnement. C'est ce qui permet de rediriger un client
de codage vers le plan local.

> **Ce qui n'est PAS prouvé, et il faut le dire** : le protocole répond ; l'usage agentique
> complet du client — outils, sessions, fichiers — n'a pas été éprouvé de bout en bout.

---

## 3. Poser la bascule

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:11434"
$env:ANTHROPIC_AUTH_TOKEN = "local"
```

Le jeton peut être n'importe quelle chaîne non vide : le moteur local ne vérifie rien, mais
le client exige que la variable existe.

Voie équivalente, packagée par le fournisseur du moteur, présente sur la version installée :

```powershell
ollama launch claude
```

### ⚠ LE NOM DU MODÈLE N'EST PAS L'ALIAS — mesuré, et c'est l'erreur la plus coûteuse

Le moteur ne connaît **pas** les alias de la passerelle. Mesuré :

```
glm-4.7-flash-local    ->  HTTP 404   "model 'glm-4.7-flash-local' not found"
glm-4.7-flash:latest   ->  HTTP 200 en 36.3 s
```

`-local` et `-cloud` sont des **alias LiteLLM**. Une fois `ANTHROPIC_BASE_URL` pointé sur le
moteur, il faut employer le **nom Ollama**, avec son tag : `glm-4.7-flash:latest`,
`qwen3-coder:30b`, `llama3.2:3b`.

La liste exacte des noms acceptés :

```powershell
ollama list
```

### La séquence complète, dans l'ordre

```powershell
$env:ANTHROPIC_BASE_URL  = "http://localhost:11434"
$env:ANTHROPIC_AUTH_TOKEN = "local"
claude --model qwen3-coder:30b
```

Les deux variables doivent être posées **avant** de lancer le client, dans **la même**
fenêtre. `$env:` ne persiste que dans la session PowerShell courante : ouvrir un nouveau
terminal les perd. Pour les rendre durables :

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://localhost:11434", "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", "local", "User")
```

**Comment savoir que la redirection a pris** : la bannière du client n'affiche plus
`Claude Max`. Tant qu'elle l'affiche, le client parle encore à l'API distante et **aucun
modèle local ne sera trouvé**, quel que soit le nom choisi.

### Quel modèle choisir — mesuré, protocole Anthropic, `max_tokens=200`

| modèle | première réponse | rendu |
| --- | --- | --- |
| **`llama3.2:3b`** | **15,2 s** | 121 car. — **le seul confortable en interactif** |
| `qwen2.5-coder:14b` | 45,0 s | 72 car. |
| `qwen3-coder:30b` | 113,4 s | 126 car. — le meilleur en code, mais lent |
| `glm-4.7-flash:latest` | 51,3 s | **VIDE** |

**`glm-4.7-flash` rend VIDE et ne convient pas** : son raisonnement consomme tout le budget de
sortie avant la livraison. C'est un défaut connu de cette famille — un budget serré y produit
du vide, pas du tronqué. Ne le choisissez pas pour un client interactif.

**Pour un premier essai, employez `llama3.2:3b`** : il répond en 15 s avec du contenu.

```powershell
claude --model llama3.2:3b
```

### Le piège à connaître avant de choisir un modèle

**Être résident en mémoire n'est pas être capable de dialoguer.** Un modèle d'*embedding*
(`nomic-embed-text`, `all-minilm`, `qwen3-embedding`) est souvent résident et refusera toute
conversation avec un `HTTP 400`. `nexus_secours` les écarte et affiche les deux nombres côte
à côte pour rendre l'écart visible.

---

## 4. Vérifier que la machine peut travailler

```powershell
python scripts/nexus_charge.py
python scripts/nexus_charge.py --json
```

**Code de retour observé : 0.** Distingue trois états du moteur, jamais deux :

```
joignable_avec_modeles   joignable_vide   injoignable
```

Les deux premiers autorisent le local ; seul le troisième l'interdit.

> **À lire avant toute mesure de durée.** Sous charge, le local passe de 38 s à 126 s pour la
> même tâche. Un timeout mesuré machine chargée ne dit rien de l'outil testé — cette erreur a
> failli faire accuser la passerelle d'un défaut qu'elle n'avait pas.

---

## 5. Faire travailler le banc local

```powershell
python scripts/nexus_agent.py `
    --tache "<la consigne>" --fichiers chemin/relatif.py `
    --modele qwen3-coder-30b-local --max-tokens 2000
```

Plusieurs tâches d'un coup :

```powershell
python scripts/nexus_agent.py --lot lot.json --parallele 4 --sortie rendus.jsonl
```

**Forcer le plan local**, sans aucune sortie de donnée :

```powershell
$env:NEXUS_LOCAL_SEUL = "1"
```

### L'ordre de repli, quand un plan tombe

```
gpt-oss-120b-cloud  ->  glm-4.7-flash-local  ->  qwen3-coder-30b-local  ->  llama3.2-3b-local
```

**Aucun alias facturé n'y figure et aucun ne doit y figurer** : une panne ne doit jamais
devenir une dépense. Trois candidats locaux, pour que la coupure des deux abonnements laisse
toujours une voie.

La bascule `cloud -> local` est autorisée : elle ne coûte que de la capacité. La bascule
`local -> cloud` est **fermée** : elle ferait sortir des données.

```powershell
python scripts/epreuve_bascule.py          # code 0 attendu
```

---

## 6. ⚠ LE CONTEXTE EST BRIDÉ PAR LE MOTEUR, PAS PAR LES MODÈLES

**Mesuré — c'est la cause la plus probable d'un client qui « répond mais n'appelle pas ses
outils » :**

| modèle | contexte **natif** | appliqué par défaut |
| --- | --- | --- |
| `llama3.2:3b` | **131 072** | 8 192 |
| `qwen3-coder:30b` | **262 144** | 8 192 |
| `gemma4:31b` | **262 144** | 8 192 |
| `qwen3:14b` | 40 960 | 8 192 |
| `qwen2.5-coder:14b` | 32 768 | 8 192 |

Tous déclarent aussi la capacité `tools`.

**Le remède** — à poser avant de démarrer le moteur :

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH", "65536", "User")
# puis redémarrer Ollama
```

Le contrat de ce dépôt (§13, §54) fixe **≥ 64 k** pour un client agentique. À 8 192, le prompt
système et les schémas d'outils saturent la fenêtre avant la question : le modèle tronque et
perd la structure des appels d'outils — il se met alors à **écrire** `< Write file=... />`
comme du texte au lieu de l'émettre.

> **RÉSERVE MESURÉE, à lire avant de monter le contexte** : `llama3.2:3b` occupe déjà **16 Go
> en mémoire pour 2 Go de poids**. Le cache de contexte domine largement le modèle, et monter
> à 64 k ou 128 k multiplie ce coût. Vérifiez la RAM disponible (`nexus_charge.py`) avant de
> fixer la valeur globalement.

### Ce qui reste vrai du découpage



**Mesuré sur cette machine :**

| | valeur |
| --- | --- |
| fenêtre d'**un seul** modèle local | 8 192 jetons — 24 371 caractères utiles |
| pour traiter ~64 k jetons | 11 fenêtres, ~6 min |
| pour traiter ~1 M jetons | 165 fenêtres, ~82 min |

Hypothèse nommée : ~4 caractères par jeton.

> La fenêtre d'un modèle **ne borne plus le volume traitable** — le découpage la contourne.
> Ce qui borne est le **temps**, et localement le temps ne coûte rien d'autre que du temps.

### La limite qu'il faut connaître

**Rediriger `ANTHROPIC_BASE_URL` vers le moteur donne un modèle à 8 k, pas un essaim.** Le
découpage vit dans les outils de ce dépôt, pas dans le protocole. Pour traiter un gros corpus
sans abonnement, il faut passer par `nexus_agent` ou `nexus_ruche`, pas par le client seul.

---

## 7. L'orchestrateur

```powershell
python scripts/nexus_ruche.py --simuler --plans local --max-cibles 6 --taille-lot 3 --essaims 2
```

**Mesuré : 153 cibles découvertes, 2 essaims concurrents, rapport rendu.**

Il découvre les cibles du dépôt, les priorise, les découpe en lots, lance plusieurs essaims et
relance sur échec. Options : `--racine`, `--essaims` (max 4), `--taille-lot`,
`--plans {cloud,local,deux}`, `--tout-refaire`, `--max-cibles`.

> **Défaut connu, non corrigé** : en mode `--simuler`, le rapport affiche des « Échecs » sous
> le même titre et les mêmes compteurs qu'une exécution réelle. Seules deux lignes en tête
> distinguent les modes. **Un rapport de simulation est donc indiscernable d'un rapport
> réel** — n'en tirez aucune conclusion sur l'état du dépôt.

---

## 8. Contrôler ce que le banc rend

```powershell
python scripts/nexus_verifie_rendu.py <fichier|repertoire> --refs "prefixe_"
python scripts/nexus_sonde_aveugle.py scripts/
```

`nexus_verifie_rendu` — **aucun modèle appelé, donc aucune hallucination possible.** Quatre
contrôles : le fichier démarre-t-il, une tranche numérique incohérente avec un préfixe, un
désaccord entre nom d'argument et variable comparée, un antislash mangé au transport.
Mesuré : **4 détections sur 4 témoins défectueux, 0 faux positif sur 100+ scripts sains.**

`nexus_sonde_aveugle` — cherche la classe de défaut la plus fréquente du dépôt : une valeur
unique pour deux situations opposées. **Code 1 = des occurrences trouvées**, ce qui est le
comportement normal. À employer en **signal**, jamais en garde bloquante : sur ce dépôt il
rend 41 occurrences dont plusieurs fausses à la lecture.

---

## 9. Ce qui survit vraiment

Le plan local **produit** ; il **n'arbitre pas**. Mesuré : sur une tâche réelle en 37,9 s à
coût nul, le rendu a **inventé son exemple** et n'a cité aucune ligne réelle malgré une
consigne explicite.

**Ce qui remplace l'arbitrage n'est pas un modèle, c'est l'outillage mécanique :**

```powershell
python scripts/nexus_test.py        # les épreuves câblées
python scripts/nexus_rituel.py      # le tour est-il clos ?
python scripts/nexus_conformite.py  # peut-on démarrer ?
```

~7 200 lignes de contrôles qui n'appellent **aucun modèle** et ne peuvent donc pas halluciner.
**Chaque épreuve câblée est un morceau d'arbitrage qui survit à la coupure, définitivement et
gratuitement.**
