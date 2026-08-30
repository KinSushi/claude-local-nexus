// Le semaphore du plan local borne-t-il vraiment, et rend-il toujours ses jetons ?
//
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee : tester
// une copie prouverait seulement que la copie fonctionne.
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(
  path.join(__dirname, "server.js"), "utf8");

const debut = source.indexOf("const CONCURRENCE_LOCALE");
const fin = source.indexOf("function estPlanLocal");
if (debut < 0 || fin < 0 || fin < debut) {
  console.error("RATE : semaphore introuvable dans server.js");
  process.exit(1);
}
const bloc = source.slice(debut, fin);

let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

function charger(limite) {
  const prelude = `process.env.NEXUS_LOCAL_CONCURRENCE = ${JSON.stringify(String(limite))};\n`;
  const module = { exports: {} };
  // eslint-disable-next-line no-new-func
  new Function("module", "process", prelude + bloc + "\nmodule.exports = { avecJetonLocal, get pris() { return jetonsLocauxPris; }, get file() { return attenteLocale.length; } };")(module, process);
  return module.exports;
}

const dors = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  // 1. Vingt appels partis DANS LE MEME TICK. C'est le cas qui a fait echouer
  // le premier jet : il incrementait le compteur apres l'await, donc tous
  // passaient ensemble.
  {
    const s = charger(1);
    let courant = 0, maximum = 0;
    await Promise.all(Array.from({ length: 20 }, () =>
      s.avecJetonLocal(async () => {
        courant++;
        maximum = Math.max(maximum, courant);
        await dors(5);
        courant--;
      })));
    verifier("limite 1 : jamais deux inferences ensemble", maximum === 1,
             `maximum observe = ${maximum}`);
    verifier("limite 1 : aucun jeton retenu a la fin", s.pris === 0 && s.file === 0,
             `pris=${s.pris} file=${s.file}`);
  }

  // 2. La borne se regle, et elle est respectee a la lettre.
  {
    const s = charger(3);
    let courant = 0, maximum = 0;
    await Promise.all(Array.from({ length: 30 }, () =>
      s.avecJetonLocal(async () => {
        courant++;
        maximum = Math.max(maximum, courant);
        await dors(3);
        courant--;
      })));
    verifier("limite 3 : bornee a trois exactement", maximum === 3,
             `maximum observe = ${maximum}`);
  }

  // 3. Un appel qui JETTE ne doit pas emporter son jeton. C'est le defaut le
  // plus grave possible ici : un jeton perdu bloque le pont a vie.
  {
    const s = charger(1);
    for (let i = 0; i < 5; i++) {
      try {
        await s.avecJetonLocal(async () => { throw new Error("panne simulee"); });
      } catch (e) { /* attendu */ }
    }
    let passe = false;
    await s.avecJetonLocal(async () => { passe = true; });
    verifier("cinq echecs de suite : le pont reste passant", passe && s.pris === 0,
             `pris=${s.pris} apres cinq exceptions`);
  }

  // 4. L'ordre est FIFO : sans equite, un appel long reste indefiniment
  // derriere les courts qui se pressent.
  {
    const s = charger(1);
    const ordre = [];
    await Promise.all(Array.from({ length: 8 }, (_, i) =>
      s.avecJetonLocal(async () => { ordre.push(i); await dors(2); })));
    const attendu = [0, 1, 2, 3, 4, 5, 6, 7].join(",");
    verifier("ordre FIFO respecte", ordre.join(",") === attendu, ordre.join(","));
  }

  // 5. La sortie de secours. Sans elle, une anomalie de comptage bloquerait
  // tout le pont -- pire que le defaut corrige.
  {
    const s = charger(0);
    let courant = 0, maximum = 0;
    await Promise.all(Array.from({ length: 6 }, () =>
      s.avecJetonLocal(async () => {
        courant++; maximum = Math.max(maximum, courant); await dors(3); courant--;
      })));
    verifier("NEXUS_LOCAL_CONCURRENCE=0 desactive la borne", maximum === 6,
             `maximum observe = ${maximum}`);
  }

  // 6. CONTRE-EPREUVE. Tout ce qui precede passerait aussi si le harnais ne
  // voyait rien. On lui soumet donc la variante FAUTIVE -- celle du premier
  // jet, qui prenait le jeton APRES l'attente -- et le harnais doit la
  // refuser. S'il l'accepte, ce sont les cinq cas d'avant qui ne valent rien.
  {
    const fautif = bloc.replace(
      "  if (jetonsLocauxPris < CONCURRENCE_LOCALE) {\n    jetonsLocauxPris++;\n  } else {\n    await new Promise((resoudre) => attenteLocale.push(resoudre));",
      "  const billet = new Promise((resoudre) => attenteLocale.push(resoudre));\n  if (jetonsLocauxPris < CONCURRENCE_LOCALE) {\n    const s = attenteLocale.shift();\n    if (s) s();\n  }\n  await billet;\n  jetonsLocauxPris++;\n  if (false) {");
    if (fautif === bloc) {
      verifier("contre-epreuve : variante fautive construite", false,
               "la substitution n'a rien remplace -- le code a change de forme");
    } else {
      const module = { exports: {} };
      let maximum = 0;
      try {
        new Function("module", "process",
          'process.env.NEXUS_LOCAL_CONCURRENCE = "1";\n' + fautif +
          "\nmodule.exports = { avecJetonLocal };")(module, process);
        let courant = 0;
        await Promise.all(Array.from({ length: 20 }, () =>
          module.exports.avecJetonLocal(async () => {
            courant++; maximum = Math.max(maximum, courant); await dors(5); courant--;
          })));
      } catch (e) {
        maximum = -1;
      }
      verifier("contre-epreuve : la variante fautive est bien VUE",
               maximum !== 1,
               `la variante fautive atteint ${maximum} appels simultanes la ou la corrigee reste a 1`);
    }
  }

  console.log("-".repeat(60));
  console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
  process.exit(echecs === 0 ? 0 : 1);
})();
