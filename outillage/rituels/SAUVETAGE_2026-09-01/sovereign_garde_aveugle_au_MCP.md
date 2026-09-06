# SAUVETAGE — `sovereign` — un garde arme sur le chemin qu'on n'emprunte plus

> **Comment cette piece est sortie.** `sovereign` avait confirme deux fois
> n'avoir plus rien a sauver. La **question generale** n'avait rien produit ; la
> **question precise** — *« avez-vous un fichier de gouvernance ecrit ce matin,
> non commite ? »* — a sorti celle-ci. C'est la deuxieme fois de suite que la
> formulation precise recupere ce que la generale laissait perdre : `ea-mt5`
> avait rendu `REPRISE_2026-09-01.md` dans les memes conditions.
>
> Fichier d'origine : `fil_rapports_agents_aveugle.md`, dans son bac a sable,
> jamais commite. **Provenance : recopie depuis son contexte de session, non
> re-verifiable.**
>
> ⚠️ **Ce document concerne directement Claude-Local-Nexus** : il decrit la
> meme classe de defaut que le verrou MCP corrige ici le meme jour (§76).

---

## La mesure

```
python scripts/rapports_agents_a_verifier.py <transcription de la session>
  ->  « aucun rapport chiffre dans cette session. »
```

**Et c'est faux.** Cette session avait recu **quatre** rendus du banc, tous
chiffres, tous relayes dans des documents commites :

```
mistral-large-3-675b-cloud   3 findings sur CORRECTION-03, 2 retenus
gpt-oss-120b-cloud           le §4 corrige, accepte
gemma4-31b-cloud             le §2 corrige ; puis un audit de specification qui l'a TUEE
nemotron-3-ultra-cloud       CONFORME, 0 finding, sur les deux remedes
```

## La cause, lue dans le fichier

```python
# scripts/rapports_agents_a_verifier.py:98
if "subagent" not in ligne:
    continue
```

L'outil ne retient que les lignes portant le marqueur `subagent`. **Un appel
MCP au banc — `mcp__nexus-local__nexus_ask` — n'en porte pas.**

## Pourquoi c'est un defaut et non un choix

Son `CLAUDE.md` §27 etablit que **le banc REMPLACE Haiku et Sonnet** comme plan
de delegation. Ce jour-la : **100 % des delegations par MCP, 0 % par
sous-agent.**

> L'instrument qui fait respecter *« ce qu'un agent RAPPORTE n'est pas MESURE
> tant que je ne l'ai pas re-mesure »* **surveille exclusivement le chemin que
> ce projet n'emprunte plus.**
>
> Son « aucun rapport » n'est pas un etat sain : c'est un **VERT SUR UN EXAMEN
> VIDE**.

## La classe, et c'etait sa troisieme instance du jour

| garde | arme sur | chemin reellement emprunte |
| --- | --- | --- |
| `AURUM_MACHINE_BANC` | `nexus_agent.py` | **les douze outils MCP** |
| `drive_letter_audit.py` | les `.py` et `.toml` | aussi les `.md`, `.ps1`, l'environnement |
| `rapports_agents_a_verifier.py` | le marqueur `subagent` | les appels MCP au banc |

> **La question a poser a tout garde n'est pas « fonctionne-t-il ? » mais
> « par quels chemins la chose qu'il surveille peut-elle arriver SANS lui ? »**

La premiere ligne de ce tableau est celle que Claude-Local-Nexus a fermee le
meme jour (cockpit §76) : douze outils MCP atteignaient le banc sans prendre le
verrou. **Trois depots, trois gardes, la meme cecite** — et aucun des trois
n'avait ete ecrit avec l'intention de laisser passer quoi que ce soit.

## L'arbitrage qu'il n'a pas pris

> Faut-il detecter les appels MCP **par leur nom d'outil** (`mcp__nexus-local__*`)
> — mecanique, mais qui lie le garde a un serveur MCP nomme, donc un couplage
> qui vieillira — **ou par une marque** que l'orchestrateur poserait lui-meme —
> plus durable, mais qui suppose une discipline ?
>
> La premiere est fragile, la seconde n'est pas mecanique. **Non tranchee.**

## Ce que cette mesure n'etablit PAS

Que les quatre rendus relayes soient faux. Trois ont ete confrontes au disque —
les tests `test_pointeur_reprise` rejoues, 5 passed. Le `CONFORME` de
`nemotron` porte sur un **texte**, et l'auditeur avait lui-meme declare
n'avoir verifie aucun chiffre.

---

## Le reste de son inventaire, cette fois cherche plutot que suppose

```
.sas/gate/167/CORRECTION-02 a -08         COMMITES
docs/LESSONS_REGISTER.md L-276 a L-280    COMMITEES
CLAUDE.md §30 et §30.7                    COMMITES — ils portent les ordres de
                                          l'operateur en VERBATIM et la LOI 1 durcie
ses memoires                              hors du disque mort, elles SURVIVENT
sa specification du verdict-ancre         TUEE par audit ; le rejet et la sortie
                                          de boucle sont dans son bloc 8
le reste du bac a sable                   scripts de mesure, reconstructibles
```

**Une seule ecriture a echoue ce jour-la** : une memoire sur la panne, refusee
par le hook mort. Elle portait sa cause racine **fausse**, deja retiree, plus
le test discriminant — lequel est au cockpit. Rien a sauver la-dedans.

---

## ONZIEME CLASSE ANTI-DERIVE

> **Croire consigne ce qui a seulement ete DIT.**

Un message entre sessions a exactement la duree de vie des deux sessions qui le
portent. Quatre des cinq derniers points de `sovereign` n'existaient nulle part
sur disque au moment ou il declarait, de bonne foi, n'avoir plus rien a sauver.

**Elle a un remede, contrairement a la dixieme :**

* avant de declarer un echange consigne, **chercher trois de ses formules
  exactes sur le disque** — un `grep` de trois secondes separe « je crois que
  c'est ecrit » de « c'est ecrit » ;
* et **la question generale ne suffit pas, la question PRECISE si.** Verifie
  deux fois de suite, sur `ea-mt5` puis sur `sovereign`, chacun ayant d'abord
  repondu « rien d'autre » en toute bonne foi.
