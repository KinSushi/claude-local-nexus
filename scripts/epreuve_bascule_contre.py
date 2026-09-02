"""Contre-epreuve : l'epreuve de bascule MORD-ELLE si on casse la regle ?

Un vert ne prouve rien tant qu'on n'a pas montre que le rouge est atteignable.
On fabrique une COPIE du depot avec une liste de replis fautive, et on verifie
que l'epreuve echoue dessus. Le depot reel n'est JAMAIS modifie.
"""
import pathlib, re, shutil, subprocess, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RACINE = pathlib.Path("scripts")
FAUTES = {
    "alias FACTURE ajoute": '["gpt-oss-120b-cloud", "claude-sonnet-5", "glm-4.7-flash-local"]',
    "AUCUN candidat local": '["gpt-oss-120b-cloud"]',
}

def _main() -> int:
    src_agent = (RACINE / "nexus_agent.py").read_text(encoding="utf-8")
    motif = re.compile(r"^REPLIS_GRATUITS = \[[^\]]*\]", re.M)
    if not motif.search(src_agent):
        print("  <<< liste des replis introuvable, contre-epreuve impossible")
        raise SystemExit(2)

    echecs = 0
    for nom, remplacement in FAUTES.items():
        with tempfile.TemporaryDirectory() as td:
            faux = pathlib.Path(td) / "scripts"
            shutil.copytree(RACINE, faux)
            (faux / "nexus_agent.py").write_text(
                motif.sub("REPLIS_GRATUITS = " + remplacement, src_agent, count=1),
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "-B", str(faux / "epreuve_bascule.py")],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            mord = r.returncode != 0
            print(
                f"  [{'OK ' if mord else 'RATE'}] {nom:<24} code={r.returncode} "
                f"{'-> elle MORD' if mord else '<<< ELLE LAISSE PASSER'}"
            )
            if not mord:
                echecs += 1
                print(f"        sortie : {(r.stdout or r.stderr)[:160]}")

    # et le depot reel doit rester vert
    r = subprocess.run(
        [sys.executable, "-B", "scripts/epreuve_bascule.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    ok = r.returncode == 0
    print(f"  [{'OK ' if ok else 'RATE'}] depot REEL inchange       code={r.returncode}")
    if not ok:
        echecs += 1

    return 1 if echecs else 0

if __name__ == "__main__":
    sys.exit(_main())
