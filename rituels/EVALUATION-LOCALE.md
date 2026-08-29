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
