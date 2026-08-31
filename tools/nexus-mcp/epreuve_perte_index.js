// ------------------------------------------------------------
// Test du bloc de lecture d'index precedent dans server.js
// ------------------------------------------------------------

const fs = require("fs");
const path = require("path");

// ----- extraction du bloc source -----
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");
const debut = source.indexOf("  let perdus = 0;");
const fin = source.indexOf("  if (motifRemplacement) {", debut);
if (debut < 0 || fin < 0 || fin - debut < 200) {
  console.error("RATE : bloc de lecture introuvable ou tronque");
  process.exit(1);
}
const bloc = source.slice(debut, fin);

// ----- fonction qui execute le bloc avec des dependances injectees -----
function creerLecteur({ fsMock, INDEX_PATH, VERSION_INDEX, embedModel, prefixe }) {
  // le bloc utilise les variables ci-dessous ; on ajoute un return explicite
  const code = `${bloc}
return { anciens, racines, motifRemplacement, perdus };`;
  return new Function("fs", "INDEX_PATH", "VERSION_INDEX", "embedModel", "prefixe", code)(
    fsMock,
    INDEX_PATH,
    VERSION_INDEX,
    embedModel,
    prefixe
  );
}

// ----- utilitaire de verification -----
let echecs = 0;
function verifier(nom, ok, detail) {
  const statut = ok ? "[OK  ]" : "[RATE]";
  console.log(`  ${statut} ${nom} : ${detail}`);
  if (!ok) echecs++;
}

// ----- constantes communes -----
const INDEX_PATH = "/tmp/index.json";
const PREFIXE = "pref_";

// ----- cas de test -----

// 1. FUSION : meme version, meme modele, deux enregistrements dont un sous le prefixe
{
  // La forme REELLE d'un enregistrement porte `file` : c'est sur lui que le
  // filtre par prefixe travaille. Une fixture qui porte `id` fait lever le
  // code, et le rempart transforme la levee en « index illisible » -- un
  // diagnostic faux, issu du test et impute au code.
  const records = [
    { file: "ailleurs/a1.md", text: "extrait 1" },
    { file: PREFIXE + "/b2.md", text: "extrait 2" }
  ];
  const indexData = {
    version: 1,
    model: "nomic-embed-text-local",
    records
  };
  const fsMock = {
    existsSync: () => true,
    readFileSync: () => JSON.stringify(indexData)
  };
  const resultat = creerLecteur({
    fsMock,
    INDEX_PATH,
    VERSION_INDEX: 1,
    // Une CHAINE, pas un objet : le code compare
    // `precedent.model !== embedModel`, et un objet n'est jamais egal a
    // une chaine -- la branche « modele different » etait donc TOUJOURS
    // prise, et deux cas passaient par coincidence.
    embedModel: "nomic-embed-text-local",
    prefixe: PREFIXE
  });
  verifier(
    "Fusion - motifRemplacement null",
    resultat.motifRemplacement == null,
    `motifRemplacement=${resultat.motifRemplacement}`
  );
  verifier(
    "Fusion - perdus zero",
    resultat.perdus === 0,
    `perdus=${resultat.perdus}`
  );
  verifier(
    "Fusion - anciens ne garde que hors prefixe",
    Array.isArray(resultat.anciens) &&
      resultat.anciens.length === 1 &&
      resultat.anciens[0].file === "ailleurs/a1.md",
    `anciens=${JSON.stringify(resultat.anciens)}`
  );
}

// 2. MODELE DIFFERENT
{
  const records = [
    { id: "c1", texte: "extrait 1" },
    { id: "c2", texte: "extrait 2" }
  ];
  const indexData = {
    version: 1,
    model: "bge-m3-local",
    records
  };
  const fsMock = {
    existsSync: () => true,
    readFileSync: () => JSON.stringify(indexData)
  };
  const resultat = creerLecteur({
    fsMock,
    INDEX_PATH,
    VERSION_INDEX: 1,
    // Une CHAINE, pas un objet : le code compare
    // `precedent.model !== embedModel`, et un objet n'est jamais egal a
    // une chaine -- la branche « modele different » etait donc TOUJOURS
    // prise, et deux cas passaient par coincidence.
    embedModel: "nomic-embed-text-local",
    prefixe: PREFIXE
  });
  verifier(
    "Modele different - motifRemplacement non null",
    resultat.motifRemplacement && /modele different/i.test(resultat.motifRemplacement),
    `motifRemplacement=${resultat.motifRemplacement}`
  );
  verifier(
    "Modele different - perdus compte les anciens",
    resultat.perdus === records.length,
    `perdus=${resultat.perdus}`
  );
}

// 3. FORMAT ANTERIEUR (version differente)
{
  const records = [{ id: "d1", texte: "extrait" }];
  const indexData = {
    version: 0,                 // version ancienne
    model: "nomic-embed-text-local",
    records
  };
  const fsMock = {
    existsSync: () => true,
    readFileSync: () => JSON.stringify(indexData)
  };
  const resultat = creerLecteur({
    fsMock,
    INDEX_PATH,
    VERSION_INDEX: 1,           // version actuelle
    // Une CHAINE, pas un objet : le code compare
    // `precedent.model !== embedModel`, et un objet n'est jamais egal a
    // une chaine -- la branche « modele different » etait donc TOUJOURS
    // prise, et deux cas passaient par coincidence.
    embedModel: "nomic-embed-text-local",
    prefixe: PREFIXE
  });
  verifier(
    "Version differente - motifRemplacement non null",
    resultat.motifRemplacement && /format ant/.test(resultat.motifRemplacement),
    `motifRemplacement=${resultat.motifRemplacement}`
  );
  verifier(
    "Version differente - perdus compte les anciens",
    resultat.perdus === records.length,
    `perdus=${resultat.perdus}`
  );
}

// 4. INDEX ILLISIBLE (JSON invalide)
{
  const fsMock = {
    existsSync: () => true,
    readFileSync: () => "this is not json"
  };
  const resultat = creerLecteur({
    fsMock,
    INDEX_PATH,
    VERSION_INDEX: 1,
    // Une CHAINE, pas un objet : le code compare
    // `precedent.model !== embedModel`, et un objet n'est jamais egal a
    // une chaine -- la branche « modele different » etait donc TOUJOURS
    // prise, et deux cas passaient par coincidence.
    embedModel: "nomic-embed-text-local",
    prefixe: PREFIXE
  });
  const motifOk =
    resultat.motifRemplacement &&
    /illisible/i.test(resultat.motifRemplacement) &&
    /inconnu/i.test(resultat.motifRemplacement);
  verifier(
    "Illisible - motifRemplacement indique illisible et inconnu",
    motifOk,
    `motifRemplacement=${resultat.motifRemplacement}`
  );
  verifier(
    "Illisible - perdus zero (inconnu)",
    resultat.perdus === 0,
    `perdus=${resultat.perdus}`
  );
}

// 5. AUCUN INDEX PRECEDENT
{
  const fsMock = {
    existsSync: () => false,
    readFileSync: () => "" // ne sera jamais appele
  };
  const resultat = creerLecteur({
    fsMock,
    INDEX_PATH,
    VERSION_INDEX: 1,
    // Une CHAINE, pas un objet : le code compare
    // `precedent.model !== embedModel`, et un objet n'est jamais egal a
    // une chaine -- la branche « modele different » etait donc TOUJOURS
    // prise, et deux cas passaient par coincidence.
    embedModel: "nomic-embed-text-local",
    prefixe: PREFIXE
  });
  verifier(
    "Aucun index precedent - motifRemplacement null",
    resultat.motifRemplacement == null,
    `motifRemplacement=${resultat.motifRemplacement}`
  );
  verifier(
    "Aucun index precedent - perdus zero",
    resultat.perdus === 0,
    `perdus=${resultat.perdus}`
  );
  verifier(
    "Aucun index precedent - anciens vide",
    Array.isArray(resultat.anciens) && resultat.anciens.length === 0,
    `anciens=${JSON.stringify(resultat.anciens)}`
  );
}

// ----- resultat final -----
if (echecs) {
  console.error(`\n${echecs} echec(s)`);
  process.exit(1);
} else {
  console.log("\nepreuve tenue");
  process.exit(0);
}
