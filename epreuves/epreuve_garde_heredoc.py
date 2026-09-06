"""Forward, reverse et fuite sur la garde de heredoc.

Le patch rend le guillemet OPTIONNEL dans la detection d entree de heredoc.
Le risque est d AFFAIBLIR la garde : si le corps d un heredoc NON quote est
desormais ignore, une expansion reellement dangereuse pourrait passer. La
question est donc double, et une seule des deux ne suffit pas.
"""
import importlib.util
import pathlib
import sys

spec = importlib.util.spec_from_file_location(
    "gs", str(pathlib.Path("scripts/nexus_garde_shell.py").resolve()))
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)

BT = chr(96)
Q = chr(39)   # apostrophe, jamais ecrite litteralement ici  # accent grave, jamais ecrit litteralement dans ce fichier

CAS = [
    # (nom, commande, doit_etre_refuse, pourquoi)
    ("FORWARD heredoc QUOTE avec accents graves",
     "git commit -F - <<'EOF'\nvoici du " + BT + "code" + BT + " et une apostrophe l'ici\nEOF\n",
     False, "le quoting interdit toute expansion : rien a refuser"),

    ("FORWARD heredoc NON quote, corps inoffensif",
     "cat <<EOF\nune ligne de texte ordinaire\nEOF\n",
     False, "aucune expansion dans le corps"),

    ("REVERSE accent grave HORS heredoc, guillemets doubles",
     'echo "resultat: ' + BT + "whoami" + BT + '"\n',
     True, "substitution de commande reelle, hors de tout heredoc"),

    # CORRIGE. Le cas precedent employait "cat <<EOF", HORS du contrat de
    # detecter_cas_a, dont le code restreint l examen aux heredocs PYTHON :
    #     if "py" not in delimiteur.lower() and "python" not in avant.lower():
    #         continue
    # L epreuve accusait donc la garde d un trou que son contrat exclut, et
    # son ECHEC se lisait comme un defaut du code. Reecrit DANS le contrat.
    ("REVERSE heredoc PYTHON non quote, accent grave dans le CORPS",
     "python - <<PYEOF\nx = " + BT + "whoami" + BT + "\nPYEOF\n",
     True, "heredoc python non quote : le shell substitue le corps"),

    ("FORWARD heredoc PYTHON QUOTE, accent grave dans le CORPS",
     "python - <<" + Q + "PYEOF" + Q + "\nx = " + BT + "whoami" + BT + "\nPYEOF\n",
     False, "quote : aucune substitution, refuser serait un faux positif"),

    ("FUITE heredoc quote dont le corps imite du code dangereux",
     "cat <<'EOF'\nrm -rf / et " + BT + "whoami" + BT + " et $(id)\nEOF\n",
     False, "quote : le shell ne lit rien de tout cela, aucune fuite"),
]

def _run_tests():
    echecs = 0
    for nom, cmd, doit_refuser, pourquoi in CAS:
        verdict = None
        for f in ("detecter_cas_a", "detecter_cas_b", "detecter_cas_ps", "analyser"):
            fn = getattr(gs, f, None)
            if fn is None:
                continue
            try:
                r = fn(cmd)
            except Exception as exc:
                print("  %-52s FONCTION %s A LEVE : %s" % (nom, f, exc))
                continue
            if r:
                verdict = (f, r)
                break
        refuse = verdict is not None
        ok = refuse == doit_refuser
        echecs += 0 if ok else 1
        print("  %-52s %s  refuse=%-5s attendu=%-5s %s"
              % (nom, "PASS" if ok else "ECHEC", refuse, doit_refuser,
                 ("<- " + verdict[0]) if verdict else ""))
        if not ok:
            print("        pourquoi ce cas : %s" % pourquoi)

    print("\n  fonctions vues : %s"
          % ", ".join(n for n in dir(gs) if n.startswith("detecter") or n == "analyser"))
    print("  %d echec(s)" % echecs)
    sys.exit(1 if echecs else 0)

if __name__ == "__main__":
    _run_tests()
