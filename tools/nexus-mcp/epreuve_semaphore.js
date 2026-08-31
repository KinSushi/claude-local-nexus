// Les deux plans sont-ils bornes, chacun chez soi, et le harnais le verrait-il sinon ?
//
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee : tester
// une copie prouverait seulement que la copie fonctionne.
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");

const debut = source.indexOf("const CONCURRENCE_LOCALE");
const fin = source.indexOf("// Temperature par defaut des outils du pont.");
if (debut < 0 || fin < 0 || fin <= debut) {
  console.error("RATE : semaphore introuvable dans server.js");
  process.exit(1);
}
const bloc = source.slice(debut, fin);
// Un bloc VIDE ou minuscule ne doit pas se lire comme un bloc valide.
//
// `fin < debut` laissait passer `fin === debut`, donc une tranche vide :
// toutes les epreuves suivantes se seraient executees sur RIEN et auraient
// rendu « epreuve tenue » sans avoir teste une seule ligne. Un seuil de
// taille est plus sur qu'une comparaison d'index, parce qu'il attrape aussi
// le cas ou les deux reperes se rapprochent sans se croiser.
if (bloc.length < 400 || !bloc.includes("function creerSemaphore")) {
  console.error("RATE : bloc extrait vide ou tronque (%d caracteres)", bloc.length);
  process.exit(1);
}

let echecs = 0;
function verifier(nom, condition, detail) {
  console.log(`[${condition ? "OK  " : "RATE"}] ${nom} : ${detail}`);
  if (!condition) echecs++;
}

// `planOf` vit ailleurs dans le fichier : on l'injecte, ce qui permet en outre
// de piloter l'aiguillage sans dependre de la table lue a la passerelle.
function charger(local, cloud, planOf, texte) {
  const prelude =
    `process.env.NEXUS_LOCAL_CONCURRENCE = ${JSON.stringify(String(local))};\n` +
    `process.env.NEXUS_CLOUD_CONCURRENCE = ${JSON.stringify(String(cloud))};\n`;
  const module_ = { exports: {} };
  new Function("module", "process", "planOf",
    prelude + (texte || bloc) +
    "\nmodule.exports = { creerSemaphore, avecJetonDuPlan, semaphoreLocal," +
    " semaphoreCloud, estPlanLocal, estPlanCloud };")(module_, process, planOf);
  return module_.exports;
}

const PLANS = (alias) =>
  alias.endsWith("-cloud") ? "Ollama Cloud, les donnees sortent"
  : alias.startsWith("claude-") ? "Anthropic, facture au token"
  : alias === "mystere" ? "plan inconnu"
  : "local, cout 0";

const dors = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  // 1. Vingt appels partis DANS LE MEME TICK. C'est le cas qui a fait echouer
  // le premier jet : il incrementait le compteur apres l'await, donc tous
  // passaient ensemble.
  {
    const s = charger(1, 4, PLANS).creerSemaphore(1);
    let courant = 0, maximum = 0;
    await Promise.all(Array.from({ length: 20 }, () => (async () => {
      await s.prendre();
      try { courant++; maximum = Math.max(maximum, courant); await dors(5); courant--; }
      finally { s.rendre(); }
    })()));
    verifier("limite 1 : jamais deux appels ensemble", maximum === 1,
             `maximum observe = ${maximum}`);
    verifier("limite 1 : aucun jeton retenu a la fin", s.pris === 0 && s.attente === 0,
             `pris=${s.pris} attente=${s.attente}`);
  }

  // 2. La borne se regle et elle est respectee a la lettre.
  {
    const s = charger(1, 4, PLANS).creerSemaphore(4);
    let courant = 0, maximum = 0;
    await Promise.all(Array.from({ length: 30 }, () => (async () => {
      await s.prendre();
      try { courant++; maximum = Math.max(maximum, courant); await dors(3); courant--; }
      finally { s.rendre(); }
    })()));
    verifier("limite 4 : bornee a quatre exactement", maximum === 4,
             `maximum observe = ${maximum}`);
  }

  // 3. LA PROPRIETE NEUVE, et la raison d'avoir deux files : un appel cloud
  // ne doit JAMAIS attendre derriere un appel local. Une file unique ferait
  // payer au cloud la lenteur du local -- 600 s d'expiration mesurees -- et
  // annulerait l'interet meme d'avoir deux plans.
  {
    const m = charger(1, 4, PLANS);
    let cloudFini = null, localFini = null;
    const t0 = Date.now();
    const local = m.avecJetonDuPlan("glm-4.7-flash-local", async () => {
      await dors(200); localFini = Date.now() - t0;
    });
    const local2 = m.avecJetonDuPlan("qwen3-coder-30b-local", async () => { await dors(200); });
    const nuage = m.avecJetonDuPlan("gpt-oss-120b-cloud", async () => {
      await dors(10); cloudFini = Date.now() - t0;
    });
    await Promise.all([local, local2, nuage]);
    verifier("le cloud n'attend pas derriere le local",
             cloudFini !== null && cloudFini < 150,
             `cloud rendu a ${cloudFini} ms, local a ${localFini} ms`);
  }

  // 4. Anthropic et le plan inconnu ne sont bornes par personne : le premier
  // se limite par le portefeuille, le second n'est pas assez connu pour
  // qu'on lui impose quoi que ce soit.
  {
    const m = charger(1, 1, PLANS);
    let courant = 0, maximum = 0;
    const tache = (alias) => m.avecJetonDuPlan(alias, async () => {
      courant++; maximum = Math.max(maximum, courant); await dors(20); courant--;
    });
    await Promise.all([tache("claude-haiku-4-5"), tache("claude-haiku-4-5"),
                       tache("mystere"), tache("mystere")]);
    verifier("Anthropic et plan inconnu ne sont pas bornes", maximum === 4,
             `maximum observe = ${maximum} sur quatre appels`);
  }

  // 5. Un appel qui JETTE ne doit pas emporter son jeton : un jeton perdu
  // bloquerait le pont a vie.
  {
    const m = charger(1, 4, PLANS);
    for (let i = 0; i < 5; i++) {
      try {
        await m.avecJetonDuPlan("glm-4.7-flash-local", async () => {
          throw new Error("panne simulee");
        });
      } catch { /* attendu : la liaison n'etait jamais lue */ }
    }
    let passe = false;
    await m.avecJetonDuPlan("glm-4.7-flash-local", async () => { passe = true; });
    verifier("cinq echecs de suite : le pont reste passant",
             passe && m.semaphoreLocal.pris === 0,
             `pris=${m.semaphoreLocal.pris} apres cinq exceptions`);
  }

  // 6. L'ordre est FIFO : sans equite, un appel long reste indefiniment
  // derriere les courts qui se pressent.
  {
    const s = charger(1, 4, PLANS).creerSemaphore(1);
    const ordre = [];
    await Promise.all(Array.from({ length: 8 }, (_, i) => (async () => {
      await s.prendre();
      try { ordre.push(i); await dors(2); } finally { s.rendre(); }
    })()));
    verifier("ordre FIFO respecte", ordre.join(",") === "0,1,2,3,4,5,6,7", ordre.join(","));
  }

  // 7. Les sorties de secours, une par plan. Sans elles, une anomalie de
  // comptage bloquerait le pont entier.
  {
    const m = charger(0, 0, PLANS);
    let courant = 0, maximum = 0;
    const tache = (alias) => m.avecJetonDuPlan(alias, async () => {
      courant++; maximum = Math.max(maximum, courant); await dors(3); courant--;
    });
    await Promise.all([tache("glm-4.7-flash-local"), tache("glm-4.7-flash-local"),
                       tache("gpt-oss-120b-cloud"), tache("gpt-oss-120b-cloud")]);
    verifier("une borne a zero desactive sa file", maximum === 4,
             `maximum observe = ${maximum}`);
  }

  // 8. CONTRE-EPREUVE. Tout ce qui precede passerait aussi si le harnais ne
  // voyait rien. On lui soumet la variante FAUTIVE -- jeton pris APRES
  // l'attente -- et il doit la refuser.
  {
    const fautif = bloc.replace(
      "      if (pris < limite) { pris++; return; }\n" +
      "      await new Promise(function (resoudre) { file.push(resoudre); });",
      "      const billet = new Promise(function (resoudre) { file.push(resoudre); });\n" +
      "      if (pris < limite) { const s = file.shift(); if (s) s(); }\n" +
      "      await billet;\n      pris++;");
    if (fautif === bloc) {
      verifier("contre-epreuve : variante fautive construite", false,
               "la substitution n'a rien remplace -- le code a change de forme");
    } else {
      let maximum = 0;
      try {
        const s = charger(1, 4, PLANS, fautif).creerSemaphore(1);
        let courant = 0;
        await Promise.all(Array.from({ length: 20 }, () => (async () => {
          await s.prendre();
          try { courant++; maximum = Math.max(maximum, courant); await dors(5); courant--; }
          finally { s.rendre(); }
        })()));
      } catch { maximum = -1; }
      // `maximum !== 1` passait aussi quand maximum valait ZERO -- c'est-a-dire
      // quand la variante fautive ne laissait passer AUCUN appel, donc quand
      // elle etait cassee autrement. La contre-epreuve acceptait alors une
      // regression au lieu de la voir. Ce qu'il faut exiger est qu'elle
      // depasse la borne, pas qu'elle en differe.
      verifier("contre-epreuve : la variante fautive est bien VUE", maximum > 1,
               `la variante fautive atteint ${maximum} appels simultanes la ou la corrigee reste a 1`);
    }
  }

  console.log("-".repeat(60));
  console.log(echecs === 0 ? "VERDICT : epreuve tenue" : `VERDICT : ${echecs} echec(s)`);
  process.exit(echecs === 0 ? 0 : 1);
})();
