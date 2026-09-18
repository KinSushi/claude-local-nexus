# Outils du pont MCP Nexus

> **CE DOCUMENT N'EST PAS ENCORE GENERABLE.** Ne pas s'y fier : il ne decrit
> aucun outil, et ce vide n'est pas un pont sans outils.

Ce fichier doit etre DERIVE de `tools/nexus-mcp/server.js` par
`outillage/nexus_mcp_readme.py`, jamais ecrit a la main. Au 2026-09-17,
l'extraction du bloc `const TOOLS` echoue : le generateur ne trouve aucun
outil alors que le serveur en declare seize.

Le generateur REFUSE desormais d'ecrire dans ce cas, et rend un code non nul
en le disant :

```
Extraction a echoue : aucun outil trouve alors que server.js n'est pas vide.
```

C'est delibere. La premiere version ecrivait un document annoncant « 0 outils »
puis, en mode `--verifier`, le declarait CONFORME au serveur : un document vide
tenu pour conforme a un serveur plein. Mieux vaut un refus bruyant qu'un
document qui ment. Le contenu que remplace ce texte etait precisement ce
document-la, date du 2026-09-17T22:08:17 et annoncant « Nombre d'outils : 0 ».

## En attendant, la source qui fait foi

* **La competence `.claude/skills/nexus-mcp/SKILL.md`** porte les seize outils
  avec leurs VRAIS noms de parametres. Elle a ete derivee du meme bloc `TOOLS`,
  par le banc, et elle est a jour au 2026-09-17.
* **`tools/nexus-mcp/server.js`**, bloc `const TOOLS`, reste l'autorite en cas
  de desaccord.

Un rappel paye le meme jour : `nexus_apply` attend `texte` et `cible`, pas
`patch` et `fichier`. Un appel portant des parametres inconnus n'etait refuse
par personne -- d'ou la pose de `additionalProperties: false` sur les quatre
schemas qui n'en declaraient aucun.

## Ce qui reste a faire

Suivi au registre sous **T-20260917-007** : corriger l'extraction --
delimitation par equilibre des accolades et des crochets, descriptions
concatenees sur plusieurs lignes a reconstituer -- puis cabler un controle qui
rougit quand le serveur declare un outil absent du document, ou l'inverse, pour
que ce document ne puisse plus vieillir en silence.
