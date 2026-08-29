# Évaluation des modèles locaux en conditions réelles

Ce fichier consigne ce que les modèles gratuits réussissent et ratent
quand on leur confie du vrai travail sur ce dépôt. Il n'est pas un
palmarès : son objet est de dire **où placer la barre** — quelle tâche
peut descendre en local, laquelle doit rester en haut, et quel défaut de
l'outillage a été révélé au passage.

Chaque entrée note trois choses distinctes, souvent confondues :

| Dimension | Question |
| --- | --- |
| Pertinence | le modèle a-t-il vu un défaut **réel** ? |
| Forme | sa réponse était-elle exploitable telle quelle ? |
| Remède | le correctif proposé était-il le bon ? |

Un modèle peut être excellent sur la première et mauvais sur la
troisième. C'est même le cas dominant, et c'est ce qui détermine le
partage du travail : **le local détecte, l'orchestrateur arbitre.**

---

## 2026-08-29 — `qwen3-coder:30b` sur `scripts/nexus_savings.py`

271 lignes, 3 appels successifs, 52 à 78 s chacun, coût 0.

### Pertinence — bonne

Le modèle a identifié sans indice le défaut le plus grave du fichier :

> `prices.get(REFERENCE, (0.000002, 0.000010))` — un tarif de repli écrit
> en dur. Si le modèle de référence n'est pas tarifé dans la
> configuration, le rapport annonce une économie en dollars construite
> sur un prix inventé, sans le signaler.

C'est exactement la faute que la charte du dépôt interdit : un chiffre
faux présenté comme mesuré. Il a aussi relevé une division par zéro
possible et une capture d'exception trop large — toutes deux réelles.

### Forme — mauvaise pendant deux essais, et la faute était la nôtre

| Essai | Résultat | Cause réelle |
| --- | --- | --- |
| 1 | « réponse inexploitable » | plafond de sortie à 3000 tokens, réponse de 4250 : **JSON coupé net**. L'outil accusait le modèle d'un défaut d'appelant. |
| 2 | « réponse inexploitable » | JSON **invalide** : sauts de ligne non échappés dans les extraits de code. |
| 3 | 2 corrections sur 3 appliquées | protocole remplacé par des délimiteurs `@@` en début de ligne. |

Deux enseignements d'outillage, tous deux corrigés :

1. **Distinguer une réponse coupée d'une réponse fautive.** `finish_reason`
   le dit ; sans lui, un plafond mal réglé se déguise en incompétence du
   modèle, et on change de modèle au lieu de changer un paramètre.
2. **Ne pas demander du code à l'intérieur d'un JSON.** Échapper sauts de
   ligne, guillemets et antislashs est un exercice que les modèles locaux
   ratent régulièrement — et l'échec détruit un travail par ailleurs
   juste. Des marqueurs en début de ligne laissent le code passer tel
   quel.

La troisième correction a été **refusée par l'outil** : le modèle avait
paraphrasé l'extrait au lieu de le citer. Le refus est le comportement
voulu — appliquer un remplacement dont la cible ne correspond pas
exactement reviendrait à deviner.

### Remède — insuffisant sur les deux corrections retenues

| Proposition | Verdict | Motif |
| --- | --- | --- |
| Attraper `urllib.error.HTTPError` avant `Exception` | **rejetée** | `urllib.error` n'est pas importé dans le fichier. L'attribut existe par effet de bord de `import urllib.request` ; s'il venait à manquer, un `NameError` serait levé **pendant** le traitement d'une erreur et masquerait la panne d'origine. Les deux branches faisaient de surcroît la même chose. |
| Échouer si le tarif de référence manque | **remplacée** | Le défaut était juste, le remède trop brutal : tout le rapport mourait pour un seul prix absent. Le décompte de tokens ne dépend d'aucun tarif et reste valable. Retenu à la place : le rapport survit, seule la conversion en dollars disparaît, avec son motif. |

### Ce qu'on en retient pour le partage du travail

- **Descendre en local** : la détection de défauts sur un fichier isolé,
  la relecture de cohérence, l'extraction. Le rendement est réel et le
  coût nul.
- **Garder en haut** : le choix du remède. Le modèle voit le problème mais
  ne pèse pas ses effets de bord — un import implicite, un rapport perdu
  pour une case vide.
- **Le format d'échange compte autant que le modèle.** Deux échecs sur
  trois venaient de la mise en forme, pas du raisonnement. Un protocole
  mal choisi fait passer un bon modèle pour un mauvais.

---

## 2026-08-29 — `qwen2.5-coder:14b`, quatre fichiers : seuil non atteint

Même protocole, même consigne, quatre scripts Python du dépôt.
**Trois tentatives, trois échecs, et cette fois la faute n'est pas dans
l'outillage.**

Le modèle n'a jamais produit un seul bloc `@@`. Il a rendu :

- une description scolaire du module `concurrent.futures`, sans rapport
  avec la consigne de relecture ;
- un bloc ```` ```plaintext ```` contenant une phrase inventée — « Fichier
  JSON a été fusionné avec succès » — alors qu'aucune fusion n'avait été
  demandée ni effectuée ;
- une troisième réponse de même nature.

Ce n'est pas une faute de forme rattrapable par un analyseur plus
tolérant : le modèle **n'exécute pas la tâche demandée**. Il décrit le
fichier au lieu de le critiquer.

### Conséquence pour le routage

| Modèle | Suivi du protocole | Détection de défauts | Verdict |
| --- | --- | --- | --- |
| `qwen3-coder:30b` | oui, dès le premier essai | réelle, vérifiée | **apte** à la relecture structurée |
| `qwen2.5-coder:14b` | non, 0 sur 3 | non évaluable | **inapte** à cette tâche |

La frontière ne passe donc pas entre « local » et « distant » mais à
l'intérieur du local. Une tâche exigeant un format de sortie strict a un
seuil de taille, et `14b` est en dessous. Le confier à un modèle
sous-dimensionné ne coûte pas seulement un échec : il coûte 138 s
d'occupation CPU, pendant lesquelles le modèle apte est privé de machine.

**Règle retenue** : réserver `qwen2.5-coder:14b` et les modèles plus
légers aux tâches à sortie libre — résumé, extraction, classification —
et n'engager `qwen3-coder:30b` que seul, sans second modèle chargé en
parallèle.

---

## 2026-08-29 — `qwen3-coder:30b` sur `scripts/nexus_state.py` : le piège de la bonne pratique

Trois corrections proposées, **une seule retenue**. Les deux autres
portaient l'apparence d'une bonne pratique et étaient l'une une
régression, l'autre du bruit.

### La régression déguisée

```python
-    except Exception:
+    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
```

Rétrécir une capture trop large est un réflexe juste — sauf ici.
**Vérifié en exécutant le cas** plutôt qu'en raisonnant :

```
FileNotFoundError n'est PAS capturé par SubprocessError
(c'est un OSError)
```

Or `run()` appelle `docker` et `ollama`. Sur une machine où l'un des deux
manque du PATH — le cas d'un poste neuf, exactement celui que
`nexus_state.py` sert à décrire — le script serait mort au lieu de
rapporter un état partiel. La capture large était **délibérée**, et le
modèle n'avait aucun moyen de le savoir : rien ne le disait dans le code.

*Enseignement portable* : une capture large mérite un commentaire disant
pourquoi elle l'est. Sans quoi le prochain relecteur — humain ou modèle —
la « corrigera ».

### Le bruit

`sha256()` renvoyait `None` en cas d'échec ; le modèle proposait `""`.
L'unique appelant écrit `digest[:32] if digest else "absent"` : les deux
sont faux, le comportement est identique. Et `(IOError, OSError)` est un
doublon, `IOError` étant un alias d'`OSError` depuis Python 3. Changement
sans effet, donc rejeté — un diff qui ne change rien coûte quand même une
relecture.

### La bonne

```python
+    try:
         with io.open(env_file, ...) as fh:
             ...
+    except OSError:
+        return ""
```

`os.path.exists` puis `open` laisse un intervalle, et un `.env` illisible
par permission passe le premier test pour échouer au second. Le script
produit un état : il ne doit pas mourir parce qu'un secret est
inaccessible, tout le reste restant calculable. **Retenue.**

### Bilan cumulé sur `qwen3-coder:30b`

| | Propositions | Retenues | Rejetées |
| --- | --- | --- | --- |
| `nexus_savings.py` | 3 | 1 (remède réécrit) | 2 |
| `nexus_state.py` | 3 | 1 | 2 |

Un tiers de rendement, sur des défauts que le modèle **a réellement
trouvés**. La valeur est dans la détection ; l'arbitrage ne peut pas
descendre — deux des quatre rejets auraient introduit une panne.

---

## Comment reproduire

```powershell
# une relecture isolée, sans toucher l'arbre principal
python scripts/nexus_worktree.py `
    --nom relecture `
    --fichier scripts/<cible>.py `
    --modele qwen3-coder-30b-local `
    --consigne "..." `
    --verifier "python -c \"import ast,io;ast.parse(io.open('{fichier}',encoding='utf-8').read())\""

python scripts/nexus_worktree.py --fusionner relecture   # retenir
python scripts/nexus_worktree.py --jeter relecture       # jeter
```

Voir aussi [`RESTE-A-FAIRE.md`](RESTE-A-FAIRE.md) pour les défauts
identifiés et non encore corrigés.
