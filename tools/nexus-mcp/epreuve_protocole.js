// Un refus nomme-t-il le parametre ET l'issue -- et refuse-t-il ce qu'il croit refuser ?
//
// Mesure du 2026-08-30, vague 2 : sur 32 cas de protocole, douze refus
// nommaient le parametre fautif sans jamais dire ce qu'il fallait fournir.
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee.
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

// La tranche qui va de la classe d'erreur au dernier helper de validation.
const debut = source.indexOf("class ErreurProtocole");
const fin = source.indexOf("function exigerTexte(");
if (debut < 0 || fin < 0) {
  console.error("RATE : helpers de validation introuvables");
  process.exit(1);
}
const finTexte = source.indexOf("\n}\n", fin) + 3;
const bloc = source.slice(debut, finTexte);
// `indexOf` rend -1 quand il ne trouve rien, donc finTexte valait 2 et la
// tranche faisait DEUX caracteres. Les helpers n'auraient pas ete definis,
// et les neuf cas suivants auraient tous echoue -- ou pire, passe a vide
// selon la forme du code. Un seuil de taille attrape les deux cas.
if (finTexte < debut || bloc.length < 400 || !bloc.includes("function exigerTexte")) {
  console.error("RATE : bloc des helpers vide ou tronque (%d caracteres)", bloc.length);
  process.exit(1);
}

const module_ = { exports: {} };
new Function("module", bloc +
  "\nmodule.exports = { ErreurProtocole, exigerTableau, exigerTexte," +
  " exigerTableauNonVide, exigerEntierPositif };")(module_);
const H = module_.exports;

let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}
function messageDe(fn) {
  try { fn(); return null } catch (e) { return e.message }
}

// 1. Le critere du depot : le refus nomme le parametre ET l'issue.
{
  const m = messageDe(() => H.exigerTableauNonVide([], "paths", 1, "chemin de fichier"));
  verifier("tableau vide : le refus nomme le parametre et l'issue",
           m && m.includes("'paths'") && m.includes("au moins 1") &&
           m.includes("chemin de fichier"), JSON.stringify(m));
}

// 2. Le seuil se regle, et le message le dit avec le bon nombre.
{
  // Le mot est fourni par l'appelant, accord compris : le helper ne devine
  // pas un pluriel, et « au moins 2 modele » se lisait mal.
  const m = messageDe(() => H.exigerTableauNonVide(["a"], "models", 2, "modeles"));
  verifier("seuil de deux : le message annonce deux, pas un",
           m && m.includes("au moins 2 modeles") && m.includes("recu 1"),
           JSON.stringify(m));
}

// 3. Le helper delegue le controle de type a exigerTableau plutot que de le
// refaire : deux controles du meme fait finissent par diverger.
{
  const m = messageDe(() => H.exigerTableauNonVide("pas un tableau", "paths", 1, "chemin"));
  verifier("non-tableau : le message de type est celui d'exigerTableau",
           m && m.includes("un tableau est attendu") && m.includes("recu string"),
           JSON.stringify(m));
}

// 4. max_tokens negatif etait ACCEPTE en silence et transmis a la passerelle,
// parce que -1 est vrai au sens de JavaScript.
{
  const m = messageDe(() => H.exigerEntierPositif(-1, "max_tokens"));
  verifier("max_tokens negatif : refuse, et la VALEUR est montree",
           m && m.includes("-1") && !m.includes("recu number"), JSON.stringify(m));
}

// 5. Le parametre reste optionnel : un defaut s'applique en son absence.
{
  const passe = H.exigerEntierPositif(undefined, "max_tokens") === undefined &&
                H.exigerEntierPositif(2048, "max_tokens") === 2048;
  verifier("optionnel absent et valeur valide passent", passe,
           "undefined et 2048 traverses sans erreur");
}

// 6. Zero et non-entier sont refuses aussi : un plafond de zero jeton est
// aussi absurde qu'un plafond negatif.
{
  const zero = messageDe(() => H.exigerEntierPositif(0, "max_tokens"));
  const demi = messageDe(() => H.exigerEntierPositif(1.5, "max_tokens"));
  verifier("zero et non-entier refuses", Boolean(zero) && Boolean(demi),
           `0 -> ${JSON.stringify(zero)} ; 1.5 -> ${JSON.stringify(demi)}`);
}

// 7. CONTRE-EPREUVE du defaut de CORRECTION. `!args.prompt` laissait passer
// une chaine d'espaces et un NOMBRE. exigerTexte refuse les deux : c'est
// bien une correction, pas seulement une reformulation.
{
  const ancien = (v) => { if (!v) throw new Error("parametre 'prompt' requis") };
  const laissaitPasser = [123, "   "].filter((v) => messageDe(() => ancien(v)) === null);
  const refusesMaintenant = [123, "   "].filter(
    (v) => messageDe(() => H.exigerTexte(v, "prompt")) !== null);
  verifier("contre-epreuve : ce que l'ancien refus laissait passer est refuse",
           laissaitPasser.length === 2 && refusesMaintenant.length === 2,
           `ancien laissait passer ${JSON.stringify(laissaitPasser)}, exigerTexte les refuse`);
}

// 8. Structurel : plus aucune validation de parametre ecrite a la main hors
// des helpers. C'est la regle, et non l'un de ses cas, qui est gardee ici.
{
  const aLaMain = source.split("\n")
    .map((l, i) => ({ n: i + 1, l }))
    .filter(({ n, l }) => /throw new ErreurProtocole\("parametre /.test(l) &&
                          !(n >= 1862 - 1 && n <= finTexte));
  const horsHelpers = aLaMain.filter(({ l }) => !/^\s{4}throw new ErreurProtocole\(\s*$/.test(l));
  const dansHelpers = source.slice(debut, finTexte);
  const restants = horsHelpers.filter(({ l }) => !dansHelpers.includes(l));
  verifier("aucune validation de parametre ecrite a la main hors des helpers",
           restants.length === 0,
           restants.length ? restants.map((r) => `ligne ${r.n}`).join(", ")
                           : "les quatre helpers sont les seuls a refuser");
}

// 9. Le refus d'un outil inconnu DEDUIT sa liste plutot que de la recopier.
// Une liste en dur divergerait le jour ou un outil est ajoute, et un refus
// qui ment sur ce qui existe est pire qu'un refus muet.
{
  const bloc = source.slice(source.indexOf('"outil inconnu : "'), source.indexOf('"outil inconnu : "') + 300);
  verifier("la liste des outils connus est deduite de TOOLS",
           bloc.includes("TOOLS.map"), bloc.includes("TOOLS.map") ? "derivee de TOOLS" : bloc.slice(0, 80));
}

console.log("-".repeat(60));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
