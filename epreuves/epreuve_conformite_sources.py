"""
Tests for nexus_conformite controls.

README control found: "33 alias" reported for 54 declared.
Config control found: file modified at 10:22, container started at 23:41
=> 10h40 drift, alias added later but unusable.
"""

import datetime
import os
import shutil
import sys
import tempfile

# add script directory to path
script_dir = os.path.abspath(os.path.dirname(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from nexus_conformite import (
        controle_readme_chiffres,
        controle_config_active,
    )
except Exception as e:  # pragma: no cover
    print("[RATE] import :", e)
    sys.exit(1)

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    if condition:
        print("  [OK  ]", nom, ":", detail)
    else:
        print("  [RATE]", nom, ":", detail)
        echecs += 1


def _write_readme(root, line, phrase=None):
    content = line
    if phrase:
        content += "\n" + phrase
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as f:
        f.write(content)


def _touch_config(root, mtime):
    cfg_path = os.path.join(root, "litellm_config.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("dummy: true\n")
    os.utime(cfg_path, (mtime, mtime))
    return cfg_path


def main():
    # ---------- Controle README ----------
    # 1. FORWARD : numbers concordent
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(
            tmp,
            "  53 alias           53 alias           53 alias",
            "sur les 53 modeles locaux mesures,",
        )

        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 53, "cloud": 53, "anthropic": 53}

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README FORWARD",
            etat == "OK",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 2. REVERSE : premier chiffre diverge
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(
            tmp,
            "  53 alias           19 alias           4 alias",
            "sur les 53 modeles locaux mesures,",
        )

        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 99, "cloud": 99, "anthropic": 99}

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README REVERSE",
            etat == "BLOQUE"
            # L'intention : le detail NOMME LES DEUX VALEURS, celle du README
            # et celle mesuree. Viser un MOT de la formulation casserait au
            # premier reformulage -- et c'est arrive : « la passerelle en
            # expose » est devenu « la configuration en declare », parce que
            # le controle lit la configuration, et que les deux divergent.
            and "53" in detail
            and "99" in detail,
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 3. TROIS divergences
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(
            tmp,
            "  10 alias           20 alias           30 alias",
            "sur les 10 modeles locaux mesures,",
        )

        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 11, "cloud": 11, "anthropic": 11}  # only first differs, but we simulate three diffs via internal logic

        # The control itself will detect three mismatches; we just call it
        etat, detail = controle_readme_chiffres(
            tmp,
            # Uniforme, comme les fixtures : 10/20/30 contre 11/11/11
            # donne exactement TROIS divergences.
            lambda: {"local": 11, "cloud": 11, "anthropic": 11})
        verifier(
            "README TROIS DIVERGENCES",
            etat == "BLOQUE" and detail.startswith("3 divergence"),
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 4. FUITE : lire_modeles lève
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(
            tmp,
            "  53 alias           53 alias           53 alias",
        )

        def lire_modeles():
            raise RuntimeError("cannot read models")

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README FUITE",
            etat == "IGNORE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 5. README absent
    tmp = tempfile.mkdtemp()
    try:
        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 0, "cloud": 0, "anthropic": 0}

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README ABSENT",
            etat == "ALERTE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 6. Ligne introuvable
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(tmp, "some unrelated content")
        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 0, "cloud": 0, "anthropic": 0}

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README LIGNE MANQUANTE",
            etat == "ALERTE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 7. Phrase divergente
    tmp = tempfile.mkdtemp()
    try:
        _write_readme(
            tmp,
            "  53 alias           53 alias           53 alias",
            "sur les 40 modeles locaux mesures,",
        )
        def lire_modeles():
            # Le controle attend un dictionnaire par plan. La valeur
            # est UNIFORME parce que les fixtures de ce test le sont :
            # deviner 19 et 4 ferait echouer le cas pour une raison
            # sans rapport avec ce qu il mesure.
            return {"local": 53, "cloud": 53, "anthropic": 53}

        etat, detail = controle_readme_chiffres(tmp, lire_modeles)
        verifier(
            "README PHRASE DIVERGENTE",
            etat == "ALERTE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # ---------- Controle config active ----------
    # helper dates
    now = datetime.datetime.now()
    older = now - datetime.timedelta(hours=2)
    newer = now + datetime.timedelta(hours=2)

    # 8. FORWARD : fichier plus ancien que demarrage
    tmp = tempfile.mkdtemp()
    try:
        _touch_config(tmp, older.timestamp())

        def date_demarrage():
            return now

        etat, detail = controle_config_active(tmp, date_demarrage)
        verifier(
            "CONFIG FORWARD",
            etat == "OK",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 9. REVERSE : fichier plus recent
    tmp = tempfile.mkdtemp()
    try:
        _touch_config(tmp, newer.timestamp())

        def date_demarrage():
            return now

        etat, detail = controle_config_active(tmp, date_demarrage)
        verifier(
            "CONFIG REVERSE",
            etat == "ALERTE"
            and "docker compose restart litellm" in detail,
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 10. Detail doit contenir les deux instants
    tmp = tempfile.mkdtemp()
    try:
        _touch_config(tmp, older.timestamp())

        def date_demarrage():
            return now

        etat, detail = controle_config_active(tmp, date_demarrage)
        verifier(
            "CONFIG DETAIL COMPLET",
            etat == "OK"
            # La specification demande « AAAA-MM-JJ HH:MM », pas de l'ISO a
            # la seconde. Le test contredisait sa propre consigne.
            and older.strftime("%Y-%m-%d %H:%M") in detail
            and now.strftime("%Y-%m-%d %H:%M") in detail,
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 11. FUITE : date_demarrage lève
    tmp = tempfile.mkdtemp()
    try:
        _touch_config(tmp, older.timestamp())

        def date_demarrage():
            raise RuntimeError("cannot get start time")

        etat, detail = controle_config_active(tmp, date_demarrage)
        verifier(
            "CONFIG FUITE",
            etat == "IGNORE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # 12. ANTI-CONTROLE REEL : ce controle ne rend JAMAIS "BLOQUE".
    #
    # CE QUI ETAIT FAUX : ce cas etait une boucle VIDE se declarant « deja
    # couverte ». Elle n'affirmait rien -- un vert qui ne peut pas rougir,
    # dans l'epreuve meme qui garde les autres.
    #
    # L'enjeu est reel : la conformite tourne AVANT le demarrage de la pile.
    # Bloquer sur « la passerelle sert une configuration perimee »
    # empecherait precisement la sequence qui la redemarre.
    tmp = tempfile.mkdtemp()
    try:
        base = datetime.datetime.now()
        situations = [
            ("fichier ancien", base - datetime.timedelta(hours=2), lambda: base),
            ("fichier recent", base + datetime.timedelta(hours=2), lambda: base),
            ("demarrage indisponible", base,
             lambda: (_ for _ in ()).throw(RuntimeError("conteneur arrete"))),
        ]
        jamais = True
        vus = []
        for nom, quand, demarrage in situations:
            _touch_config(tmp, quand.timestamp())
            etat, _detail = controle_config_active(tmp, demarrage)
            vus.append("%s=%s" % (nom, etat))
            if etat == "BLOQUE":
                jamais = False
        # Et le cas du fichier absent, quatrieme situation.
        vide = tempfile.mkdtemp()
        try:
            etat, _detail = controle_config_active(vide, lambda: base)
            vus.append("config absente=%s" % etat)
            if etat == "BLOQUE":
                jamais = False
        finally:
            shutil.rmtree(vide, ignore_errors=True)

        verifier(
            "CONFIG NE BLOQUE JAMAIS",
            jamais,
            " ; ".join(vus),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 13. Fichier absent
    tmp = tempfile.mkdtemp()
    try:
        def date_demarrage():
            return now

        etat, detail = controle_config_active(tmp, date_demarrage)
        verifier(
            "CONFIG ABSENT",
            etat == "ALERTE",
            f"etat={etat} detail={detail}",
        )
    finally:
        shutil.rmtree(tmp)

    # bilan
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
