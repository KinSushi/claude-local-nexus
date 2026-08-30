// Un corps vide dit-il pourquoi il est vide ?
//
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee : tester
// une copie ne prouverait que la copie. Elle rejoue le cas MESURE le
// 2026-08-30 -- glm-5.3-cloud, 8234 jetons, corps vide -- et non un cas
// invente pour la circonstance.
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

const debut = source.indexOf("function mentionsReponse(");
if (debut < 0) {
  console.error("RATE : mentionsReponse introuvable dans server.js");
  process.exit(1);
}
// Jusqu'a l'accolade fermante de premier niveau.
let profondeur = 0, fin = -1;
for (let i = source.indexOf("{", debut); i < source.length; i++) {
  if (source[i] === "{") profondeur++;
  else if (source[i] === "}") { profondeur--; if (profondeur === 0) { fin = i + 1; break } }
}
if (fin < 0) {
  console.error("RATE : corps de mentionsReponse non delimite");
  process.exit(1);
}
const bloc = source.slice(debut, fin);

const module_ = { exports: {} };
new Function("module", bloc + "\nmodule.exports = mentionsReponse;")(module_);
const mentionsReponse = module_.exports;

let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

// 1. Le cas MESURE : le modele a produit 8234 jetons, et le corps est vide
// parce que sa balise de pensee n'a jamais ete refermee.
{
  const m = mentionsReponse({ text: "", tokens_sortie: 8234, tronquee: false });
  verifier("corps vide malgre des jetons produits : la raison est dite",
           m.includes("apres retrait du raisonnement") && m.includes("8234"),
           JSON.stringify(m));
}

// 2. Le cas voisin, et il ne faut PAS l'accuser du meme motif : le modele
// n'a rien emis du tout.
{
  const m = mentionsReponse({ text: "", tokens_sortie: 0, tronquee: false });
  verifier("aucun jeton produit : le retrait du raisonnement n'est pas accuse",
           m.includes("aucun jeton") && !m.includes("retrait du raisonnement"),
           JSON.stringify(m));
}

// 3. Le libelle historique est repris MOT POUR MOT. Un premier jet avait
// ecrit « a ${result.max_tokens} tokens » -- champ inexistant, donc
// « a undefined tokens » : une mention juste changee en mention cassee.
{
  const m = mentionsReponse({ text: "une reponse", tokens_sortie: 12, tronquee: true });
  verifier("libelle de troncature inchange et sans valeur substituee",
           m.includes("REPONSE TRONQUEE a max_tokens") && !m.includes("undefined"),
           JSON.stringify(m));
}

// 4. Les deux peuvent coexister : coupe par max_tokens AU MILIEU du
// raisonnement, donc tronquee ET vide.
{
  const m = mentionsReponse({ text: "", tokens_sortie: 2048, tronquee: true });
  verifier("troncature et vide annonces tous les deux",
           m.includes("TRONQUEE") && m.includes("retrait du raisonnement"),
           JSON.stringify(m));
}

// 5. Le silence quand tout va bien. Une mention qui s'affiche toujours ne
// veut plus rien dire.
{
  const m = mentionsReponse({ text: "tout va bien", tokens_sortie: 42, tronquee: false });
  verifier("silence sur une reponse saine", m === "", JSON.stringify(m));
}

// 6. Aucun accent dans ce qui s'affiche : la sortie passe par cp1252.
{
  const cas = [
    { text: "", tokens_sortie: 8234, tronquee: false },
    { text: "", tokens_sortie: 0, tronquee: false },
    { text: "x", tokens_sortie: 1, tronquee: true },
  ];
  // Le point median separateur est admis : il est deja dans les en-tetes.
  const fautifs = cas.map(mentionsReponse)
                     .filter((m) => /[À-ÿ]/.test(m.replace(/·/g, "")));
  verifier("aucun accent dans les libelles rendus", fautifs.length === 0,
           fautifs.length ? JSON.stringify(fautifs) : "trois libelles en pur ASCII");
}

// 7. CONTRE-EPREUVE. Tout ce qui precede passerait aussi si le harnais ne
// voyait rien. On lui soumet la version d'AVANT -- celle qui n'annoncait que
// la troncature -- et il doit la refuser.
{
  const avant = (result) => (result.tronquee ? " · REPONSE TRONQUEE a max_tokens" : "");
  const m = avant({ text: "", tokens_sortie: 8234, tronquee: false });
  verifier("contre-epreuve : la version d'avant est bien VUE",
           !(m.includes("retrait du raisonnement") && m.includes("8234")),
           `l'ancienne version rend ${JSON.stringify(m)} sur le cas mesure`);
}

console.log("-".repeat(60));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
