// Le decoupage coupe-t-il un emoji en deux ?
//
// DEFAUT SIGNALE par une equipe voisine, avec differentiel : corpus AVEC
// emojis -> HTTP 500 « surrogates not allowed » ; corpus SANS -> 470 extraits.
// Meme modele, meme appel.
//
// CAUSE : une chaine JavaScript est en UTF-16, et `slice` coupe en UNITES DE
// CODE. Un emoji en occupe DEUX. Une frontiere entre les deux laisse une
// moitie seule, qui ne peut pas s'encoder en UTF-8.
//
// Le banc porte AUSSI les cas degeneres : un correctif qui abandonnerait du
// texte en silence serait pire que le defaut -- l'erreur d'origine, elle, se
// voyait.
const CHUNK_CHARS = 1400;
const CHUNK_OVERLAP = 200;

let echecs = 0;
function verifier(nom, ok, detail) {
  console.log("  [" + (ok ? "OK  " : "RATE") + "] " + nom + " : " + detail);
  if (!ok) echecs++;
}

// Le candidat est injecte : on eprouve la fonction AVANT de la greffer.
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee : tester
// une copie prouverait seulement que la copie fonctionne.
const fs = require("fs");
const path = require("path");
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");
const debut = source.indexOf("function chunkText(text) {");
const fin = source.indexOf("function lineOf(", debut);
if (debut < 0 || fin < 0 || fin - debut < 200) {
  console.error("RATE : chunkText introuvable ou tronque dans server.js");
  process.exit(1);
}
const chunkText = new Function("CHUNK_CHARS", "CHUNK_OVERLAP",
  source.slice(debut, fin) + "; return chunkText;")(CHUNK_CHARS, CHUNK_OVERLAP);

function moitieSeule(s) {
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c >= 0xD800 && c <= 0xDBFF) {
      const d = s.charCodeAt(i + 1);
      if (!(d >= 0xDC00 && d <= 0xDFFF)) return true;
      i++;
    } else if (c >= 0xDC00 && c <= 0xDFFF) {
      return true;
    }
  }
  return false;
}

// --- Le cas qui a casse chez eux : un emoji A LA FRONTIERE ----------------
const EMOJI = "\u{1F512}";            // cadenas, deux unites UTF-16
let texte = "a".repeat(CHUNK_CHARS - 1) + EMOJI + "b".repeat(3000);
let segs = chunkText(texte);
verifier("aucune moitie seule dans un segment",
         segs.every((c) => !moitieSeule(c.text)),
         segs.length + " segments");
verifier("chaque segment s'encode en UTF-8",
         segs.every((c) => {
           try { Buffer.from(c.text, "utf8"); return !moitieSeule(c.text); }
           catch (e) { return false; }
         }),
         "c'est l'erreur exacte que la passerelle renvoyait");

// --- AUCUN TEXTE PERDU : le defaut qu'un correctif naif introduirait ------
//
// Un `break` sur cas degenere abandonnerait le reste du texte SANS LE DIRE.
// L'erreur d'origine, elle, se voyait -- une perte silencieuse est pire.
const couvert = segs.length ? segs[segs.length - 1].start + segs[segs.length - 1].text.length : 0;
verifier("le dernier segment atteint la fin du texte",
         couvert === texte.length,
         "couvert " + couvert + " sur " + texte.length);

// --- CAS ORDINAIRES ------------------------------------------------------
verifier("texte court : un seul segment",
         chunkText("dix signes").length === 1, "");
verifier("texte vide : aucun segment",
         chunkText("").length === 0, "");

const sansEmoji = "x".repeat(5000);
const s2 = chunkText(sansEmoji);
verifier("sans emoji, la couverture est complete",
         s2[s2.length - 1].start + s2[s2.length - 1].text.length === 5000,
         s2.length + " segments");

// --- CAS DEGENERE : un emoji DES LE PREMIER SIGNE ------------------------
const s3 = chunkText(EMOJI + "y".repeat(4000));
verifier("emoji en tete : rien de perdu",
         s3.length > 0 &&
           s3[s3.length - 1].start + s3[s3.length - 1].text.length === 4002,
         s3.length + " segments");

// --- EMOJIS EN RAFALE sur toute la frontiere -----------------------------
const s4 = chunkText(EMOJI.repeat(2000));
verifier("rafale d'emojis : aucune moitie seule",
         s4.every((c) => !moitieSeule(c.text)), s4.length + " segments");
verifier("rafale d'emojis : rien de perdu",
         s4.length > 0 &&
           s4[s4.length - 1].start + s4[s4.length - 1].text.length === 4000,
         "");

console.log("");
if (echecs) { console.log("banc rate : " + echecs + " cas"); process.exit(1); }
console.log("banc tenu");
process.exit(0);
