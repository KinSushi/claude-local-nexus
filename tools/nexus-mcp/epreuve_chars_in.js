const fs = require("fs");
const path = require("path");

// ---------- Lecture et extraction du bloc cible ----------
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

// recherche du début du bloc : fonction caracteresEntree
const idxStart = source.indexOf("\nfunction caracteresEntree(");
if (idxStart < 0) {
  console.error("RATE : fonction caracteresEntree introuvable dans server.js");
  process.exit(1);
}

// recherche de la fin du bloc : ligne contenant uniquement '}'
const idxEnd = source.indexOf("\n}\n", idxStart);
if (idxEnd < 0) {
  console.error("RATE : fin du bloc caracteresEntree introuvable dans server.js");
  process.exit(1);
}

// on veut inclure le caractère '}' de fin
const bloc = source.slice(idxStart + 1, idxEnd + 2); // +1 pour enlever le \n initial, +2 pour garder le '}'

// validation minimale du bloc
if (bloc.length < 50) {
  console.error(`RATE : bloc extrait trop petit (${bloc.length} caractères)`);
  process.exit(1);
}

// ---------- Fonction utilitaire de vérification ----------
let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

// ---------- Compilation du bloc ----------
let caracteresEntree;
try {
  const fn = new Function(`${bloc}\nreturn caracteresEntree;`);
  caracteresEntree = fn();
} catch (e) {
  console.error(`RATE : impossible de compiler le bloc extrait : ${e.message}`);
  process.exit(1);
}

// ---------- Tests de conformité ----------
function tester(nom, input, attendu) {
  try {
    const val = caracteresEntree(input);
    verifier(nom, val === attendu, `valeur observée = ${val}`);
  } catch (e) {
    verifier(nom, false, `exception ${e.message}`);
  }
}

// F1
tester("F1 simple texte", [{ role: "user", content: "abc" }], 3);

// F2
tester(
  "F2 plusieurs messages",
  [
    { role: "system", content: "a".repeat(100) },
    { role: "user", content: "b".repeat(200) },
  ],
  300
);

// F3
tester(
  "F3 contenu tableau mixte",
  [
    {
      role: "user",
      content: [
        { type: "text", text: "c".repeat(90) },
        { type: "image_url", image_url: { url: "data:x" } },
      ],
    },
  ],
  90
);

// R1 - undefined
tester("R1 undefined", undefined, 0);
// R1 - null
tester("R1 null", null, 0);
// R1 - string
tester("R1 string", "abc", 0);

// R2 - tableau hétérogène
tester(
  "R2 tableau hétérogène",
  [null, { role: "user" }, { role: "user", content: 5 }, { role: "user", content: "dddd" }],
  4
);

// R3 - tableau vide
tester("R3 tableau vide", [], 0);

// ---------- Contre‑épreuve C1 ----------
verifier(
  "C1 chars_in présent",
  source.includes("chars_in:"),
  source.includes("chars_in:") ? "présent" : "chars_in absent de l'evenement"
);

// ---------- Verdict final ----------
console.log("-".repeat(60));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
