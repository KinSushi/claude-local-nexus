import sys
import subprocess
import pathlib
import re

def _print_rate(message: str) -> None:
    print(f"[RATE] refus_verrou : {message}")

def _translate_line(line: str):
    """
    Retourne un tuple (type, texte) où type est 'OK' ou 'RATE' et texte la ligne formatée.
    Retourne None si la ligne ne correspond à aucun format attendu.
    """
    line = line.strip()
    if not line:
        return None
    m_ok = re.fullmatch(r'\[(?P<name>[^\]]+)\]\s*OK\s*', line)
    if m_ok:
        name = m_ok.group('name')
        return ('OK', f"[OK  ] {name} : ok")
    # Tout ce qui n'est pas OK est considéré comme échec ou autre statut
    m_fail = re.fullmatch(r'\[(?P<name>[^\]]+)\]\s*FAIL\s+(?P<detail>.*)', line)
    if m_fail:
        name = m_fail.group('name')
        detail = m_fail.group('detail')
        return ('RATE', f"[RATE] {name} : {detail}")
    # Cas générique non-OK
    m_other = re.fullmatch(r'\[(?P<name>[^\]]+)\]\s*(?P<detail>.+)', line)
    if m_other:
        name = m_other.group('name')
        detail = m_other.group('detail')
        return ('RATE', f"[RATE] {name} : {detail}")
    return None

def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    tool_path = root / 'outillage' / 'nexus_epreuve_refus.py'

    if not tool_path.is_file():
        _print_rate(f"outil introuvable {tool_path}")
        sys.exit(1)

    try:
        result = subprocess.run(
            [sys.executable, str(tool_path), '--epreuve'],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        _print_rate("pas de reponse en 300 s")
        sys.exit(1)

    translated = 0
    all_ok = True

    for raw_line in result.stdout.splitlines():
        translated_line = _translate_line(raw_line)
        if translated_line is None:
            continue
        line_type, out_line = translated_line
        print(out_line)
        translated += 1
        if line_type != 'OK':
            all_ok = False

    if translated == 0:
        _print_rate("aucun cas rendu")
        sys.exit(1)

    if all_ok and result.returncode == 0:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()