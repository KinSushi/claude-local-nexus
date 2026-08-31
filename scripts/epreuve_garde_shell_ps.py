# -*- coding: utf-8 -*-
"""Le garde shell juge-t-il PowerShell, et le juge-t-il AVEC SES PROPRES REGLES ?

CE QUI ETAIT FAUX, mesure le 2026-08-31 : la meme commande dangereuse,
soumise sous deux noms d'outil, donnait deux verdicts opposes.

    tool_name = "Bash"        -> REFUSE
    tool_name = "PowerShell"  -> PASSE

Le trou avait DEUX etages : le matcher de .claude/settings.json, qui ne
nommait que « Bash », et la ligne `if tool_name != "Bash": return` du garde
lui-meme. En elargir un seul aurait laisse l'autre fermer la porte.

MAIS ELARGIR SANS ADAPTER AURAIT ETE PIRE QUE LE TROU. Les deux regles
existantes sont propres a bash : le heredoc du CAS A n'existe pas en
PowerShell, et l'accent grave du CAS B y est le caractere d'ECHAPPEMENT
ordinaire, la ou bash en fait une substitution de commande. Un garde qui
refuse le travail normal se fait desarmer -- c'est le risque principal, plus
grave que le trou.

L'anti-controle est donc aussi important que le controle, et il porte la
moitie des cas ci-dessous.
"""
import json
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GARDE = os.path.join(RACINE, "scripts", "nexus_garde_shell.py")

echecs = 0


def verifier(nom, condition, detail):
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    global echecs
    if not condition:
        echecs += 1


def soumettre(outil, commande):
    """Le verdict du garde sur une commande, tel qu'un hook le recevrait."""
    charge = json.dumps({"tool_name": outil, "tool_input": {"command": commande}})
    r = subprocess.run([sys.executable, GARDE], input=charge,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    sortie = (r.stdout or "") + (r.stderr or "")
    return "deny" in sortie.lower()


def main():
    global echecs
    echecs = 0

    # --- Le trou mesure : la meme commande, deux outils ------------------- #
    #
    # L'accent grave entre guillemets doubles est une substitution de commande
    # en bash -- un message de commit citant du code partait ampute de ses
    # noms techniques, sans que rien ne le signale. C'est arrive ici le
    # 2026-08-30.
    ACCENT_GRAVE = 'git commit -m "voir `nexus_bench.py` pour la mesure"'
    verifier("bash : accent grave refuse", soumettre("Bash", ACCENT_GRAVE),
             "substitution de commande, le cas du 2026-08-30")

    # ANTI-CONTROLE, et c'est le cas qui empeche le garde d'etre desarme :
    # la MEME commande doit PASSER en PowerShell, ou l'accent grave n'est que
    # le caractere d'echappement. Refuser ici punirait du travail legitime.
    verifier("powershell : accent grave PASSE", not soumettre("PowerShell", ACCENT_GRAVE),
             "en PowerShell l'accent grave echappe, il ne substitue pas")

    # --- La regle propre a PowerShell ------------------------------------- #
    #
    # Le delimiteur de fermeture d'une here-string doit etre en COLONNE ZERO.
    # L'indenter est une erreur de syntaxe : la commande echoue avant d'avoir
    # rien fait.
    INDENTEE = (
        "git commit -m @'\n"
        "Un message sur plusieurs lignes.\n"
        "    '@\n"
    )
    verifier("powershell : here-string indentee refusee", soumettre("PowerShell", INDENTEE),
             "'@ indente est une erreur de syntaxe PowerShell")

    CORRECTE = (
        "git commit -m @'\n"
        "Un message sur plusieurs lignes.\n"
        "'@\n"
    )
    verifier("powershell : here-string correcte PASSE", not soumettre("PowerShell", CORRECTE),
             "fermeture en colonne zero : rien a reprocher")

    # --- Les regles bash ne debordent PAS sur PowerShell ------------------- #
    #
    # Un heredoc n'existe pas en PowerShell ; appliquer le CAS A la-bas
    # refuserait une chaine qui n'a rien de dangereux.
    HEREDOC = "python - <<'ZZ'\nimport re\nprint(re.sub(r'\\\\d', '', 'a1'))\nZZ\n"
    verifier("bash : heredoc a antislash refuse", soumettre("Bash", HEREDOC),
             "le shell consomme l'antislash avant Python")
    verifier("powershell : le CAS A ne deborde pas", not soumettre("PowerShell", HEREDOC),
             "un heredoc n'existe pas en PowerShell")

    # --- Le travail PowerShell ordinaire passe ---------------------------- #
    #
    # Sans ces cas, un garde qui refuse tout paraitrait parfait.
    ORDINAIRES = [
        ("continuation de ligne", "Get-ChildItem -Path C:\\temp `\n    -Recurse"),
        ("variable echappee", 'Write-Host "valeur : `$brut"'),
        ("commande simple", "Get-ScheduledTask | Format-List"),
    ]
    for nom, cmd in ORDINAIRES:
        verifier("powershell ordinaire : %s" % nom, not soumettre("PowerShell", cmd),
                 "le travail normal ne doit jamais etre refuse")

    # --- Un outil tiers n'est pas juge ------------------------------------ #
    verifier("outil inconnu ignore", not soumettre("Read", ACCENT_GRAVE),
             "ce garde ne juge que les deux shells")

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
