# Checklist Progress
Generated: 2026-09-02 15:42:57

## 1. Depot
| Metric | Value |
|---|---|
| Commits non pushes | 3 |
| Etat de l'arbre | propre |
| Date du dernier commit | 2026-09-02 15:42:43 -0500 |

## 2. Rituels
| Script | Regressions annoncees |
|---|---|
| nexus_cablage.py | 1 |
| nexus_outillage.py | 85 |

## 3. Outils
| Description | Value |
|---|---|
| Scripts nexus dans scripts/ | 74 |
| Occurrences name:"nexus_" dans server.js | 15 |

## 4. Checklist VS Code
| Couleur | Nombre |
|---|---|
| Vert | 13 |
| Jaune | 11 |
| Rouge | 15 |

## 5. Sauvegardes
| Metric | Value |
|---|---|
| Nombre de fichiers .bundle | 0 |
| Date du plus recent | inconnu |

## 6. Corpus
| Metric | Value |
|---|---|
| Lignes dans fragments_embeddings.jsonl | 20366 |

## CE QUI RESTE OUVERT
- Regressions de cablage : 1
- Regressions d outillage : 85
- Prescriptions rouges : 15
  - Dependency validation
  - Coordination testing
  - Tool compatibility checks
  - Tool shadowing
  - Graceful degradation EN TIERS
  - TTL sur les donnees echangees
  - Timeout-aware retry with backoff
  - 12 639 PDF a portee, jamais ingeres
  - le repli automatique n essaie qu UN SEUL candidat
  - Idempotency
  - TTL
  - Degradation en tiers
  - reste 🔴
  - `nexus_epreuve_vide.py` est appele SANS ARGUMENT
  - les worktrees d agents naissent en retard, et se resynchronisent sur le MAUVAIS point
  - ORPHELINE
  - Consequence tenue
- Commits non pousses : 3

---

## 9. VERIFICATION DU TABLEAU DE BORD LUI-MEME — 2026-09-02

Question posee par l operateur : *« as-tu mis a jour ton progress md ? l as-tu
verifie ? »* Reponse mesuree, et elle etait NON :

```
Generated       : 15:31:49
dernier commit  : 15:39:38
```

**Le tableau decrivait un depot d avant huit minutes de travail.** Il n est pas
faux par construction — il est faux par PERIME, ce qui se lit exactement
pareil. Regenere.

> **Un tableau de bord n est a jour que si on le VERIFIE a jour.** Le
> regenerer n est pas le verifier : c est en croire la derniere execution,
> dont rien ne dit qu elle a suivi le dernier commit.

## 10. COMMENT SAVOIR QU UN AGENT EST EN VOL — deux instruments, un seul juste

Question posee : *« je ne vois pas tous en vol la »*.

**Premier instrument, FAUX** : l age et la taille du fichier `.output` de
chaque tache. Tous rendaient **0 octet**, y compris celui d un agent ayant
DEJA RENDU son rapport complet. Le `.output` ne reflete donc pas l activite —
il est ecrit a la fin, ou pas du tout.

**Second instrument, juste** : l activite reelle dans le worktree.

```
find <worktree> -newermt '-120 seconds' -type f     -> fichiers touches
git -C <worktree> status --short                    -> travail deja pose
```

Mesure du moment : **un seul** agent touchait des fichiers dans les deux
dernieres minutes ; **un autre portait sept fichiers modifies sans aucune
activite recente** — il avait fini, et sa notification n est jamais arrivee.
Ses sept fichiers ont ete repeches par `git diff`.

> Un agent qui a fini sans notifier est indiscernable d un agent mort, **si on
> juge par le canal de notification**. Il ne l est plus si on regarde son
> WORKTREE. Le travail est dans les fichiers, jamais dans la prose.

C est la meme famille que le reste de la journee : **un instrument exact — le
`.output` existe bien, sa taille est bien 0 — qui repond a la question
voisine.**

## 11. DEUX AGENTS TOURNENT DANS LE VIDE — constate, non force

Consigne de l operateur : *« si cela tourne dans le vide ne pas insister »*.

Mesure, en deux temps parce que le premier instrument etait FAUX :

```
1er essai, en excluant references/  ->  0 fichier touche  =>  « morts »
2e essai, SANS exclusion            ->  0 fichier touche  ET  references/ deja
                                        copiees (207 Mo et 195 Mo)
```

**Le premier essai ne prouvait rien** : les agents copient 130 Mo de doc au
demarrage, precisement dans le repertoire que mon filtre excluait. « Aucun
fichier touche » pouvait signifier « en train de copier ». Seul le second
essai — qui montre les ressources DEJA en place et zero activite malgre tout —
tranche.

| agent | etat mesure | perimetre en suspens |
| --- | --- | --- |
| trois agents | **EN VOL**, fichiers touches dans les 3 dernieres minutes | epreuves JS + `server.js`, configuration, docs A-M |
| **deux agents** | **VIDE** — 0 fichier touche, ressources deja copiees | **16 PowerShell**, **9 fichiers de racine** |

**Non relances**, conformement a la consigne. Leurs deux perimetres restent
donc **NON COUVERTS** par cette vague, et c est inscrit ici plutot que passe
sous silence.

> **Un troisieme instrument faux dans le meme tour** — apres le `.output` a
> zero octet et le tableau de bord perime. Chaque fois : l instrument
> fonctionne exactement comme ecrit, et repond a une question voisine de celle
> qu on pose. Ici : « ce worktree a-t-il ete touche, hors ressources ? » au
> lieu de « ce worktree vit-il ? »
