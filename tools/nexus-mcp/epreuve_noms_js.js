// Une fonction appelee existe-t-elle encore ?
//
// Defaut REEL du 2026-08-30, et paye en production : un correctif a remplace
// une REGION de server.js delimitee par deux commentaires, et cette region
// contenait aussi sansRaisonnement() et mentionsReponse(). Les deux sont
// restees appelees en six endroits. `node --check` a passe -- il valide la
// SYNTAXE, jamais la resolution des noms -- et les epreuves existantes
// extraient des blocs isoles, donc aucune ne pouvait le voir. Le serveur a
// plante a son redemarrage suivant, chez une session voisine.
//
// Le controle est volontairement ETROIT, comme son cousin Python : un appel
// NU (pas `obj.methode()`) a un nom qui n'est lie nulle part dans le fichier
// et qui n'est pas un global connu. Un detecteur qui crie a tort est desarme
// le jour meme.
const fs = require("fs");
const path = require("path");

const CHEMIN = path.join(__dirname, "server.js");
const source = sansCommentairesDeBloc(fs.readFileSync(CHEMIN, "utf8"));

// Globals de JavaScript et de Node employes ici. La liste est volontairement
// large : un faux positif coute plus cher qu'un manque.
const GLOBAUX = new Set([
  "require", "String", "Number", "Boolean", "Object", "Array", "Symbol",
  "Promise", "Error", "TypeError", "RangeError", "JSON", "Math", "Date",
  "RegExp", "Map", "Set", "WeakMap", "WeakSet", "parseInt", "parseFloat",
  "isNaN", "isFinite", "encodeURIComponent", "decodeURIComponent", "escape",
  "unescape", "setTimeout", "clearTimeout", "setInterval", "clearInterval",
  "setImmediate", "queueMicrotask", "Buffer", "process", "console",
  "structuredClone", "AbortController", "URL", "URLSearchParams", "TextEncoder",
  "TextDecoder", "Function", "BigInt", "Proxy", "Reflect", "fetch",
  "if", "for", "while", "switch", "catch", "return", "function", "typeof",
  "await", "yield", "new", "delete", "void", "in", "of", "do", "else",
  "async", "super", "try", "throw", "case", "default", "extends", "this",
  "import", "export", "class", "const", "let", "var", "instanceof",
]);

// Les commentaires de BLOC doivent partir avant toute analyse. Sans cela,
// « separement (phase MAP) » dans un commentaire francais se lisait comme un
// appel a une fonction nommee « ment » : les accents ne sont pas des
// caracteres de mot pour le motif, et le fragment restant l'etait.
function sansCommentairesDeBloc(src) {
  // Les sauts de ligne sont conserves pour que les numeros ne bougent pas.
  return src.replace(/\/\*[\s\S]*?\*\//g,
                     (bloc) => bloc.replace(/[^\r\n]/g, " "));
}

function nomsLies(src) {
  const lies = new Set();
  const ajouter = (re, groupe) => {
    for (const m of src.matchAll(re)) {
      const brut = m[groupe || 1];
      if (!brut) continue;
      // Une destructuration donne plusieurs noms d'un coup.
      for (const n of brut.split(/[,{}\[\]:]+/)) {
        const propre = n.trim().split("=")[0].trim().replace(/^\.\.\./, "");
        if (/^[A-Za-z_$][\w$]*$/.test(propre)) lies.add(propre);
      }
    }
  };
  ajouter(/\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)/g);
  ajouter(/\b(?:const|let|var)\s+([^=;\n]+)=/g);
  ajouter(/\bclass\s+([A-Za-z_$][\w$]*)/g);
  ajouter(/\bcatch\s*\(\s*([A-Za-z_$][\w$]*)/g);
  // Parametres de fonction, fleches comprises.
  ajouter(/\bfunction\s*\*?\s*[A-Za-z_$][\w$]*\s*\(([^)]*)\)/g);
  ajouter(/\bfunction\s*\*?\s*\(([^)]*)\)/g);
  ajouter(/\(([^()]*)\)\s*=>/g);
  ajouter(/(?:^|[^\w$.])([A-Za-z_$][\w$]*)\s*=>/gm);
  // Methodes d'objet litteral : `nom(...) {`
  ajouter(/^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/gm);
  ajouter(/^\s*(?:get|set)\s+([A-Za-z_$][\w$]*)\s*\(/gm);
  return lies;
}

function appelsNus(src) {
  // Le nom n'est precede ni d'un point, ni d'un mot -- donc pas une methode,
  // pas un mot-cle colle, et pas la definition elle-meme.
  const trouves = new Map();
  const lignes = src.split("\n");
  lignes.forEach((ligne, i) => {
    const sansChaines = ligne
      .replace(/"(?:[^"\\]|\\.)*"/g, '""')
      .replace(/'(?:[^'\\]|\\.)*'/g, "''")
      .replace(/`(?:[^`\\]|\\.)*`/g, "``")
      .replace(/\/\/.*$/, "");
    for (const m of sansChaines.matchAll(/(^|[^\w$.])([A-Za-z_$][\w$]*)\s*\(/g)) {
      const nom = m[2];
      if (!trouves.has(nom)) trouves.set(nom, i + 1);
    }
  });
  return trouves;
}

function manquants(src) {
  const lies = nomsLies(src);
  const dehors = [];
  for (const [nom, ligne] of appelsNus(src)) {
    if (GLOBAUX.has(nom) || lies.has(nom)) continue;
    dehors.push({ nom, ligne });
  }
  return dehors;
}

let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

// 1. Le fichier reel ne doit appeler aucune fonction disparue.
{
  const absents = manquants(source);
  verifier("server.js : aucune fonction appelee sans definition",
           absents.length === 0,
           absents.length ? absents.map((a) => `${a.nom} (ligne ${a.ligne})`).join(", ")
                          : "toutes les fonctions appelees sont definies");
}

// 2. CONTRE-EPREUVE : on rejoue la suppression reelle. Sans elle, le cas 1
// passerait aussi avec un motif casse.
{
  const debut = source.indexOf("function sansRaisonnement(");
  let profondeur = 0, fin = -1;
  for (let i = source.indexOf("{", debut); i < source.length; i++) {
    if (source[i] === "{") profondeur++;
    else if (source[i] === "}") { profondeur--; if (!profondeur) { fin = i + 1; break } }
  }
  if (debut < 0 || fin < 0) {
    verifier("contre-epreuve : suppression rejouable", false,
             "sansRaisonnement introuvable, le fichier a change de forme");
  } else {
    const ampute = source.slice(0, debut) + source.slice(fin);
    const absents = manquants(ampute);
    verifier("contre-epreuve : la suppression reelle est bien VUE",
             absents.some((a) => a.nom === "sansRaisonnement"),
             absents.length ? absents.map((a) => a.nom).join(", ") : "rien vu");
  }
}

console.log("-".repeat(64));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
