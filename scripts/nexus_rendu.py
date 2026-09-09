"""
Reparation d'un defaut MESURE du banc : certains modeles rendent le code avec
les entites HTML encodees (&lt; &gt; &amp; &quot;), ce qui casse les marqueurs
de patch et le code lui-meme (defaut #8, confirme en usage reel deux fois).

Regle de prudence : si des marqueurs BRUTS (trois chevrons ouvrants d'affilee)
sont presents, le banc n'a pas encode et un &lt; ailleurs est legitime -- le
texte reste intact. Le de-encodage n'a lieu que sur un rendu ou tout est encode,
et l'appelant l'annonce.
"""
import html


def deencoder_si_entites(texte):
    """Rend (texte_resultat, deencode). Pure, ne leve jamais."""
    try:
        if texte is None or texte == "":
            return (texte, False)
        if ("<" * 3) in texte:
            return (texte, False)
        if "&lt;" in texte or "&gt;" in texte or "&amp;" in texte or "&quot;" in texte:
            return (html.unescape(texte), True)
        return (texte, False)
    except Exception:
        return (texte, False)