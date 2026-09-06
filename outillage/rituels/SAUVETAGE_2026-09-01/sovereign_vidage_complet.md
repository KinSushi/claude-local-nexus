# SAUVETAGE — `sovereign-ai-system` — vidage de contexte complet

> **Pourquoi ce fichier existe.** Meme panne, meme heure : la reinitialisation
> de la liaison USB-SCSI du 2026-09-01 a 11:35:16 a emporte le volume portant
> ce depot. La session s'est retrouvee sans disque, sans shell, sans ecriture.
> Ce qui suit est son vidage de contexte, recopie **verbatim**.
>
> **Legende de provenance, posee par son auteur :**
>
> | marque | signification |
> | --- | --- |
> | `[M+C]` | mesure ET commite sur `origin` — re-verifiable des le clone |
> | `[M-NE]` | **MESURE, jamais ecrit** — disparait si personne ne le consigne |
> | `[CTX]` | lu dans le contexte de session, **non re-verifiable** |
>
> Son avertissement, conserve : tous les blocs `[M-NE]` ont ete mesures avant la
> panne, avec les commandes qui les ont produits, mais sont relus dans un
> contexte de session et non sur disque. **Re-verifiable des le clone :** blocs
> 4 et 2, et le 7 partiellement. **Perdu si personne ne l'ecrit :** blocs 3, 5,
> 6 et 8.

---

## 0. Etat exact au moment de la panne

`[M+C]` Dernier commit : `f3a2d523`. RIEN apres. L'arbre etait a 0 modification.

`[M-NE]` `carte.py --index` puis `self_matrix.py` avaient ete lances en tache
de fond APRES `CORRECTION-08`. Elles ont rendu **code 127** — tuees par la
panne, pas terminees.

> **La carte et la self-matrix sont donc PERIMEES sur `origin`.** Premier geste
> a la reprise.

`[M-NE]` Aucun code ecrit et non commite. Rien a reconstruire de ce cote.

## 1. Point de reprise

`[M+C]` `.sas/gate/167/CORRECTION-08.md` §0. Lot 167 **PENDING**.

`[M-NE]` Pas suivant, dans l'ordre :

1. cloner avec `core.longpaths=true`, et **VERIFIER LE COMPTE de fichiers**,
   pas le code de retour ;
2. regenerer carte et self-matrix — elles sont perimees, cf. bloc 0 ;
3. **NE PAS relancer la boussole** : l'architecte a tranche de ne pas adopter
   la ligne d'ancre polluee, donc chaque nouveau releve **CREUSE** l'ecart au
   lieu de le combler. Le retard passerait de 2 a 3 ;
4. les deux conditions M1 non rendues : `m1_cert.py`, et H3-via-EffectGate.

## 2. Le plan courant — le plus important, et il n'est nulle part

`[M-NE]` Extrait par le banc de `.sas/gate/164/CORRECTION-72.md` §7.4. Le
fichier EST sur `origin`, l'extraction ne l'est pas. Les backlogs que
`CLAUDE.md` designe sont PERIMES, et le plan le dit lui-meme : « piege arme
pour toute session obeissante ». Il y est tombe.

> **RIEN NE PEUT PASSER AU VERT TANT QUE CECI N'EST PAS FAIT PAR
> L'ARCHITECTE.**

| # | objet | etat |
| --- | --- | --- |
| A1 | plafond mypy 749 vers 392 | contenu PREPARE, l'ACL empeche l'agent. `Copy-Item` en admin |
| A2 | 4 gardes sans serrure : `citation_baseline.json`, `citation_audit.py`, `garde_append_only.py`, `verdict_gate.py` | `Set-Acl` en admin |
| A3 | decision de cablage, 3 objets | « C'est le SEUL obstacle au VERT » |
| A4 | `verrou_machine.py` — divergence `B1E3DDE8` contre `0D0B8F2D` | options (a) / (b) / (c) |
| A5 | clause 4 du gate M1 : « H3-via-EffectGate » nomme `orchestration.effect_gate`, atteint par AUCUN code de production | « le gel est leve » |
| A6 | backlogs perimes | `MASTER_PLAN.md` s'annonce v1.91.0 pour un mtime du 2026-08-14 |

**M0, « le quart d'heure de l'architecte »** : plafond + serrures + decision de
cablage + `verrou_machine` — pour obtenir `mypy_ratchet` 392/392, `Get-Acl`
protege=True x4, `verdict_gate` VERT.

`[M-NE]` **Le chiffre qui debloque A1**, et qui repond a l'exigence de
`CLAUDE.md` §1 — prouver que la baisse est REELLE et non une perte de
visibilite :

> « mypy analyse **925 fichiers** aujourd'hui contre **910** au 2026-08-13 —
> **15 de PLUS**, pour **241 erreurs de MOINS**. » La verification est FAITE.

`[M-NE]` **A3 est REDUIT DE TROIS OBJETS A DEUX**, mesure par lignes lues et
non comptees :

| objet | verdict |
| --- | --- |
| `preparation_vision` | **DEJA CABLE** — `src/multimodal/vlm.py:113` fait `from multimodal.preparation_vision import preflight_image` ET l'invoque. Les autres occurrences sont des docstrings |
| `preparation_audio` | orphelin REEL — une seule occurrence hors de lui-meme, l'entree d'exemption de `wiring_check.py:130` |
| `append_sans_doublon` | orphelin REEL — et `garde_duplication_registres.py:238` IMPRIME « Pour ne plus en creer : `src/ingest/append_sans_doublon.py` fait exactement cela ». **Le garde RECOMMANDE le remede, rien ne l'emploie** |

## 3. Le verdict de cloture du gate — delibrement non ecrit dans le lot qu'il juge

`[M-NE]` `gate_cloture.txt`, code de sortie **REEL 2** — la notification
annoncait 0, cinquieme fois de la journee que le canal ment sur le code.

```
INTERROMPU 15/26, arret a « une sauvegarde se prouve »
VIOLATIONS : 0        fichiers hors du filet : 0
NON VERIFIE : 1 — l'ancre du depot a 2 lignes de retard
```

Quatorze etapes franchies, toutes vertes : ruff · mypy (cliquet par zone) ·
lettres de lecteur · derivation reprise · chemins bruts · regles de permission ·
duplication registres · `code_source.txt` des livres · append-only (G1) ·
`pytest.raises` en mutation · tracabilite des references · BOM et CRLF dans les
`.sh` · un temoin ne scelle pas par un compte · invariant BOM des `.ps1`.

`[M-NE]` **Etapes 16 a 26 mesurees une par une, hors du gate** — la chaine en
`&&` etant bloquee a 15 :

```
permission-kernel fuzz    iterations 5000, failures 0        VERT
12 fichiers TCB           TCB manifest verified, ok=True     VERT
zero third-party deps     third_party ()                     VERT
chaos / resilience        all_safe True                      VERT
suite pytest              11 failed / 7106 passed / 25 skipped / 2 xfailed
                          1 565,18 s (26 min 05 s), code REEL 1
```

`[M-NE]` **Les 88 avertissements ne sont PAS un defaut de protocole**, et c'est
le comptage par type qui l'etablit : 84 `SyntaxWarning` + 2
`PytestCacheWarning`, dont **ZERO ne vient d'un fichier de l'arbre** — 43 de
source `<unknown>`, 41 de `<t>`, toutes des bribes synthetiques compilees par
`test_garde_chemins_bruts` pour prouver que le garde voit les 52 lettres.

> **Constat residuel : 84 avertissements intentionnels enterreraient un vrai.**

`[M-NE]` **Aucune comparaison possible sur les 11 echecs.** Le dernier verdict
connu de cette suite est celui de `CLAUDE.md`, 4 859 passes sur 4 865 tests au
2026-08-09. Il y en a 7 144 aujourd'hui. **Parler de « regressions » serait
inventer un point de comparaison.**

## 4. Les onze echecs, et comment chacun s'est ferme

`[M+C]` Les correctifs sont sur `origin`. `[M-NE]` La classification ne l'est
pas.

| # | test | cause et fermeture |
| --- | --- | --- |
| 1-4 | `test_pointeur_reprise` x4 | **MOI.** Deux ordres de reprise coexistaient, donc aucun. Ferme par un APPEND portant le §0, sans editer un scelle |
| 5-6 | `test_carte` x2 | **MOI.** Carte perimee par mes ecritures. `carte.py --index` : 5 888 fichiers, 3 588 resumes. Verifie, code 0 |
| 7 | `test_self_matrix` | **PAS un defaut de code** : `--check` ecrit son verdict sur STDERR (2 200 octets), le test lit STDOUT. Ferme par la seule regeneration, AUCUN changement de code |
| 8 | `test_hook_rappel_rituels` | Le temoin confondait « aucun rappel de RETARD » et « aucune sortie ». `rappels()` insere INCONDITIONNELLEMENT la ligne ISOLEMENT — **le test ne pouvait JAMAIS passer** |
| 9 | `test_corpus_lecture` | Le corpus « securite » declare pour l'HUMAIN dans `doc.py`, absent de la table `CORPUS` qui sert les AGENTS. 85 cles cote plateforme, celle-ci absente. 28 symboles sur disque |
| 10 | `test_recolter_consignes` | Ecart 53 (independant) contre 32 (`extraire()`). Les 23 entrees de l'ecart sont TOUTES des `<cross-session-message>`. **AUCUNE des deux fonctions n'etait fautive** : leur docstring declarait une concordance EXACTE 167==167. C'est la MATIERE qui a change — trois sessions se parlent depuis ce jour |
| 11 | `test_image_utils_reelles` | 2 images sur 284. **Octets lus** : `b45b9f323f93_bodywt_variability.png` commence par `3c 21 44 4f 43 54 59 50` = `<!DOCTYP` ; `54a61cb94ab9_xgm3IwP.jpg` commence par `89 50 4e 47 0d 0a 1a 0a` = signature PNG. **Le validateur avait RAISON. C'etait la POPULATION du temoin qui etait fausse, pas le verdict** |

## 5. Inventaire anti-derive — et il porte un P0

`[M-NE]`

```
23 gardes presents sur disque
 5 armes comme hooks dans .claude/settings.json
12 appeles par scripts/gate.sh
 1 ORPHELIN : scripts/garde_modele_resolu.py, AUCUN appelant
```

Sa docstring : « Refuse une configuration dont le modele par defaut n'existe
pas sur l'hote. `config/sas.toml` `default_model = "llama3.2"`
`fallback_chain = ["llama3.2","echo"]` ».

> **C'est le garde qui ferme le P0 de la plateforme** : un modele par defaut non
> resolu qui retombe sur `echo`, soit un pipeline VERT servant un SIMULACRE.
> Ecrit, juste, jamais appele.
>
> **Avant d'armer un garde neuf, compter ceux qui existent et ne tournent pas.**

`[M-NE]` **Fausse alarme ecartee par la mesure** : `settings.json` arme les
variantes `.restaure.py`, pas les `.py`. Elles sont OCTET POUR OCTET identiques
— `6679f0eb…` et `093d28b2…`. L'armement est equivalent. Il n'y avait rien.

## 6. Empreinte Merkle : 45,5 % sont des worktrees d'agents

`[M-NE]` Releve du 2026-09-01T14:10, decompose. Le total colle EXACTEMENT a
l'ancre (`files=96277`), ce qui valide l'instrument de decomposition.

```
fichiers hors worktrees      52 495
fichiers DANS worktrees      43 782      45,5 %
repertoires hors              6 530
repertoires DANS                914      12,3 %

par worktree : risk-drawdown 22 283 · agent-ab7a28 19 017 · agent-addbc2 1 281 ·
               agent-a8ad1b 648 · agent-ac9cda 400 · agent-af5301 64 ·
               agent-ab6cbd 45 · agent-ab72d9 44
```

`[M-NE]` **Comparaison avec le releve de la veille**, CSV extrait de git
(`f12b947a`), son total collant a son ancre (73 919) :

```
                             08-31 T21:04   09-01 T14:10        delta
fichiers hors worktrees        52 420        52 495       +75
fichiers DANS worktrees        21 499        43 782   +22 283
total                          73 919        96 277   +22 358
```

`+22 283` est EXACTEMENT le compte de `risk-drawdown`, worktree absent la
veille.

> **La croissance reelle du depot entre les deux releves est de 75 fichiers,
> pas 22 358.** 99,7 % de la croissance apparente est UN SEUL worktree d'agent.
> Et ils pesaient deja 29,1 % la veille : ce n'est pas un accident du jour.

**Consequence :** `root_hash` est un Merkle sur l'ensemble, donc toute creation
ou destruction d'un worktree change l'empreinte de l'arbre vif. **Le detecteur
de DERIVE repond aujourd'hui a l'ACTIVITE DES AGENTS autant qu'a la derive du
depot, et rien ne distingue les deux.** Decision d'architecte en attente :
exclure `.claude/worktrees` stabiliserait l'empreinte ET rendrait invisible ce
qu'un agent y depose.

## 7. L'ancre polluee — origine RESOLUE, et la ligne ne peut qu'etre ADOPTEE

`[M-NE]` L'origine etait dans un champ jamais lu :
`tree=D:\...\.claude\worktrees\risk-drawdown`.

**Prouve par arithmetique, pas par vraisemblance :**

```
33 316 suivis - 11 033 (_REFERENCE_PYTHON_LIBS) - 1 (_BOUSSOLE_HASH.csv)
+ 1 (ignore mais present et non exclu : .claude/settings.local.json) = 22 283
ancre du T14:10 = 22 283.   ECART ZERO.
```

L'ecart de 4 declare « inexplique » venait de **DEUX INSTANTS COMPARES** :
l'ancre disait 22 278 a 02:07, la boussole 22 283 a 14:10. Une derivation faite
a 09:00 etait comparee a une mesure prise a 02:07.

`[M-NE]` `garde_sauvegarde.py:291` compare **par PREFIXE D'OCTETS**
(`externe.startswith(interne)`). Sauter une ligne est IMPOSSIBLE. Ecarter n'est
pas une option : **la ligne ne peut qu'etre ADOPTEE.** L'architecte a tranche :
ON N'ADOPTE PAS. Le gate reste donc bloque a 15/26 indefiniment, et **c'est un
ARBITRAGE assume, pas un echec**.

## 8. Decisions d'arbitrage — ce qui a ete REJETE, et pourquoi

`[M-NE]` Un rejet perdu se re-propose et se re-teste. Les voici.

**REJETE — « le verdict porte l'empreinte de ce qu'il a juge ».** Tue par un
audit de `gemma4-31b-cloud`, P1 : « l'ecriture du checkpoint modifie l'arbre,
donc l'empreinte de FIN sera systematiquement differente de l'ACTUELLE. Le
mecanisme mesure l'ecriture de son propre resultat comme une invalidation. »
Sortie de boucle : ce que le gate juge d'un checkpoint n'est pas son CONTENU
mais sa **PRESENCE DANS GIT**. Donc ecrire, commiter, lancer la porte avec son
journal HORS de l'arbre, et **consigner le verdict dans le lot suivant**.

**REJETE — l'outil O2**, les chemins a lettre de lecteur dans `settings.json`
comme cause racine. FAUX : les hooks employaient deja `${CLAUDE_PROJECT_DIR}`.
Voir cockpit §79.1.

**REJETE, quatre fois** — modifier un temoin pour qu'il concorde avec
l'instrument qu'il surveille. A chaque fois, le principe autorisant la
modification a du valoir INDEPENDAMMENT du fait qu'il fasse passer le test, et
etre ecrit dans la docstring.

**REJETE** — un rendu de `gemma4` qui avait AMPUTE une mesure du §2 en la
resumant.

**REJETE** — un rendu de `gpt-oss` qui a **FABRIQUE** le nombre 18 432 et bati
un tableau autour. Cause : la consigne de reprise ajoutait une contrainte de
FORME a une contrainte de CONTENU. **La forme est plus facile a satisfaire que
le fond.** Remede qui a marche : nommer la fabrication ET **enumerer les
chiffres autorises**.

**REJETE** — relever `max_tokens` pour corriger un rendu vide. `qwen3.5` a
produit 3 759 jetons a 3 000 de budget et rendu vide quand meme. **La FAMILLE
est le levier, pas le budget.** Corrige `CLAUDE.md` §28.5, qui parlait d'un
seuil.

## 9. Ce qui reste attendu

`[M-NE]` Une seule chose, qu'il ne peut pas faire : **mesurer si l'un des
quatre outils de consultation laisses hors serialisation touche reellement
Ollama.**

> **Reponse apportee depuis, cote Nexus** — mesure faite, et le pari etait faux
> pour un des quatre :
>
> ```
> nexus_search    -> searchIndex()  -> await embed(model, [query])   INFERENCE
> nexus_models    -> getJson(), /api/ps                              metadonnees
> nexus_profile   -> getJson(), runPython()                          metadonnees
> nexus_savings   -> getJson(), runPython()                          metadonnees
> ```
>
> `nexus_search` est desormais serialise. Les trois autres restent libres, sur
> une mesure et non sur un pari.
