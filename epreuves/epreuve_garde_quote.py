# -*- coding: utf-8 -*-
"""Trois epreuves sur le CAS A du garde shell, dont la contre-epreuve.

Mesure du 2026-08-31, par od -c : un heredoc a delimiteur QUOTE ne subit
aucune expansion du shell, antislash compris. Le garde refusait pourtant, et
son message affirmait l'inverse. Trois fois dans un meme tour il a bloque
son propre auteur sur une construction sure.

  AVANT   un heredoc NON quote portant un antislash doit etre REFUSE
  INVERSE le meme, a delimiteur QUOTE, doit etre ACCEPTE
  CONTRE  l'epreuve INVERSE doit ECHOUER sur le code d'avant correction

La troisieme est la seule qui prouve que le controle detecte quelque chose :
un depot sain et un motif casse rendent exactement le meme silence.
"""
import importlib.util
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def charger(chemin, nom):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    if spec is None:
        print("impossible de charger %s : spec non creee pour %s" % (nom, chemin))
        sys.exit(1)
    if spec.loader is None:
        print("impossible de charger %s : aucun loader pour %s (extension .py manquante ?)" % (nom, chemin))
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print("impossible de charger %s depuis %s : %s" % (nom, chemin, e))
        sys.exit(1)
    return mod


NON_QUOTE = "\n".join([
    "python - <<PY",
    'x = "a\\nb"',
    "PY",
])

QUOTE = "\n".join([
    "python - <<'PY'",
    'x = "a\\nb"',
    "PY",
])

SANS_ANTISLASH = "\n".join([
    "python - <<'PY'",
    'x = "ab"',
    "PY",
])


def jouer(mod, etiquette):
    cas = [
        ("AVANT   non quote + antislash -> REFUSE", NON_QUOTE, True),
        ("INVERSE quote + antislash     -> PASSE ", QUOTE, False),
        ("temoin  quote sans antislash  -> PASSE ", SANS_ANTISLASH, False),
    ]
    resultats = []
    for nom, commande, attendu in cas:
        obtenu = mod.detecter_cas_a(commande)
        ok = obtenu == attendu
        resultats.append((nom, ok, obtenu, attendu))
        print("  [%s] %s  (detecte=%s, attendu=%s)"
              % ("OK  " if ok else "ECHEC", nom, obtenu, attendu))
    return resultats


def main():
    chemin_neuf = os.path.join(RACINE, "scripts", "nexus_garde_shell.py")
    if not os.path.exists(chemin_neuf):
        print("introuvable : %s" % chemin_neuf)
        return 1

    print("=== code CORRIGE ===")
    neuf = charger(chemin_neuf, "garde_neuf")
    res_neuf = jouer(neuf, "corrige")
    tout_ok = all(r[1] for r in res_neuf)

    # CONTRE-EPREUVE : le meme jeu sur le code d'AVANT. L'epreuve INVERSE
    # doit y ECHOUER, sinon ces epreuves ne detectent rien.
    avant = os.environ.get("GARDE_AVANT")
    contre_ok = None
    if avant and os.path.exists(avant):
        print()
        print("=== CONTRE-EPREUVE : code d'AVANT correction ===")
        vieux = charger(avant, "garde_vieux")
        res_vieux = jouer(vieux, "avant")
        inverse = [r for r in res_vieux if r[0].startswith("INVERSE")]
        contre_ok = bool(inverse) and not inverse[0][1]
        print("  contre-epreuve : %s"
              % ("OK -- l'epreuve INVERSE echoue bien sur le code d'avant"
                 if contre_ok
                 else "ECHEC -- elle passe aussi avant : elle ne prouve RIEN"))
    else:
        print()
        print("CONTRE-EPREUVE NON JOUEE : poser GARDE_AVANT sur une copie du "
              "fichier d'avant correction. Sans elle, ces epreuves ne "
              "prouvent pas qu'elles detectent.")

    print()
    if tout_ok and contre_ok:
        print("VERDICT : les trois epreuves tiennent.")
        return 0
    if tout_ok and contre_ok is None:
        print("VERDICT : forward et inverse tiennent, contre-epreuve absente.")
        return 1
    print("VERDICT : ECHEC.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
