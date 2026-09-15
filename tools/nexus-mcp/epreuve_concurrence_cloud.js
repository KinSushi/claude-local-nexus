const fs = require("fs");
const path = require("path");

// ---------- Lecture et extraction du bloc cible ----------
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

// recherche du début du bloc : fonction entierStrictementPositif
const idxStart = source.indexOf("\nfunction entierStrictementPositif(");
if (idxStart < 0) {
  console.error("RATE : fonction `entierStrictementPositif` introuvable dans server.js");
  process.exit(1);
}

// recherche de la fin du bloc : ligne const CONCURRENCE_CLOUD =
const idxEndLine = source.indexOf("\nconst CONCURRENCE_CLOUD =", idxStart);
if (idxEndLine < 0) {
  console.error("RATE : ligne `const CONCURRENCE_CLOUD =` introuvable dans server.js");
  process.exit(1);
}

// on veut inclure toute la ligne de déclaration
const idxEnd = source.indexOf("\n", idxEndLine + 1);
const bloc = source.slice(idxStart + 1, idxEnd >= 0 ? idxEnd : undefined); // +1 pour enlever le \n initial

// validation minimale du bloc
if (bloc.length < 80) {
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
let fn;
try {
  fn = new Function("process", `${bloc}\nreturn CONCURRENCE_CLOUD;`);
} catch (e) {
  console.error(`RATE : impossible de compiler le bloc extrait : ${e.message}`);
  process.exit(1);
}

// ---------- Fonction d'évaluation ----------
function evalBloc(envValue) {
  const env = {};
  if (envValue !== undefined) env.NEXUS_CLOUD_CONCURRENCE = envValue;
  return fn({ env });
}

// ---------- Tests de conformité ----------
try {
  const val = evalBloc(undefined);
  verifier("D1 env absent", val === 10, `valeur observée = ${val}`);
} catch (e) {
  verifier("D1 env absent", false, `exception ${e.message}`);
}

try {
  const val = evalBloc("7");
  verifier("D2 env '7'", val === 7, `valeur observée = ${val}`);
} catch (e) {
  verifier("D2 env '7'", false, `exception ${e.message}`);
}

try {
  const val = evalBloc("abc");
  verifier("R1 env 'abc'", val === 10, `valeur observée = ${val}`);
} catch (e) {
  verifier("R1 env 'abc'", false, `exception ${e.message}`);
}

try {
  const val = evalBloc("0");
  verifier("R2 env '0'", val === 10, `valeur observée = ${val}`);
} catch (e) {
  verifier("R2 env '0'", false, `exception ${e.message}`);
}

try {
  const val = evalBloc("-4");
  verifier("R3 env '-4'", val === 10, `valeur observée = ${val}`);
} catch (e) {
  verifier("R3 env '-4'", false, `exception ${e.message}`);
}

// ---------- R4 : l'ancienne forme ne doit plus être présente ----------
verifier(
  "R4 ancienne forme absente",
  !bloc.includes("NEXUS_CLOUD_CONCURRENCE || 16"),
  bloc.includes("NEXUS_CLOUD_CONCURRENCE || 16") ? "encore présente" : "absente"
);

// ---------- Contre‑épreuve C1 ----------
const ancienneLigne = "const CONCURRENCE_CLOUD = Number(process.env.NEXUS_CLOUD_CONCURRENCE || 16);";
let fnC1;
try {
  fnC1 = new Function("process", `${ancienneLigne}\nreturn CONCURRENCE_CLOUD;`);
} catch (e) {
  verifier("C1 compilation ancienne ligne", false, `exception ${e.message}`);
}

if (fnC1) {
  // cas variable absente → 16
  try {
    const val = fnC1({ env: {} });
    verifier("C1 env absent → 16", val === 16, `valeur observée = ${val}`);
  } catch (e) {
    verifier("C1 env absent → 16", false, `exception ${e.message}`);
  }

  // cas variable 'abc' → NaN
  try {
    const val = fnC1({ env: { NEXUS_CLOUD_CONCURRENCE: "abc" } });
    const ok = Number.isNaN(val);
    verifier("C1 env 'abc' → NaN", ok, `valeur observée = ${val}`);
  } catch (e) {
    verifier("C1 env 'abc' → NaN", false, `exception ${e.message}`);
  }
}

// ---------- Verdict final ----------
console.log("-".repeat(60));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
