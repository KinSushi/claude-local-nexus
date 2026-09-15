const fs = require("fs");
const path = require("path");

// ---------- Lecture et extraction du bloc cible ----------
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

// recherche de l'appel qui utilise le sémaphore cloud MACHINE
const idxCall = source.indexOf("tenirVerrou(classeSem, { semaphore: n })");
if (idxCall < 0) {
  console.error("RATE : appel `tenirVerrou` introuvable dans server.js");
  process.exit(1);
}

// le bloc se termine juste avant le `try {` qui précède cet appel
const idxTry = source.lastIndexOf("try {", idxCall);
if (idxTry < 0) {
  console.error("RATE : `try {` précédant l'appel introuvable");
  process.exit(1);
}

// le bloc commence à la dernière déclaration `const classeSem` avant le `try {`
const idxStart = source.lastIndexOf("const classeSem", idxTry);
if (idxStart < 0) {
  console.error("RATE : déclaration `const classeSem` introuvable");
  process.exit(1);
}

// extraction du bloc
let bloc = source.slice(idxStart, idxTry);

// validation minimale du bloc
if (bloc.length < 40) {
  console.error(`RATE : bloc extrait trop petit (${bloc.length} caractères)`);
  process.exit(1);
}
// ---------- Fonction utilitaire de vérification ----------
let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

// ---------- Évaluation du bloc ----------
let fn;
try {
  fn = new Function("process", `${bloc}\nreturn n;`);
} catch (e) {
  console.error(`RATE : impossible de compiler le bloc extrait : ${e.message}`);
  process.exit(1);
}

// ---------- Tests de conformité ----------
function evalBloc(envValue) {
  const env = {};
  if (envValue !== undefined) env.NEXUS_CLOUD_CONCURRENCE = envValue;
  return fn({ env });
}

// 1. F1 : env = '7' → n doit être 7
try {
  const n = evalBloc("7");
  verifier("F1 env '7'", n === 7, `n = ${n}`);
} catch (e) {
  verifier("F1 env '7'", false, `exception ${e.message}`);
}

// 2. F2 : env absent → n doit être 10
try {
  const n = evalBloc(undefined);
  verifier("F2 env absent", n === 10, `n = ${n}`);
} catch (e) {
  verifier("F2 env absent", false, `exception ${e.message}`);
}

// 3. R1 : env = '0' → n doit être 10
try {
  const n = evalBloc("0");
  verifier("R1 env '0'", n === 10, `n = ${n}`);
} catch (e) {
  verifier("R1 env '0'", false, `exception ${e.message}`);
}

// 4. R2 : env = 'abc' → n doit être 10
try {
  const n = evalBloc("abc");
  verifier("R2 env 'abc'", n === 10, `n = ${n}`);
} catch (e) {
  verifier("R2 env 'abc'", false, `exception ${e.message}`);
}

// 5. R3 : env = '-3' → n doit être 10
try {
  const n = evalBloc("-3");
  verifier("R3 env '-3'", n === 10, `n = ${n}`);
} catch (e) {
  verifier("R3 env '-3'", false, `exception ${e.message}`);
}

// 6. R4 : l'identifiant nu, marque du defaut de 39877fb, ne doit plus figurer dans le bloc
verifier("R4 identifiant nu absent", !bloc.includes("typeof NEXUS_CLOUD_CONCURRENCE"), !bloc.includes("typeof NEXUS_CLOUD_CONCURRENCE") ? "absent" : "encore présent");

// ---------- Contre‑épreuve C1 ----------
const ligneFausse = "    const n = (typeof NEXUS_CLOUD_CONCURRENCE === 'number' && NEXUS_CLOUD_CONCURRENCE > 0) ? NEXUS_CLOUD_CONCURRENCE : 10;";
const blocFautif = bloc.replace(/const\s+n\s*=\s*[^;]+;/, ligneFausse);

if (blocFautif === bloc) {
  verifier("C1 contre‑epreuve construction", false, "la substitution n'a rien remplacé");
} else {
  let fnFautif;
  try {
    fnFautif = new Function("process", `${blocFautif}\nreturn n;`);
  } catch (e) {
    verifier("C1 contre‑epreuve compilation", false, `exception ${e.message}`);
  }
  if (fnFautif) {
    try {
      const n = fnFautif({ env: { NEXUS_CLOUD_CONCURRENCE: "7" } });
      verifier("C1 contre‑epreuve F1 doit échouer", n === 10, `n = ${n}`);
    } catch (e) {
      verifier("C1 contre‑epreuve exécution", false, `exception ${e.message}`);
    }
  }
}

// ---------- Verdict final ----------
console.log("-".repeat(60));
console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
process.exit(echecs === 0 ? 0 : 1);
