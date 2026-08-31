CANDIDAT = '''

#: Verbes dont la cible d'ecriture se lit de facon fiable dans la ligne de commande.
_VERBES_ECRITURE: Final[frozenset[str]] = frozenset(
    {"tee", "cp", "mv", "dd", "sed", "Set-Content", "Add-Content", "Out-File"}
)

#: Jetons qui terminent une commande et en ouvrent une autre.
_ENCHAINEMENTS: Final[frozenset[str]] = frozenset({"|", "||", "&&", ";"})

#: Puits qui ne sont pas des fichiers du depot. `ls > /dev/null` est anodin et tres courant :
#: le refuser a fait RESTAURER une greffe dans un depot voisin le meme jour.
_PUITS: Final[frozenset[str]] = frozenset({"/dev/null", "nul", "NUL", "/dev/stdout", "/dev/stderr"})


def _cible_plausible(jeton: str) -> bool:
    """Vrai si ce jeton peut designer un fichier du depot.

    Un jeton portant `$`, un accent grave, `*` ou `?` est un chemin CONSTRUIT : le resoudre
    demanderait de simuler le shell, et le deviner serait pire que ne rien rendre.
    """
    if not jeton or jeton.startswith("-"):
        return False
    if jeton in _PUITS:
        return False
    return not any(c in jeton for c in "$`*?")


def cibles_shell(commande: str) -> list[str]:
    """Les chemins que cette commande ECRIRAIT. Elle mesure, elle ne juge pas.

    CE QUI LA JUSTIFIE, mesure le 2026-08-31 : un sous-agent confine dans son worktree pouvait
    faire `echo x > src/kernel/event_log.py` sans etre arrete -- la cible est un des DOUZE
    FICHIERS TCB GELES. Le garde ne lisait que `tool_input["file_path"]`, jamais la commande.

    CE QU'ELLE NE VOIT PAS, ET C'EST UNE LIMITE DECLAREE, PAS UN OUBLI :
      - les chemins CONSTRUITS (`$CIBLE`, substitution, glob) : les resoudre demanderait de
        simuler le shell ;
      - l'ecriture INDIRECTE -- `python un_script.py` qui ecrit -- que rien dans la ligne de
        commande ne trahit.
    Une couverture partielle ANNONCEE vaut mieux qu'une couverture apparente fondee sur des
    suppositions ; c'est la difference entre un trou qu'on connait et un trou qu'on croit fermer.

    ELLE REND UNE LISTE, JAMAIS UN BOOLEEN : c'est l'appelant qui decide ce qu'une cible hors
    perimetre entraine. Melanger la mesure et la decision rendrait les deux intestables.
    """
    try:
        jetons = shlex.split(commande)
    except ValueError:
        # Guillemet non ferme : accident courant. On ne devine pas ce qu'on ne sait pas lire.
        return []

    # Le decoupage en segments se fait APRES `shlex`, jamais sur la chaine brute : un `|` a
    # l'interieur de guillemets appartient au texte, pas a la syntaxe.
    segments: list[list[str]] = []
    courant: list[str] = []
    for jeton in jetons:
        if jeton in _ENCHAINEMENTS:
            if courant:
                segments.append(courant)
            courant = []
            continue
        courant.append(jeton)
    if courant:
        segments.append(courant)

    trouvees: set[str] = set()
    for segment in segments:
        _cibles_du_segment(segment, trouvees)
    return sorted(trouvees)


def _cibles_du_segment(jetons: list[str], trouvees: set[str]) -> None:
    """Les cibles d'UNE commande, sans enchainement. Mute `trouvees` plutot que de rendre."""
    for indice, jeton in enumerate(jetons):
        # `2>&1` et ses formes ne designent pas un fichier.
        if ">&" in jeton:
            continue

        if jeton in (">", ">>"):
            if indice + 1 < len(jetons) and _cible_plausible(jetons[indice + 1]):
                trouvees.add(jetons[indice + 1])
            continue
        if jeton.startswith(">"):
            colle = jeton.lstrip(">")
            if _cible_plausible(colle):
                trouvees.add(colle)
            continue

        if jeton == "tee":
            for suivant in jetons[indice + 1:]:
                if suivant.startswith("-"):
                    continue
                if _cible_plausible(suivant):
                    trouvees.add(suivant)

        elif jeton in ("cp", "mv"):
            # La DESTINATION est le dernier operande : c'est le seul chemin ecrit.
            operandes = [j for j in jetons[indice + 1:] if not j.startswith("-")]
            if operandes and _cible_plausible(operandes[-1]):
                trouvees.add(operandes[-1])

        elif jeton == "dd":
            for suivant in jetons[indice + 1:]:
                if suivant.startswith("of=") and _cible_plausible(suivant[3:]):
                    trouvees.add(suivant[3:])

        elif jeton == "sed":
            if not any(j == "-i" or j.startswith("-i") for j in jetons[indice + 1:]):
                continue
            # LE PREMIER OPERANDE EST L'EXPRESSION, PAS UN FICHIER. Mesure : `sed -i s/a/b/ f.py`
            # rendait `s/a/b/` comme cible -- une fausse cible ferait refuser une commande saine,
            # et un garde qui refuse du travail sain se fait desarmer. Vrai aussi de la forme
            # `sed -i -e <expr> <fichier>`, ou l'expression suit une option.
            operandes = [j for j in jetons[indice + 1:] if not j.startswith("-")]
            for suivant in operandes[1:]:
                if _cible_plausible(suivant):
                    trouvees.add(suivant)

        elif jeton in ("Set-Content", "Add-Content", "Out-File"):
            suite = jetons[indice + 1:]
            if suite and _cible_plausible(suite[0]):
                trouvees.add(suite[0])
            for rang, suivant in enumerate(suite):
                if suivant in ("-Path", "-FilePath") and rang + 1 < len(suite):
                    if _cible_plausible(suite[rang + 1]):
                        trouvees.add(suite[rang + 1])
'''

if __name__ == "__main__":
    import pathlib
    cible = pathlib.Path(__file__).with_name("cibles_shell_bloc.txt")
    cible.write_text(CANDIDAT, encoding="utf-8")
    print(f"bloc candidat ecrit : {cible} ({len(CANDIDAT)} caracteres)")
