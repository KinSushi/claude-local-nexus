# -*- coding: utf-8 -*-
"""La regle du quota partage detecte-t-elle, ou se tait-elle par chance ?"""
import io
import os
import re
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(RACINE, "litellm_config.yaml")
SCRATCH = os.environ.get("TEMP", RACINE)
COPIE = os.path.join(SCRATCH, "config_sonde_quota.yaml")


def jouer_validateur(chemin: str):
    r = subprocess.run(
        [sys.executable, os.path.join(RACINE, "scripts", "nexus_validate.py"),
         "--config", chemin],
        cwd=RACINE, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def jouer() -> int:
    """Joue le validateur sur la configuration REELLE puis sur une copie FAUTIVE.

    Le silence sur une configuration saine ne prouve rien : un motif casse
    rend exactement le meme silence. On injecte donc le defaut -- un repli
    d'un MODELE cloud vers un autre alias cloud -- et l'on exige que le
    validateur le refuse.
    """
    # Le fichier se ferme, meme si la suite leve. Un descripteur laisse
    # ouvert verrouille le fichier sous Windows, et le prochain qui veut
    # y ecrire echoue pour une raison sans rapport avec sa propre faute.
    with io.open(CONFIG, encoding="utf-8") as fh:
        src = fh.read()

    # On INJECTE un repli modele -> modele entre deux alias cloud, c'est-a-dire
    # exactement le defaut que la regle doit voir. On le pose dans la liste
    # `fallbacks` du routeur, sous une source qui n'est PAS un routeur.
    motif = re.search(r"^(\s{2})fallbacks:\s*$", src, re.M)
    assert motif, "liste fallbacks introuvable"
    indent = motif.group(1)
    injection = (motif.group(0) + "\n" +
                 indent + "  - gpt-oss-120b-cloud:\n" +
                 indent + "      - qwen3.5-397b-cloud\n")
    fautif = src.replace(motif.group(0) + "\n", injection, 1)
    assert fautif != src, "injection sans effet"

    with io.open(COPIE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fautif)

    code_sain, sortie_saine = jouer_validateur(CONFIG)
    code_fautif, sortie_fautive = jouer_validateur(COPIE)

    vu = "meme plafond" in sortie_fautive or "meme compte" in sortie_fautive

    print("configuration REELLE  : code %d %s"
          % (code_sain, "(valide)" if code_sain == 0 else "(REFUSEE)"))
    print("configuration FAUTIVE : code %d, regle vue : %s"
          % (code_fautif, vu))
    if vu:
        for ligne in sortie_fautive.splitlines():
            if "meme plafond" in ligne or "meme compte" in ligne:
                print("   " + ligne.strip()[:110])

    try:
        os.remove(COPIE)
    except OSError as exc:
        # UN MENAGE QUI ECHOUE SE DIT. Le remplacer par un `pass` -- ou par
        # `contextlib.suppress`, ce qui revient au meme en plus elegant --
        # ferait de cette ligne un handler muet de plus, la classe 1 que
        # nexus_traque compte deja vingt-huit fois ici. Une copie de
        # configuration laissee sur le disque n'est pas grave ; ne pas savoir
        # qu'elle y est l'est davantage.
        print("menage incomplet : %s subsiste (%s)" % (COPIE, exc))

    ok = (code_sain == 0) and (code_fautif != 0) and vu
    print("-" * 66)
    print("VERDICT : la regle detecte" if ok else "VERDICT : ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(jouer())
