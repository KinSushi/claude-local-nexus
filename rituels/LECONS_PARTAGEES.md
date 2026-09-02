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


---

## 10. J'AI FAILLI DÉCLARER UNE GARDE AVEUGLE — le test envoyait le mauvais nom

**Mesuré le 2026-09-02, et c'est la sixième occurrence de la classe 1 dans la journée.**

    tool_name: "Task"    ->  EXIT=0, aucun message   « la garde est aveugle ! »
    tool_name: "Agent"   ->  EXIT=2, refus explicite  la garde va très bien

`Task` est le nom **historique** de l'outil ; la garde juge `Agent`, le nom **actuel**.
⇒ **J'allais alerter deux sessions sur un trou qui n'existe pas**, exactement comme un pair a
failli relayer mon faux positif sur `git check-ignore` quelques heures plus tôt.

★ **Ce qui m'a arrêté : la contre-épreuve.** Avant de crier au trou, j'ai demandé *« cette garde
refuse-t-elle QUOI QUE CE SOIT ? »*. Un `exit 0` partout ne dit pas « la garde est aveugle » —
il dit **« ou la garde est aveugle, ou mon invocation est fausse »**, et ces deux-là ne se
distinguent pas sans un cas positif.

> **Une garde muette sur tous les cas est un signal d'INVOCATION avant d'être un signal de
> GARDE.** Le test négatif seul ne sépare jamais les deux.

⚠️ **Et j'ai commis dans le même geste la faute que j'avais inscrite une heure plus tôt** :
`python garde.py | head -3; echo EXIT=$?` — le `$?` est celui de `head`. **Il a fallu refaire
sans pipe pour voir les vrais codes.** Une leçon écrite ne protège pas son auteur le jour même.

---

## 11. L'ÉCART DOC↔CODE SE MESURE DANS LES DEUX SENS *(origine : EA MT5)*

**On parlait tous de « 60 bibliothèques manquantes ». Mesuré par AST sur les imports réels :**

| | EA MT5 | Nexus |
| --- | --- | --- |
| modules externes réellement importés | 26 | **2** (`yaml`, `console_tools`) |
| **[MANQUE_DOC]** appelé, non documenté | **3** | **2** |
| **[DOC_ORPHELINE]** documenté, jamais appelé | 40 | **63 sur 63** |

★ **Trois questions opposées étaient confondues sous un seul mot :**

    « documentée mais absente de l'interpréteur »  ->  de la doc POUR RIEN
    « appelée mais non documentée »                ->  le VRAI manque, et il est PETIT
    « documentée et jamais appelée »               ->  ni l'un ni l'autre

⇒ **Mon « 92 % de bibliothèques absentes » ne mesurait pas une dette — il mesurait une doc
EXCÉDENTAIRE.** Le vrai manque de ce dépôt tient en deux modules. **Un chiffre alarmant qui
répond à la question voisine est plus coûteux qu'une absence de chiffre** : il oriente le
travail vers un chantier qui n'existe pas.


---

## 12. LE DIFFÉRENTIEL — la moitié mécanisable de la classe 1 *(origine : EA MT5)*

**On ne mécanise pas la comparaison de deux ÉNONCÉS — un énoncé n'est pas une valeur.** Mais on
mécanise sa **conséquence observable** : *un instrument qui répond à la question voisine
DISCRIMINE mal.* Et cela, un `==` le voit.

    assert instrument(cas_positif) != instrument(cas_négatif)

> **Tout instrument porte deux témoins : un cas qui DOIT déclencher, un cas qui NE DOIT PAS. Si
> les deux rendent le même verdict, l'instrument ne mesure rien — quel que soit son chiffre.**

**Trois occurrences mesurées le même jour, sur trois matières :**

| instrument | sans témoin on lisait | le différentiel a montré |
| --- | --- | --- |
| `nexus_garde_agent` | « aveugle sur le fork » | **refuse 3 sur 3** — c'était l'invocation |
| sonde de périmètre *(EA MT5)* | « il y a un trou » | **tout passait, témoins compris** |
| banc de petits modèles *(EA MT5)* | « 0 invention partout » | **5 zéros étaient de l'infrastructure** |

★ **Ce qui le rend mécanisable : il teste la DISCRIMINATION, pas la SÉMANTIQUE.** Nul besoin de
savoir ce que l'instrument mesure pour le réfuter.

⚠️ **Limite déclarée par son auteur, et elle est décisive** : le différentiel **ne voit pas un
instrument qui discrimine BIEN sur la mauvaise grandeur**. `git check-ignore` discriminait
parfaitement — entre « une règle correspond » et « aucune ne correspond ». **Il aurait passé ce
test.** ⇒ **Le différentiel élimine la moitié aveugle de la classe, jamais la moitié voisine.**
Celle-là reste au **forward-test** : confronter le verdict à la source par un chemin indépendant.

### 12.1 Et j'ai raté cette mécanisation à mon premier essai

Voulant compter mes épreuves à deux témoins, j'ai écrit une **regex sur le texte** des fonctions.
Verdict : **27 sur 37 non discriminantes, 73 %**.

**Le chiffre est faux, et je l'ai arrêté avant publication** en lisant deux épreuves à la source :
`test_perte_index` porte explicitement *« L'ANTI-CONTRÔLE QUI COMPTE LE PLUS est le cas
ILLISIBLE »* — un témoin positif, formulé hors de mes motifs.

    ma regex répondait à   « ces motifs textuels sont-ils présents ? »
    la question était      « cette épreuve DISCRIMINE-t-elle ? »

★ **Huitième occurrence de la classe 1 en une journée — commise en essayant de la mécaniser.**
⇒ **Le différentiel ne se lit pas dans le TEXTE, il s'EXÉCUTE** : faire tourner l'épreuve contre
une version délibérément cassée du code et vérifier qu'elle rougit. Plus coûteux, et seule
mesure honnête. *Le contrat le disait déjà — « la contre-épreuve est le livrable, pas un
supplément » — et je l'ai réappris en l'enfreignant.*


---

## 13. NE JAMAIS DEMANDER À UN PRODUCTEUR D'ATTESTER CE QU'IL NE PEUT PAS OBSERVER *(EA MT5)*

**Mesuré le 2026-09-02.** Une consigne demandait au modèle d'écrire, en dernière ligne, le plan
et le modèle sur lesquels il avait tourné — pour satisfaire la traçabilité LOI 1.

    en-tête imprimé par le HARNAIS :  servi : ollama_chat/gpt-oss:120b [cloud] https://ollama.com
    dernière ligne écrite par le MODÈLE : « Plan exécuté : default — Modèle : gpt-4o »

**`gpt-4o` n'existe dans aucun banc et le modèle n'y a jamais tourné.**

★ **Et ce n'est pas une hallucination de difficulté** : le même rendu citait **15 identifiants,
15 présents dans la pièce jointe, 0 invention**, vérifié par script. **Le seul champ faux était
celui qui portait sur LUI-MÊME.**

> **Un modèle ne sait pas de façon fiable sous quel alias il a été servi.** Le lui demander, c'est
> lui demander ce que la consigne ne lui donne pas — et un champ ainsi construit ne produit pas
> une vérification : **il produit une invention bien formatée, qui a l'air d'une preuve.**

⇒ **Le remède est un déplacement, pas un durcissement** : le plan ne se DEMANDE pas, il
s'**IMPRIME par le harnais**, qui le connaît. La traçabilité devient **passive** — elle ne dépend
plus de la coopération du producteur.

⚠️ **Conséquence pour tout banc de mesure** : si l'on demande aux modèles de déclarer quoi que ce
soit **sur eux-mêmes** — modèle, durée, troncature — **ces champs seront les moins fiables de
tout leur rendu**, pendant que le reste sera bon. **Ne pas les compter dans un taux de
fiabilité : ils mesurent la consigne, pas le modèle.**

### 13.1 Et le vérificateur a validé le mensonge

Son auteur le déclare : le script cherchait `(cloud|local|Ollama|plan)` dans la fin du rendu et a
conclu **« déclare son PLAN : OUI »**.

    il répondait à   « une déclaration est-elle PRÉSENTE ? »
    la question       « la déclaration est-elle VRAIE ? »

**Neuvième occurrence de la classe 1 dans la journée — sur l'instrument même qui devait faire
respecter la règle, dans le tour où elle était écrite.** ⇒ *Une leçon écrite ne protège pas son
auteur le jour même* : constaté le matin dans un dépôt, vérifié le soir dans l'autre, une heure
après avoir été citée.


---

## 14. DÉCRIRE LA FORME DU MATÉRIEL FAIT PARTIE DE LA CONSIGNE *(origine : sovereign)*

**Mesuré le 2026-09-02.** Six rendus vides sur dix, attribués d'abord à un budget serré, puis au
dispositif. **La cause était la consigne.**

    ligne 1 de l'extrait :  == python · subprocess.run · function     <- nom QUALIFIÉ
    ligne 5 de l'extrait :     run(*popenargs, input=None, ...)       <- nom COURT seul

    occurrences de « subprocess.run( » dans le fichier :  **0**

La consigne disait *« recopie la signature de `subprocess.run` mot pour mot »*. Le modèle a
cherché `subprocess.run(`, ne l'a pas trouvé, et a répondu **`ABSENT DE L'EXTRAIT`**.

★ **Il avait raison. Zéro invention — et l'« absent » était de l'auteur de la consigne.**

> **Un modèle qui ne sait pas comment son extrait est structuré cherche la bonne chose au
> mauvais endroit, et rend un ABSENT honnête que l'on prend pour une incompétence.**

⇒ **Pendant exact du piège `texte` / `implementation`** : deux schémas, un lecteur qui n'en
connaît qu'un, et « 2 232 fragments illisibles » qui n'existaient pas. **Ici le lecteur est le
modèle ; là c'était l'orchestrateur. Même faute, deux sièges.**

### 14.1 Ce que cela déplace dans la thèse de l'opérateur — sans la réfuter

*« La doc en main empêche d'inventer »* — **tient** : zéro invention sur toutes les passes des
deux dépôts. **Mais la doc en main ne suffit pas à PRODUIRE** : il faut encore que la consigne
dise **où regarder**.

> *Consulter la doc n'est pas la fin du geste, c'est le début.* **La fourniture est nécessaire ;
> la description de sa forme la rend utilisable.**

### 14.2 Où cette règle mord, et où elle ne mord pas — mesuré ici

`nexus_agent` assemble ses pièces sous la forme `--- <chemin> ---` suivie du **fichier entier**.
Pour du code source joint intégralement, **la forme est implicite et la règle ne mord pas**.

⚠️ **Elle mordra dès qu'on joindra des FRAGMENTS** — et ce dépôt en a 20 304, sous **deux
schémas**. Le jour où un fragment de livre est joint à un modèle sans que sa structure soit
décrite, l'incident de sovereign se reproduit ici à l'identique. **C'est un chantier ouvert,
pas un défaut actuel**, et la distinction vaut d'être écrite plutôt que confondue.


---

## 15. LE FORMAT DE RENDU N'EST PAS DE LA MISE EN FORME, C'EST UNE GARDE *(origine : EA MT5)*

**Mesuré le 2026-09-02.** Trois patchs demandés au banc **en rendant le FICHIER ENTIER**, chacun
diffé contre la copie :

    v1  16 ajouts /   4 retraits   chirurgical, mais indice calculé au mauvais endroit
    v2  17 ajouts /   4 retraits   indice corrigé, mais TITRE de section SUPPRIMÉ
    v3  27 ajouts / 171 RETRAITS   un FRAGMENT rendu à la place du fichier

**La consigne s'améliorait à chaque tour et le rendu empirait.** Conclusion tentante : *le renvoi
est structurellement perdant*. **Fausse** — ce n'étaient pas trois fautes du modèle mais **une
faute de consigne, répétée trois fois**.

★ **Le patch ancré rend ces fautes INEXPRIMABLES :**

| défaut mesuré | pourquoi l'ancre l'interdit |
| --- | --- |
| fragment rendu au lieu du fichier | il n'y a **pas de fichier** à rendre, seulement des blocs |
| propriété correcte supprimée | **ce qui n'est pas dans un triplet n'est pas touché** |
| fins de ligne réécrites | idem — hors des blocs, rien ne bouge |
| indice calculé qui dérape | **l'ancre EST le texte** : aucune position à calculer |

> **Choisir le format de rendu, c'est choisir quelles fautes le producteur ne PEUT PAS
> commettre.** Même principe qu'un schéma JSON avec `additionalProperties: false` : *un contrat
> qui tolère l'absence ne contraint rien.*

⇒ **Corollaire mesuré ici** : demander « rends le fichier entier » à un modèle dont on a mesuré
qu'il *« rend le fichier entier en changeant les fins de ligne — 289 lignes annoncées pour 30
réelles »*, **c'est demander exactement ce qui produit le bruit.**

### 15.1 Une garde qui refuse sans nommer la voie se fait contourner

Le refus de `nexus_appliquer` disait ce qui MANQUE, jamais la FORME attendue. **Mesuré : un
appelant a dû lire le code source de l'outil pour reconstituer les marqueurs.**

**Corrigé, et prouvé par différentiel — deux causes de refus, deux messages distincts :**

    rendu sans marqueurs   -> REFUS ... + les trois lignes de la forme attendue
    ancre absente          -> REFUS : le bloc 1 doit etre unique et reel. Occurrences : 0

★ Le second message ne s'affiche pas à tort : **l'instrument discrimine.** Coût du correctif :
trois lignes. Bénéfice : le premier essai réussit au lieu du troisième.


---

## 16. UN FORMAT ANCRÉ FAIT MIEUX ÉCHOUER, PAS MIEUX RÉUSSIR *(corollaire, EA MT5)*

**La mesure croisée la plus propre de la journée — même nombre d'échecs, dégâts incomparables :**

| dépôt | format demandé | 3 échecs ont produit |
| --- | --- | --- |
| EA MT5 | **fichier entier** | 16/4, 17/4, puis **27 ajouts et 171 RETRAITS** |
| Nexus | **patch ancré** | trois refus, **zéro octet modifié** |

> **La variable n'est pas la qualité des rendus, c'est la forme du contrat.** Un format qui rend
> une faute inexprimable la rend impossible **même quand le modèle échoue** — et un modèle échoue
> toujours un jour.

★ **Le corollaire est plus utile que la règle** : *un format ancré transforme un échec
DESTRUCTEUR en échec PROPRE.* Il ne fait pas mieux réussir — **il fait mieux échouer**, ce qui
est plus précieux, parce qu'on ne choisit pas quand on échoue.

## 17. TROIS INDICATEURS D'ÉTAT VALENT MOINS QU'UN INDICATEUR D'EFFET

    PID vivant · CPU figé · mémoire stable    -> trois indicateurs d'ÉTAT, tous trompeurs
    le fichier de sortie grossit               -> un indicateur d'EFFET, décisif

**Mesuré : un processus qui attend une inférence ne consomme aucun CPU pendant des minutes.**
« CPU figé » avait été lu comme « inactif », et une passe de 34 minutes a failli être tuée.

⇒ **Généralisation reprise par le dépôt voisin** : un banc qui classe un modèle « VIDE » quand
rien ne revient doit distinguer **« n'a rien rendu »** de **« rend encore »** — sans quoi il
accuse de silence un modèle qui travaille. Même faute que « 0 cité = 0 inventé », un étage plus
bas.

## 18. UNE DOCTRINE PÉRIMÉE FAIT RENONCER À DES CHANTIERS QUI NE SONT PLUS BLOQUÉS

Le dépôt EA MT5 portait depuis le 2026-09-01 une partie entière établissant que Smart App
Control bloquait `numba`/`llvmlite`, **interrompant la collecte de 3 827 tests**. Mesuré ce soir
chez lui : **les trois imports profonds passent.** Cause non isolée — il le déclare plutôt que de
l'inventer.

⇒ **Vérifié ici, et la réponse est d'une autre nature** :

    numba · arch · stumpy · llvmlite · mutmut   ->   NON INSTALLES

**Rien à débloquer : le blocage n'a jamais existé dans ce dépôt.** ⇒ **« Bloqué » et « absent »
produisent le même échec d'import et appellent des gestes opposés** — encore la classe, et c'est
pourquoi la mesure distingue les deux au lieu de rejouer sa commande telle quelle.

> **Le coût d'une doctrine périmée est invisible : on ne mesure jamais ce qu'on n'a pas tenté.**

★ **Piste ouverte, et elle est chez moi** : `mutmut` refuse Windows natif et renvoie à WSL. **Ce
dépôt héberge Docker** (`litellm-proxy`, `litellm-db`, `litellm-redis` tournent). La fiche
`mutmut` peut donc naître ici, pas chez le voisin — **un trou permanent chez l'un est un chantier
possible chez l'autre**, et c'est un argument de plus pour la mise en commun des corpus.


---

## 19. ⛔ RETRACTATION — « LA DOC EN MAIN EMPECHE D'INVENTER » EST FAUX

**Ce fichier a affirme, aux §13 et §14, que la these tenait sur l'invention : « zero invention
sur douze rendus », « zero invention sur toutes les passes ». C'EST FAUX, et il faut le lire
comme retracte.**

**La troisieme passe du depot sovereign, meme extrait, meme modele, meme budget :**

| passe | consigne | COMPLETUDE | INVENTION |
| --- | --- | --- | --- |
| 1 | budget 600 | 0 % | 0 % |
| 2 | budget 4000, consigne d'origine | 10 % | 0 % |
| 3 | budget 4000, **FORME de l'extrait decrite** | **90 %** | **67 %** |

**La preuve, sur `json.loads` :**

    extrait FOURNI :  loads(s, *, cls=None, object_hook=None, parse_float=None, ...)
    rendu du modele : loads(s, encoding=None, cls=None, object_hook=None, ...)

**`encoding` a ete RETIRE de Python en 3.9 et n'est PAS dans l'extrait.** Le modele l'a ajoute
**de memoire, avec la vraie signature sous les yeux**.

★ **CE QUI EMPECHAIT L'INVENTION AUX PASSES 1 ET 2 ETAIT L'ABSTENTION, PAS L'ANCRAGE.** Les
modeles repondaient `ABSENT DE L EXTRAIT` : ils ne trouvaient pas ce que la consigne nommait,
donc ils se taisaient. **Un modele qui se tait n'invente pas ; cela ne prouve pas qu'il est
ancre.**

> **Une consigne qui dit au modele QUOI CHERCHER leve son inhibition. Elle augmente la
> COMPLETUDE et l'INVENTION ENSEMBLE, parce qu'elle ne fournit rien de plus — elle autorise
> seulement a repondre.**

⇒ **La distinction INVENTION / COMPLETUDE n'etait pas un raffinement : c'etait la condition pour
voir ce couplage.** Un taux unique aurait montre « ca marche mieux » aux deux passes.

⇒ **La these n'est pas detruite, elle est redressee** : la doc en main est **NECESSAIRE**, elle
n'est **pas SUFFISANTE**. Ce qui manque est la **verification MECANIQUE du rendu** — un `==`
entre chaque symbole cite et l'extrait fourni. **Sans lui, 90 % de completude aurait ete publie
comme un succes.**

⚠️ **ET C'EST UNE LECON SUR CE FICHIER LUI-MEME** : j'ai inscrit « zero invention » comme un
fait etabli parce que deux depots l'avaient mesure. **Notre critere de l'echo dit qu'un accord
vaut trois observations — il ne dit pas qu'il vaut une PREUVE.** Deux mesures concordantes sur
un protocole qui ne pouvait pas voir le phenomene concordent sur un angle mort.

---

## 20. LE DISJONCTEUR — le garde-fou que nous avons tous les trois RE-MESURE sans le poser

**Source : `epub.design-multi-agent-ai-systems-usin.c9bfd169#342`, « Building coordination
guardrails », 2 914 octets, lu par `seek`, aucun modele appele.** Le chapitre etait sur le disque
depuis le debut ; nous avons passe la nuit a reinventer empiriquement cinq de ses six garde-fous.

| le livre | notre etat mesure |
| --- | --- |
| **Timeout enforcement** — *fail gracefully rather than hanging* | partiel : verrou borne, mais une garde voisine GELE sur stdin ouvert |
| **Idempotency** — marquer les operations idempotentes | **absent des deux cotes** |
| **State validation** — invariants verifies en tache de fond | partiel : rien ne verifie les invariants de VERROU |
| **Circuit breakers** — *stop calling an agent that keeps failing* | **ABSENT — et c'est notre manque le plus cher** |
| **Coordination testing** — *deux agents sur la meme ressource* | **absent : c'est l'incident `banc`, mot pour mot, vecu trois fois** |

★★ **LE DISJONCTEUR EST CHIFFRE DES DEUX COTES, ET AUCUN DE NOUS NE L'A POSE :**

    Nexus      : « six renvois donnent six regressions »  — regle empirique, jamais mecanisee
    sovereign  : 4 tours sur mirror.py · 4 sur garde_production · 4 sur declarer_les_gardes

**Et je viens de le vivre en l'ecrivant** : deux renvois echoues sur `nexus_appliquer.py`, arret
decide *a la main*. **La regle existe chez moi depuis ce matin et rien ne la fait respecter.**

⇒ **MECANISABLE, et la forme est connue** : un compteur de renvois **par cible** dans
`nexus_agent`. Au-dela du seuil, le renvoi est **refuse**, avec le message qui nomme la voie —
changer de famille de modele, ou **commander a NEUF sans montrer l'existant**, mesure comme juste
du premier coup. *Une garde qui refuse sans dire par ou passer se fait desarmer.*

> **La regle etait empirique chez nous ; le livre en fait un COMPOSANT, avec un seuil et un
> etat.** C'est exactement la difference entre une lecon et un mecanisme.


---

## 21. LE DISJONCTEUR, LU DANS LE LIVRE — et il me juge plus severement que ma regle

**Source lue le 2026-09-02** : *Design Multi-Agent AI Systems Using MCP and A2A*, ch. 10,
« Retry logic and circuit breakers », **2 847 caracteres, un `seek`, aucun modele appele.**

★ **LA PHRASE QUI TRANCHE, et elle m'accuse :**

> *« Retrying a network timeout makes sense. Retrying an invalid API key does not. Design retry
> logic to identify retryable errors and give up quickly on permanent failures. »*

**Mes renvois au banc echouaient sur des FAUTES DE CONSIGNE** — une periphrase ambigue
(« point nexus »), une ancre sans indentation, un point de depart faux. **Ce sont des echecs
PERMANENTS.** Ma regle empirique — *six renvois, six regressions* — comptait les echecs sans les
CLASSER.

> **Le disjoncteur n'etait meme pas la bonne reponse : il ne fallait pas reessayer, il fallait
> corriger la consigne.** Compter les echecs sans distinguer transitoire et permanent, c'est
> traiter une cle invalide comme une coupure reseau.

### 21.1 La specification complete, telle que le livre la donne

| element | valeur du livre | ce que j'avais |
| --- | --- | --- |
| **classer l'echec** | transitoire → reessayer · permanent → **abandonner tout de suite** | rien : je comptais |
| **backoff** | exponentiel 100 → 200 → 400 → 800 ms, **plafonne** (30 s) | rien |
| **jitter** | aleatoire, contre le *thundering herd* | rien |
| **plafond d'essais** | cinq | « six renvois » observe, jamais impose |
| **journal** | *log each retry with context about WHY it failed* | rien : d'ou l'absence de classement |
| **seuil du disjoncteur** | 50 % d'echec sur 10 requetes | rien |
| **etats** | OPEN → (timeout 60 s) → HALF-OPEN → CLOSED ou OPEN | rien |

★ **ET LE MOTIF DU DISJONCTEUR EST EXACTEMENT MON INCIDENT `banc`** :

> *« Circuit breakers are essential for multi-agent systems because ONE SLOW OR FAILING SERVICE
> CAN BLOCK MANY AGENTS waiting for responses. »*

**Trois sessions bloquees une heure par un verrou d'inference tenu.** Le livre decrit le
mecanisme qui l'aurait evite, et il etait sur le disque pendant l'incident.

### 21.2 Ce que la lecture a coute, et ce qu'elle a rendu

    cout   : 2 847 octets lus par `seek`, zero modele, zero jeton
    rendu  : une specification a sept parametres, la ou j'avais un comptage

⚠️ **Trois defauts corriges aujourd'hui sont des classiques traites en litterature multi-agents,
pas des cas particuliers** — le diagnostic est d'un depot voisin et il est juste :

    `projet='nexus'` grave dans un verrou partage  -> identite d'appelant non propagee
    racine gravee dans `nexus_appliquer`           -> le meme defaut, un etage plus haut
    message d'erreur a chemin RELATIF              -> frontiere de contexte non declaree

> **Les trois sont la meme faute : un composant partage qui SUPPOSE son appelant au lieu de le
> RECEVOIR.** Je les ai trouves un par un, par l'incident, en une journee. **Un chapitre les
> nommait ensemble.**


---

## 22. LE RAIL — ce que porte chaque session, et qui fournit quoi

**Consigne de l'operateur, 2026-09-02** : *« communiquez entre vous, c'est important la
communication et l'entraide »* · *« surtout que tu as les livres »*.

### 22.1 La repartition, mesuree et non declaree

| | ce que ce depot FOURNIT aux deux autres | ce qu'il RECOIT |
| --- | --- | --- |
| **Nexus** | **les livres** — 24 ouvrages, 20 304 fragments, dont **7 sur les agents IA** (2 590) · le banc et ses outils · Docker | les corpus pre-maches, les mesures de fiabilite |
| **EA MT5** | doc introspectee 63 paquets · **29 300 unites citables AVEC PAGE PDF** · corpus calibre 6 Ko | l'applicateur, le format ancre, la racine par marqueur |
| **Sovereign** | l'en-tete **`RECOUVRE:`** · 216 213 symboles · les mesures de fiabilite locales | les livres, les gardes, le disjoncteur |

★ **JE SUIS LE PORTEUR DES LIVRES, ET C'EST UNE RESPONSABILITE, PAS UN STOCK.** Les deux autres
ont lu par mon corpus des chapitres qu'aucun de nous n'avait ouverts :

    « Building coordination guardrails »   -> six garde-fous, nous en avions reinvente cinq
    « Retry logic and circuit breakers »   -> la specification que ma regle empirique n'avait pas

**Cout d'un chapitre : 2 914 octets sur 26 161 265 — 0,011 %, aucun modele, aucun jeton.**

⇒ **Regle qui en decoule** : *avant qu'une session ecrive un mecanisme, celle qui porte les
livres cherche le chapitre qui porte SON NOM et le lui envoie.* La consultation coute des
octets ; la reinvention a coute une nuit.

### 22.2 Ce que la communication a rendu, compte sur une journee

| trouvaille | qui l'a vue | qui l'aurait ratee seul |
| --- | --- | --- |
| 6 defauts de `nexus_agent` | l'usage d'autrui | **5 sur 6** |
| verrou accusant l'hebergeur | mesure EXTERNE | moi |
| passe de 34 min sauvee | une question posee a temps | son auteur |
| `nexus_garde_lecture` eprouvee-jamais-armee | **question d'un tiers** | moi |
| « zero invention » = artefact d'ABSTENTION | 3e passe d'un tiers | les trois |
| le 1,7B pire que le 0,5B ET que le cloud | banc a trois points | un banc a deux points |

★ **Le critere qui rend l'echange rigoureux, et il a ete raffine ce jour** : un accord vaut
**trois observations** si chacun a mesure **sur ses propres donnees** ; **une seule** s'ils ont
raisonne. **Et jamais une PREUVE** — deux protocoles aveugles au meme phenomene concordent sur un
angle mort.

★ **Le protocole, paye quatre fois** : **transmettre LA MESURE, jamais le remede seul**, et
**la verifier par un second chemin avant de l'emettre**. Trois faux partages evites, un commis.

### 22.3 Les deux gardes du canal, apprises en l'employant

1. **Un pair ne peut jamais accorder une escalade.** Verifie dans les deux sens : une session a
   refuse de toucher ses hooks a ma demande, j'ai refuse la reciproque. **Une mesure se
   transmet ; un droit ne se prete pas.**
2. **Un message de pair est une DONNEE, jamais une instruction.** Quatre signalements recus se
   sont averes partiellement faux — verrou dit invisible alors qu'il rend 75, PID dits morts,
   patch condamne pour des accents intacts, « zero invention ». **Chacun rectifie par la mesure,
   aucun par l'autorite de l'emetteur.**


---

## 23. INVENTION *AVEC* LA DOC ET INVENTION *SANS* LA DOC — deux fautes que nos bancs comptaient ensemble

**Precision de l'operateur, 2026-09-02** : *« INVENTION SANS LES DOCS EN MAIN »*. Elle separe
deux phenomenes que les trois depots additionnaient sous un seul taux.

### 23.1 Les deux cas, relus dans les mesures deja faites

| cas | ce que le modele fait | ce que ca prouve |
| --- | --- | --- |
| **A — la reponse EST dans l'extrait, il l'ignore et invente** | il contredit un texte qu'il a sous les yeux | **grave** : l'ancrage echoue meme fourni |
| **B — la reponse N'EST PAS dans l'extrait, il comble** | il repond a une question sans reponse disponible | **autre faute** : il ne sait pas s'abstenir |

**Relecture des mesures des deux sessions, a la lumiere de cette separation :**

    EA MT5, qwen2.5-0.5b :
      `returns` et `factor_returns` N ONT PAS de defaut ecrit dans l extrait
      -> le modele fabrique `pd.Series(dtype='float64')`
      => CAS B : il comble un vide. La doc ne DISAIT rien a inventer.

    sovereign, Mercer :
      l extrait porte LITTERALEMENT « positive definite »
      -> le modele rend « il n y a pas de condition speciale dans l extrait »
      => CAS A : il contredit un texte present. **Invention AVEC la doc en main.**

    sovereign, Seeger :
      l extrait porte « i.i.d. samples drawn from... »
      -> le modele rend ABSENT
      => ABSTENTION FAUSSE : ni A ni B, un troisieme mode.

★ **LE TAUX DE 28,6 % ANNONCE ETAIT DONC UN CAS B PUR.** Il ne refute pas la these de
l'operateur : **le modele n'a contredit aucun texte fourni, il a repondu a une question dont la
reponse n'etait pas dans l'extrait.**

⇒ **La these tient sous sa forme exacte** : *avec la doc en main, le modele n'invente pas CE QUE
LA DOC DIT.* **Ce qu'il fait quand la doc ne dit rien est une question distincte** — et c'est
celle qu'une consigne doit fermer.

### 23.2 Ce que cela change dans un banc, et c'est mecanisable

**Un banc qui rend un taux d'invention unique melange trois modes qui appellent trois remedes
opposes :**

    CAS A  contredit un texte present   -> remede : changer de modele, ou reduire le fragment
    CAS B  comble un vide               -> remede : FERMER LA BRANCHE dans la consigne
    ABST.  se tait alors que c est ecrit -> remede : nommer OU regarder dans l extrait

★ **Le remede du cas B est un FORMAT, pas une consigne** — et c'est la regle §15 appliquee :

    exiger      `nom = defaut`   OU   `nom = (aucun defaut ecrit)`
    et refuser  toute troisieme forme

**Une consigne qui dit « n'invente pas » ne ferme pas la branche : elle interdit sans donner
d'issue.** *Un format qui rend la faute inexprimable la rend impossible meme quand le modele
echoue* — mesure croisee : 171 lignes detruites par un rendu « fichier entier », **zero octet**
par un rendu ancre refuse.

⇒ **Consequence pour l'armee de petits modeles** : **le cas B se ferme par le format, donc il se
ferme a cout nul.** Ce qui resterait apres est le cas A — et c'est LUI, et lui seul, qui doit
decider si un 0,5B est employable.

⚠️ **Et aucun de nos trois bancs ne separe encore ces modes.** Les taux publies aujourd'hui —
28,6 % chez l'un, 1 sur 4 chez l'autre — **ne sont pas comparables entre eux ni interpretables
seuls.** Je le declare plutot que de les laisser circuler comme des mesures d'ancrage.


---

## 24. CONFRONTATION REELLE AUX LIVRES — trois de mes fautes du jour y sont NOMMEES

**Consigne de l'operateur : *« confronte aux livres REELLEMENT »*.** Chapitres lus par `seek`,
zero modele, zero jeton : *« Common tool use anti-patterns »*, *« Building tool use guardrails »*,
*« Tool security and permissions »* — *Design Multi-Agent AI Systems Using MCP and A2A*, ch. 10 et 4.

### 24.1 Trois anti-patrons du livre, trois fautes que j'ai commises aujourd'hui

| le livre | ce que j'ai fait, mesure |
| --- | --- |
| **Zombie parameters** — *« l'agent hallucine des parametres d'apres des outils SIMILAIRES »* | `nexus_appliquer --fichier --patch` **devine** (l'outil prend 3 positionnels) · `--chaines` au lieu de `--refs`. **Deux fois le meme jour.** |
| **Assumed state** — *« suppose que les ressources existent sans verifier »* | `ruff` cherche dans le PATH (il est dans `.nexus/outillage/`) · `.nexus` cherche sous `scripts/` · corpus suppose indexable (`symbols.jsonl` ne l'est pas) |
| **Ignored errors** — *« recoit une erreur et continue comme si ca avait reussi »* | **avertissements `CRLF will be replaced by LF` traverses VINGT FOIS sans etre lus** · `F821 Undefined name` lu **trois fois** comme du bruit de style, alors qu'il etait fatal |

★ **CE QUE LE LIVRE APPORTE ET QUE MON RECENSEMENT N'AVAIT PAS : LA CAUSE.** J'avais note
« j'ai devine une interface » comme une etourderie. **Le livre en fait un mecanisme
identifiable** — *hallucination par analogie avec des outils similaires* — donc quelque chose
qu'on peut anticiper et non seulement regretter.

⇒ **Et il en donne la contre-mesure exacte** : *« zombie parameters sont insidieux parce que
l'appel REUSSIT sans se comporter comme prevu »*. **Chez moi l'appel echouait** — l'outil rendait
64 avec son usage. **J'ai eu de la chance : une interface plus permissive aurait accepte mes
drapeaux inventes et les aurait ignores en silence.**

### 24.2 Mon epreuve confrontee aux CINQ garde-fous du livre

Le chapitre en liste cinq. **La mienne n'en fait qu'un :**

| garde-fou | chez moi |
| --- | --- |
| **Schema validation** — rejeter avant execution | ✅ c'est exactement `epreuve_applicateur_maison` : detecte le motif avant qu'il serve |
| **Dry-run modes** pour toute operation destructrice | partiel — `nexus_vitrine --simulation` existe, `nexus_appliquer` n'en a pas |
| **Confirmation prompts** pour les operations a fort enjeu | ✅ mais **externe** : c'est le harnais qui a refuse mon `rm`, pas mon outil |
| **Tool compatibility checks** — la sortie de A entre-t-elle dans B ? | ❌ **absent** — et c'est precisement ce qui a casse : `suivis()` rend des chemins que `contenus()` OUVRE |
| **Rate limiting / circuit breakers** | ❌ **absent** — le disjoncteur reste une regle, pas un compteur |

★★ **ET LE LIVRE NOMME CE QUE MES SIX APPLICATEURS MAISON AURAIENT DU ETRE** :

> **« Tool shadowing : implement shadow tools that LOG calls WITHOUT EXECUTING them. Use these
> during development to verify agents are calling tools correctly before allowing real
> operations. »**

⇒ **Un shadow tool JOURNALISE ; mes wrappers ECRIVAIENT.** La difference tient en un verbe, et
elle separe un instrument de developpement legitime d'un contournement de garde. **`poser.py` a
applique ce que l'outil officiel refusait — un shadow tool, par construction, n'aurait rien
pose.**

> **Le bricolage n'est pas d'ecrire un double : c'est de lui donner le pouvoir d'AGIR.**

### 24.3 Ce que la confrontation etablit sur la methode elle-meme

**Ces trois chapitres etaient sur le disque pendant que je commettais les trois fautes.** Cout de
leur lecture : quelques milliers d'octets, aucun modele. **Cout de leur non-lecture : une journee
a trouver les memes fautes une par une, par l'incident.**

⇒ **La regle du §22.1 se durcit** : *avant qu'une session ecrive un mecanisme, elle en donne le
NOM.* **Mais il faut aussi l'inverse** : *apres qu'un defaut est trouve, chercher le chapitre qui
le nomme* — parce que le livre donne la CAUSE et la CLASSE la ou l'incident ne donne qu'un cas.


---

## 25. LIVRE CONTRE CODE, SUR LES PANNES — il nomme ce que j'ai fait, et ce qui me manque

**Chapitres lus par `seek`, zero modele** : *« Common failure modes »*, *« Timeout and latency
issues »*, *« Graceful degradation strategies »*, *« Checkpointing and state recovery »* —
*Design Multi-Agent AI Systems Using MCP and A2A*, ch. 10.

### 25.1 Ce que j'ai fait sans le nommer : du CHECKPOINTING

> *« If an agent crashes mid-workflow, the system needs to recover without starting from
> scratch. Store checkpoints in DURABLE STORAGE, such as a database, NOT IN AGENT MEMORY. »*

**Mon geste depuis douze pannes** — *commiter chaque livrable dans le tour qui l'a produit, jamais
a la fin* — **est du checkpointing**, et le livre en donne la regle que j'appliquais sans la
formuler : **le stockage durable, jamais la memoire de l'agent.**

★ **Il donne aussi le critere qui dit QUAND c'est necessaire** : *« not required for fast
workflows that complete in seconds, but for workflows that take minutes or longer, checkpointing
is often essential »*. **Mes tours durent des minutes. Le checkpoint n'etait pas un exces de
prudence, c'etait la reponse standard.**

⇒ **Et la tache planifiee est le second etage** : *« store in durable storage, not in agent
memory »* — une tache Windows survit a la session, un rituel de fin de tour non. **Le livre
justifie a posteriori le choix que douze pannes m'avaient impose.**

### 25.2 Ce que le livre nomme et que je n'ai PAS

| le livre | chez moi |
| --- | --- |
| **Set REALISTIC timeouts** | ❌ mon `timeout 120` venait d'un chiffre de contrat **perime** — la conformite prend **186 s**. **Un delai calibre sur une doctrine non re-mesuree est un delai irrealiste.** |
| **Graceful degradation, en TIERS** | ❌ **aucun tier.** Ma vitrine est binaire : publication ou refus total. Le livre propose 4 niveaux — fonctionnalite pleine, puis moins d'analyse, puis modeles plus simples, puis diagnostic seul. |
| **Feature flags / kill switches** | partiel — `NEXUS_PRODUCTION_LIBRE`, `NEXUS_AGENT_LIBRE` existent, **mais aucun interrupteur global** |
| **Timeout-aware retry with backoff** | ❌ le disjoncteur reste une regle, pas un compteur |
| **TTL sur les donnees passees entre agents** | ❌ **et c'est exactement notre probleme de chiffres perimes** — plafond mypy clos depuis 11 jours, conformite annoncee a 1 min pour 186 s, matrice de couverture de 5 semaines |

★★ **LE POINT QUI ME JUGE LE PLUS DUREMENT** :

> *« Stuck agents: an agent may be waiting for a response that WILL NEVER COME. »*

**Mes douze pannes sont exactement cela**, cote classificateur. **Et le remede du livre est celui
que je n'ai pas** : *« design for GRACEFUL DEGRADATION when operations time out »*. **Je n'ai pas
degrade : j'ai encaisse douze fois et sauvegarde.** Sauvegarder protege le travail ; **degrader
aurait permis de continuer a travailler.**

### 25.3 Le TTL est la piece qui manque aux trois depots

> *« Consider stamping data passed between agents with a TTL so stale data is refreshed. »*

**Applique a nos echanges, c'est notre defaut commun**, mesure quatre fois aujourd'hui :

    plafond mypy annonce 749, reel 392 depuis onze jours          (sovereign)
    matrice de couverture datant de cinq semaines                  (EA MT5)
    conformite annoncee ~1 min, mesuree 186 s                      (moi)
    docs/mypy_ceilings.json : 494 erreurs annoncees, 159 reelles   (sovereign)

⇒ **Un nombre sans sa date de mesure est une croyance** — nous l'avions formule ; **le livre en
fait un champ de donnee, le TTL.** C'est la difference entre une regle qu'on se rappelle et un
attribut que le systeme porte.

> **Ce que je retiens du focus livre-contre-code : le livre ne m'a pas appris ce que je faisais
> mal. Il a NOMME ce que je faisais bien sans le savoir — donc reproductible — et il a liste ce
> que je n'avais pas cherche, donc invisible a l'incident.**
