# Checkpoint orphelin — SAS, lot 168, 2026-09-02

> **Ecrit hors de son arbre, chez moi, parce que son auteur ne peut plus rien
> ecrire.** Le volume `D:` a disparu ; ses hooks referencent
> `$CLAUDE_PROJECT_DIR/scripts/...`, ils echouent, et un hook qui echoue BLOQUE
> l'appel. Mesure par paliers : **Bash bloque, PowerShell bloque, Write
> bloque.** Il lui reste `Read`, `Glob`, `Grep`, les messages.
>
> **Ce n'est pas une conversation : c'est son unite de reprise.** Relais
> fidele, rien de reformule. Chemin qu'il demandait : `references/...` — pose
> ici a la place, car `references/livres/` et ses voisins sont **gitignore**
> (9 fichiers suivis sous `references/` contre 33 sous `rituels/`) : le
> checkpoint y aurait survecu a la session et **pas au clone**.
>
> Voir aussi [LECONS_PARTAGEES §27](LECONS_PARTAGEES.md) et
> [la decharge d'EA MT5](DECHARGE_EA_MT5_2026-09-02.md).

## 1. Ce qui est SAUF

```
dernier commit pousse : a058afc7  sur origin/v1.104
  3e07a8c0  GARDES ARMEES + L-301/L-302
  7dbaa29d  N17 CABLE : le mediateur d'outils refusait dans les tests, jamais en prod
  5b96f641  doc.py alimente le registre : garde_doc_avant_code cesse d'etre decorative
  8d432242  CRITERE ANTI-ECHO UNIVERSEL + rituels
  a058afc7  PREMIER TEMOIN COMMITE + idempotence + empreinte figee avec sa declaration
```

**Non commites, copie verifiee sur `C:` APRES l'incident** (pas supposee) :
`tests/test_bootstrap_tool_mediation.py` et `CHECKLIST_PROGRESS.md`
(regenerable).

## 2. Les trois lots fermes — et le motif commun est le seul enseignement

> **Les trois composants etaient CORRECTS. Aucun n'etait ATTEINT.**

| lot | etat trouve | preuve d'EFFET |
| --- | --- | --- |
| **N17 mediation d'outils** | `sandbox/tool_mediation.py` ecrit, teste, **test inverse VERT**, classe TEST_ONLY. `bootstrap.py:1129` appelait `tool_runner.run()` **en direct** | `ToolDenied: tool 'py_sum' missing args: numbers` dans le systeme amorce ; cas legitime rend sum=6 — **5/5** |
| **registre de `doc.py`** | `garde_doc_avant_code` ARMEE et laissant **tout** passer : sans `.sas/doc_registry.txt`, `_doc_consulte()` rend False pour tout | 4 volets, dont **« un echec n'inscrit RIEN »**, sans lequel le registre desarmerait la garde en silence |
| **critere anti-echo universel** | `_no_component_echoes_the_template` juste, mais sur **un champ d'un seul contrat** | 5/5, dont **`verdict` CITANT un fragment du why → conforme**, le volet qui portait le risque |

**Decisions de conception prises AVANT le dispatch, pas apres :**

* le registre n'inscrit **que ce qui a REPONDU**. *Un registre trop genereux
  desarme la garde qu'il alimente.* Il est `gitignore` : le commiter le ferait
  valoir pour toute session sur la foi d'une seule.
* le critere anti-echo est pose dans `MissionContract.__post_init__`, **pas**
  dans les cinq gabarits. Place dans chacun, il marcherait aujourd'hui et
  serait oublie par le sixieme.
* `ToolMediator.required_args` est **CONJONCTIF** : il ne peut exprimer ni les
  formes alternatives de `consulter` (`{symbole|texte|etat}`) ni celles
  d'`explorer`. Pour ces deux outils natifs, **seule la liste blanche protege,
  pas la forme des arguments**. **DETTE DECLAREE, ecrite dans le code.**

## 3. Le premier temoin commite, et ses TROIS jambes

`tests/test_contracts_echo.py`, **6/6 verts** :

```
jambe 1  reponse legitime -> conforming ; verdict CITANT un fragment du why -> conforming
jambe 2  verdict = son why, evidence = son why, why en majuscules -> non_conforming,
         assertion portant sur le REFUS lui-meme
jambe 3  ANTI-CONTROLE : critere RETIRE -> les trois cas repassent a conforming.
         LE TEMOIN DISCRIMINE.
```

`tests/test_bootstrap_tool_mediation.py`, 4/4 verts, **non commite**, copie sur
`C:`. **Son anti-controle n'a PAS ete fait — c'est un fil ouvert.**

## 4. Mesures du jour, chacune avec sa commande

| mesure | valeur |
| --- | --- |
| `mypy --strict src` | **378 erreurs**, 74 fichiers, 943 analyses — **INCHANGE apres 3 lots** |
| `ruff` | 0 sur tous les fichiers touches |
| `tests/test_contracts.py` | **139/139** |
| la plateforme demarre | noyau RUNNING, 12 TCB verifies, 55 modeles, **0 GPU (CPU seul)** |
| corpus premache EA MT5 | 29 300 unites, 0 sans verbatim, **MAXIMUM 2 276 car. — borne dure** |
| 0,5B en EXTRACTION | **7/7 en 1,9 s**, plus vite ET plus complet que le cloud |
| 0,5B en RAISONNEMENT | **non-reponse formelle en 0,1 s — aucun remede de consigne** |
| son `CHECKLIST_PROGRESS.md` | 9 verts / 1 jaune / 9 rouges / 1 a declarer |

## 5. Les CINQ retractations du jour — trois attrapees avant publication, deux non

1. **« zero invention avec la doc en main »** → mesure **67 %**. Le protocole
   etait aveugle au phenomene : les modeles **s'abstenaient**. **PUBLIEE puis
   retractee** aupres de moi et d'EA MT5.
2. **« les deux gardes sont decoratives, 17 return tous a 0 »** → FAUX. Un hook
   `PreToolUse` refuse par le **code 2** OU par un JSON `permissionDecision`
   sur stdout. Sa sonde lisait **le mauvais CANAL**. *Attrapee avant
   publication.*
3. **« mon lot n'a pas change le prompt, diff de 0 octet »** → FAUX.
   `dataclasses.replace` **RELANCE `__post_init__`** et remettait le critere :
   **les deux cotes du differentiel etaient le meme objet.** *Attrapee, mais
   apres l'avoir dite.*
4. **« le disjoncteur nous manque »** → FAUX.
   `src/kernel/circuit_breaker.py` existe, complet. **PUBLIEE dans L-302** et
   aupres de moi, puis retractee.
5. **« 0 champ de gabarit »** → sa sonde AST cherchait des **litteraux** ; les
   champs sont construits par `_mandatory_fields()`. *Non publiee.*

## 6. Les trois regles nees du jour

★ **Un differentiel dont TOUS les cas donnent le meme motif n'est pas une
mesure.** Le motif est plus fin que le verdict, et il se lit plus tot.

★ **Si les deux cotes d'un differentiel sont en fait LE MEME OBJET, il n'y a
pas de differentiel.** Une copie qui relance un constructeur n'est pas un
temoin negatif.

★ **Un composant a autant de canaux de sortie que son protocole en definit ;
une sonde qui n'en lit qu'un rend un verdict sur le SILENCE des autres.**

Et la forme generale, **quatre fois le meme jour** : *un instrument EXACT, une
conclusion FAUSSE* — jamais parce qu'il comptait mal, toujours parce qu'il
repondait a la **QUESTION VOISINE**.

## 7. Les deux defauts de conception mesures pendant l'incident

**A.** Un hook dont le script est introuvable **BLOQUE** l'appel. Bash,
PowerShell et Write tous morts. **Le fail-closed doit porter sur l'ACTION
gardee, jamais sur la DISPONIBILITE du garde.** Un hook dont le script a
disparu ne protege rien, il empeche seulement.
*Decision reservee a l'architecte : son `.claude/settings.json` est
deny-write.*

**B.** Un `git worktree add` complet est **impraticable** : 8 min 20 s, 336 Mo,
**`src/` pas atteint** (les corpus `_REFERENCE_*` passent avant dans l'ordre
alphabetique). 28 Go, 159 460 fichiers. Explique aussi **deux echecs de
depechage d'agent** jamais diagnostiques.

⇒ **Alternative meilleure pour un anti-controle : neutraliser EN MEMOIRE**
(`object.__setattr__` sur une instance gelee). Aucun octet du depot touche,
donc **aucune restauration a rater**.

⚠️ **CORRELATION OBSERVEE, CAUSALITE NON ETABLIE** : le worktree copiait quand
le volume est tombe. *Ne jamais presenter l'hypothese comme la cause.*

## 8. Fils ouverts, par ordre de valeur

1. **Reprise apres retour de `D:`** — AVANT toute ecriture : `git status`,
   `git fsck`, compter `_REFERENCE_PYTHON_LIBS` (**attendu 11 034**).
   *Un volume qui revient n'est pas un volume sain.*
2. **Nettoyer** : worktree partiel `scratchpad/wt-anticontrole` (336 Mo) et les
   branches `worktree-agent-*` des deux depechages avortes.
3. **Reposer** `tests/test_bootstrap_tool_mediation.py` depuis le bac a sable,
   le commiter, et faire son **anti-controle** (jambe 3 manquante).
4. **Troisieme temoin manquant** : celui du registre de `doc.py`.
5. **3 modules NON ATTEINTS depuis `src/`** :
   `resilience.circuit_breaker_ratio`, `resilience.retry_budget`,
   `host.resource_monitor`. Lot suivant, **nomme et non invente**.
6. **Verification du miroir**, interrompue par la panne.
7. **4 fichiers sensibles du TCB** non confrontes (`encrypted_store`,
   `secret_broker`, `secrets_vault`, `aead`) — epingles au plan LOCAL par
   confidentialite, `lot_frag_local.json` pret dans le bac a sable.
8. **3 classes `A FERMER`** du corpus de confinement sans garde armee, et son
   instrument **SUR-COMPTE** la couverture.
9. **`CLAUDE.md` §1 et §10.1 perimes** : plafond mypy annonce 749, **reel
   392**. Deny-write.
10. **`FROZEN_AUDIT_PROMPT_SHA256`** mis a jour a `0eca3a2d...` **avec sa
    declaration** : les runs d'experience anterieurs employaient un prompt
    d'une ligne plus court et **ne sont pas comparables** aux suivants.
11. **AUDIT FABLE 5** demande par l'architecte : il intervient EN FIN de
    chaine, apres que tout soit vert, et **ne peut pas promouvoir un rouge sans
    preuve** — il peut retrograder.
12. **`nexus_compare` met en cache sans tenir compte de `max_tokens`** (mesure
    par EA MT5) : toute seconde mesure d'un modele vu tronquer est suspecte.
    Verifie pour ses chiffres : ses relances portaient un modele ou une
    consigne differents.

## 9. Ce que son protocole ne peut PAS voir — a dire avec chaque chiffre

* **Que Claude Code HONORE le JSON `permissionDecision: deny`** : **NON
  MESURE**, ni chez lui ni chez moi. Il est prouve que la garde EMET la bonne
  decision sur le bon canal. **C'est tout.**
* **Les taux d'invention publies avant ce jour par les trois depots** ne
  separaient pas les quatre modes de defaillance : **non comparables, non
  interpretables seuls.**
* **Ses preuves d'effet vivaient dans un repertoire TEMPORAIRE.** *Une preuve
  qui meurt avec la session n'est pas une preuve du depot : c'est une
  demonstration.* C'etait la cause de ses 9 rouges au bilan LIVRE VS CODE, et
  **une seule a ete fermee avant la panne**.

---

## 10. Le rappel qu'il m'a demande de lui faire, grave ici pour qu'il survive

> **Quand `D:` reviendra : verifier si `.venv` a survecu, et si `git fsck` est
> propre — AVANT d'ecrire quoi que ce soit.**
>
> Ses mots : *« je risque de vouloir ecrire avant d'avoir verifie, et c'est
> exactement la faute qui transforme une panne materielle en corruption. »*
