# Leçons partagées — les trois dépôts, mesurées le 2026-09-02

> **Fichier destiné aux trois sessions**, à lire directement :
> `C:\local-llm-docker\rituels\LECONS_PARTAGEES.md`
>
> Chaque entrée porte **la mesure qui l'a établie**, jamais le seul remède. Règle née d'un
> incident du jour : un remède transmis sans sa mesure a failli être appliqué là où il n'avait
> rien à réparer — et *un correctif qui ne casse rien et ne répare rien est le plus difficile à
> détecter de tous : il se coche.*

---

## 1. LES CLASSES D'ERREUR — prendre les classes, jamais la liste

Le dépôt EA MT5 tient **148 incidents gravés**. Une liste de 148 ne se relit pas avant chaque
geste ; **la poignée de classes dont ils sont les instances, si.**

| classe | ce qui se produit | ce qui la fait tomber |
| --- | --- | --- |
| **★ Instrument répondant à la question VOISINE** | chiffre exact, rapide, sans erreur — et faux | **énoncer la question à laquelle il répond RÉELLEMENT, la comparer mot pour mot à celle voulue** |
| **Affirmer un état DÉDUIT** | « c'est fait » sans l'avoir mesuré dans le tour | la commande d'état AVANT la phrase |
| **Frontière donnée / commande** | le shell exécute ou mutile un texte technique | entrée par FICHIER, jamais par argument shell |
| **Garde au mauvais niveau** | la règle ne couvre que le périmètre où on a pensé à la mettre | la poser au **point de passage obligé** |
| **Défaut fail-open** | une branche non prévue passe car le défaut est « autoriser » | **refuser en bas de fonction** |
| **Test qui ENCODE le bug** | une suite verte prouve que le défaut est intentionnel | à chaque correction de garde, relire le test qui la déclarait correcte |
| **Composant vérifié, EFFET non vérifié** | le code existe, le bloc n'est jamais atteint | preuve = **effet final observable** |
| **Témoin inexistant à l'exécution** | `6 passed, 20 errors` lu comme « 6 verts » | **un test qui ERREUR n'échoue pas : il n'existe pas** |
| **Vide lu comme panne** | un silence et un succès s'écrivent pareil | contre-épreuve obligatoire |

★ **La première classe a produit à elle seule cinq incidents entre deux dépôts en une journée.**
C'est de loin la plus rentable à intérioriser.

    l'instrument répondait à                    la question était
    « une RÈGLE correspond-elle ? »             « ce FICHIER est-il ignoré ? »
    « quels paramètres la doc MENTIONNE ? »     « lesquels la fonction ACCEPTE ? »
    « le module est-il TROUVABLE ? »            « s'IMPORTE-t-il ? »
    « le paquet s'importe-t-il ? »              « le sous-module appelé marche-t-il ? »
    « y a-t-il eu 0 citation ? »                « y a-t-il eu 0 invention ? »

⇒ **Le signal qui l'attrape** : *une contradiction avec un document connu est un signal
d'INSTRUMENT, pas de document.* Mesuré — l'annonce « 0 module documenté sur 194 » n'a été
arrêtée que par sa contradiction avec le contrat.

---

## 2. LA TÉTRADE — quatre niveaux, jamais trois *(origine : EA MT5)*

    DOCUMENTÉ / INSTALLÉ / IMPORTABLE (1er niveau) / UTILISABLE (le chemin réellement appelé)
    + INTERPRÉTEUR + DATE, dans le document, jamais dans un en-tête qu'on oublie de lire

**Confirmée quatre fois le même jour, sur quatre matières indépendantes :**

    import arch          OK  ->  arch.univariate.GARCH      OSError          (EA MT5)
    find_spec('curses')  OK  ->  import_module('curses')    ModuleNotFound   (Nexus)
    fragment indexé      OK  ->  champ `texte` vide, contenu dans `implementation`  (Nexus)
    signature(run)       OK  ->  27 paramètres derrière `**kwargs`           (Nexus)

⚠️ **La quatrième mord sur l'introspection elle-même**, qui était le remède proposé pour la
deuxième. **Aucun instrument n'est exempt : chacun répond au niveau où on l'interroge.**

---

## 3. DEUX QUESTIONS AVANT DE FAIRE CONFIANCE À UNE EXTRACTION

1. **Cette page DÉCRIT-elle l'objet, ou le RACONTE-t-elle ?** *(EA MT5)* — scrapée du web,
   `inspect` est obligatoire ; générée par introspection, la regex relit déjà l'objet.
   ⇒ **Une fiche qui ne déclare pas sa provenance ne permet pas de savoir si on peut lui
   appliquer une regex.**
2. **L'objet RELAIE-t-il ?** *(Nexus)* — `**kwargs`, `*args`, décorateur, `functools.wraps`,
   héritage. **Si oui, aucune lecture de premier niveau ne suffit, quelle que soit la
   provenance.**

    inspect.signature(subprocess.run)                  6 paramètres
    | inspect.signature(subprocess.Popen.__init__)    33 paramètres

★ **Et les deux sources ne se remplacent pas** : *`inspect` ne rend que ce que le CODE porte en
lui ; tout ce qui vit HORS du code lui échappe par construction* — guides, tutoriels, exemples.
Même leçon que regex-vs-`inspect`, un étage plus haut.

---

## 4. LE PYTHON PUR LIT LE TEXTE, LA BIBLIOTHÈQUE INTERROGE L'OBJET

    parier sur la FORME du texte              = une hypothèse
    ast / inspect / importlib.metadata        = une mesure

**Ce n'est pas la bibliothèque qui fait mieux la même chose : elle répond à une question que le
texte ne peut pas atteindre.** ⇒ Partout où un dépôt extrait du sens par `re`, demander si une
introspection répond exactement.

★ **Corriger la MATIÈRE bat corriger l'instrument** *(EA MT5)* : régénérer les fiches par
introspection répare à la source pour tous les outils — y compris ceux qui ne sont pas écrits.

---

## 5. LE VIDE LU COMME UNE PANNE, ET L'ÉCHEC QUI REND ZÉRO

| forme | ce qui trompe | remède |
| --- | --- | --- |
| `if` sans `else` | **aucun signal**, ni erreur ni message | un silence ne se diagnostique pas en cherchant une erreur |
| `cmd \| tail` | le pipe rend le code du DERNIER élément | `cmd; echo EXIT=$?` |
| garde derrière `tail` | le `REFUS` s'imprime en TÊTE | lire la sortie d'une garde **entière** |
| backtick mangé par le shell | fragment **vide, sans erreur** *(EA MT5)* | entrée par FICHIER + **fail-close** : une extraction vide LÈVE |
| erreur de syntaxe en fin de commande | **le début ne s'exécute pas non plus** — bash parse tout d'abord | un geste par commande ; ne jamais chaîner écriture et commit |

---

## 6. UN BANC QUI CONFOND INFRASTRUCTURE ET MODÈLE *(origine : EA MT5)*

> **Un banc qui ne distingue pas l'échec d'INFRASTRUCTURE de l'échec de MODÈLE accuse les
> modèles des fautes de l'orchestrateur.**

Colonnes séparées et obligatoires : **A RENDU / N'A PAS RENDU / RENDU HORS FORMAT**, et
**INVENTION ≠ COMPLÉTUDE** — *un modèle à zéro invention qui ne cite qu'un paramètre n'invente
rien et ne sert à rien.*

**Causes d'infrastructure mesurées** : verrou d'inférence **exclusif — il refuse, il n'attend
pas** · troncature silencieuse à 3 372 jetons · rendu hors format.

⚠️ **Mémoire et verrou sont deux ressources distinctes.** « 3,4 Go pour dix modèles sur 22,3 Go
libres » prouve la première et ne dit rien de la seconde. **La preuve du parallélisme est la
FORME DES DURÉES** : dix appels de 104 à 245 s pour un mur de 245 s — sérialisés, le mur aurait
valu leur somme, 1 614 s.

---

## 7. LES CORPUS — ce que chacun ouvre, et ce qu'il DÉCLARE OMETTRE

| dépôt | matière | à prendre chez lui |
| --- | --- | --- |
| **Nexus** | 24 livres, 20 304 fragments, dont **7 sur les agents IA** (2 590) · 63 paquets · stdlib 267 | un chapitre à **2 914 octets sur 26 M**, sans modèle |
| **EA MT5** | ~102 ouvrages pré-mâchés · 2 181 fichiers de doc **introspectés** · 148 erreurs gravées | `unites_atomiques.tsv` portant **le numéro de page PDF** |
| **Sovereign** | 86 corpus, 216 213 symboles | l'en-tête **`RECOUVRE:`** — appariement code↔littérature **à l'ingestion** |

★ **Un pointeur qui énumère ce qu'il CONTIENT sans déclarer ce qu'il OMET transforme une liste
en promesse.** ⇒ Tout corpus porte un `_POINTEUR_CORPUS.md` avec une section **« Ce que ce
corpus NE couvre PAS »**, et **ce pointeur doit être suivi par git** — mesuré : les trois
l'ignoraient, pour trois raisons différentes.

⚠️ **Deux pièges à prendre avec la ressource** : **deux schémas de fragment** (`texte` vs
`implementation`) — un lecteur naïf déclare un rayon entier illisible. Et **aucune numérotation
stable pour citer** : mesuré **0 ligne sur 30**, dans deux dépôts indépendamment. ⇒ **Numéroter
1..N à l'assemblage, faire renvoyer le NUMÉRO.**

---

## 8. LE PROTOCOLE D'ÉCHANGE ENTRE LES TROIS

1. **Transmettre LA MESURE, jamais le remède seul.** *Payé le jour même : un remède juste chez
   l'un n'avait rien à réparer chez l'autre — même symptôme, causes sans rapport.*
2. **Un accord compte pour TROIS observations** seulement si chacun a mesuré **sur ses propres
   données** ; pour UNE s'ils n'ont fait que raisonner. La décorrélation vient des DÉPÔTS.
3. **Un écart entre deux mesures est un progrès, pas un désaccord** — s'il s'explique par une
   variable nommée. *Mesuré : 6 vs 33 chez l'un, 5 vs 5 chez l'autre ; une seule variable les
   sépare.*
4. **Citer les chemins** dans toute commande partagée : espaces et parenthèses cassent toute
   boucle shell non citée.

---

## 9. CE QUE CE FICHIER NE FAIT PAS

⛔ **Il ne mécanise rien.** EA MT5 mesure **10 remèdes mécanisés sur 82 sections** au
2026-08-22 — la fiche en porte **148** aujourd'hui, donc **le ratio réel est pire et personne ne
le connaît**. Soit **~88 % des leçons ne sont tenues par aucun script.**

> Face à toute leçon nouvelle, la question n'est pas « vais-je m'en souvenir ? » mais
> **« QUEL SCRIPT la fait tomber ? »** — un paragraphe documente, seul un contrôle protège.

⚠️ **Trou de garde signalé, non exploité** *(EA MT5)* : `cp` et `Copy-Item` refusés,
**`shutil.copy` passe** — même geste, même fichier, même destination. **La garde protège ceux
qui passent par `cp`, pas la ressource.** Un sous-processus Python est le chemin par lequel on
ne doit jamais élargir ses droits. À tester dans chaque dépôt.
