// Un reveil qui ECHOUE doit-il pouvoir etre rejoue ?
//
// CE QUI ETAIT FAUX, et mesure chez une session voisine : le drapeau
// `_modelesReveilles.add(model)` etait pose AVANT la tentative de reveil. Un
// reveil qui expirait s'enregistrait donc comme reussi, et le modele n'etait
// plus jamais reveille. qwen3.6-27b-local a echoue DEUX FOIS SUR DEUX -- non
// pas deux incidents, mais un seul mecanisme qui se repete.
//
// C'est un fail-open par construction : la branche non prevue -- l'echec --
// prend la valeur « autoriser ». Le second passage ne peut plus rien
// corriger, puisque l'etat dit que tout va bien.
//
// Le budget de 15 s aggravait la chose : mesure ce jour contre le moteur,
// qwen3.6:27b demande 31 s a froid et 2 s a chaud. Le reveil expirait donc a
// coup sur, sur les modeles memes qu'il existait pour couvrir.
//
// L'epreuve porte sur le CODE REEL de server.js, extrait a la volee : tester
// une copie prouverait seulement que la copie fonctionne.

const fs = require("fs");
const path = require("path");

// Extraction du bloc source contenant la fonction a tester.
const source = fs.readFileSync(path.join(__dirname, "server.js"), "utf8");
const debut = source.indexOf("async function reveillerModele");
const fin = source.indexOf("async function chat(", debut);
if (debut < 0 || fin < 0 || fin <= debut) {
  console.error("RATE : reveillerModele introuvable dans server.js");
  process.exit(1);
}
const bloc = source.slice(debut, fin);
if (bloc.length < 300 || !bloc.includes("_reveilEnCours")) {
  console.error(
    "RATE : bloc extrait vide ou tronque (%d caracteres)",
    bloc.length
  );
  process.exit(1);
}

// Fabrique une version instrumentee de reveillerModele.
function fabriquer(chatBouchon) {
  const etat = {
    reveilles: new Set(),
    enCours: new Set(),
    journal: [],
    budgets: [],
    appelsChat: 0,
  };
  const fabrique = new Function(
    "planOf",
    "chat",
    "log",
    "_modelesReveilles",
    "_reveilEnCours",
    // le bloc extrait + retour de la fonction
    bloc + "; return reveillerModele;"
  );
  const fn = fabrique(
    () => "local",
    (m, msgs, max, budget) => {
      etat.budgets.push(budget);
      etat.appelsChat++;
      return chatBouchon(m);
    },
    (msg) => etat.journal.push(msg),
    etat.reveilles,
    etat.enCours
  );
  return { fn, etat };
}

// Outil de verification.
let echecs = 0;
function verifier(nom, condition, detail) {
  console.log("[%s] %s : %s", condition ? "OK  " : "RATE", nom, detail);
  if (!condition) echecs++;
}

// Tout `await` sur la fonction eprouvee passe par ici. Un reveil ne doit
// JAMAIS relancer : chat() l'appelle a sa premiere ligne, donc une relance
// transformerait un chargement lent en panne franche. Sans cette enveloppe,
// une relance tuait le harnais en rejet non intercepte -- rouge, mais muet.
async function appeler(fn, modele, budget) {
  try {
    await fn(modele, budget);
  } catch (e) {
    verifier("pas de relance", false,
             "reveillerModele(" + modele + ") a propage « " +
             (e && e.message) + " »");
  }
}

// Execution des tests.
(async () => {
  // ---------- CAS 1 : FORWARD ----------
  {
    const { fn, etat } = fabriquer(() => Promise.resolve());
    await appeler(fn, "modele1", undefined);
    verifier(
      "CAS1-1",
      etat.reveilles.has("modele1"),
      "le modele doit etre dans reveilles apres succes"
    );
    const appelsApresPremier = etat.appelsChat;
    await appeler(fn, "modele1", undefined);
    verifier(
      "CAS1-2",
      etat.appelsChat === appelsApresPremier,
      "un second appel ne doit pas rappeler chat"
    );
    verifier(
      "CAS1-3",
      etat.enCours.size === 0,
      "enCours doit etre vide a la fin du cas 1"
    );
  }

  // ---------- CAS 2 : REVERSE ----------
  {
    const { fn, etat } = fabriquer(() => Promise.reject(new Error("boom")));
    await appeler(fn, "modele2", undefined);
    verifier(
      "CAS2-1",
      !etat.reveilles.has("modele2"),
      "le modele ne doit PAS etre dans reveilles apres echec"
    );
    const appelsApresPremier = etat.appelsChat;
    await appeler(fn, "modele2", undefined);
    verifier(
      "CAS2-2",
      etat.appelsChat === appelsApresPremier + 1,
      "un second appel doit rappeler chat apres echec"
    );
    verifier(
      "CAS2-3",
      etat.enCours.size === 0,
      "enCours doit etre vide a la fin du cas 2"
    );
  }

  // ---------- CAS 3 : BUDGET ----------
  {
    const { fn, etat } = fabriquer(() => Promise.resolve());
    await appeler(fn, "modele3", 180000);
    verifier(
      "CAS3-1",
      etat.budgets[0] === 180000,
      "budget doit etre 180000 quand timeoutMs fourni"
    );
    await appeler(fn, "modele4", undefined);
    verifier(
      "CAS3-2",
      etat.budgets[1] === 15000,
      "budget doit etre 15000 quand timeoutMs absent"
    );
    verifier(
      "CAS3-3",
      etat.enCours.size === 0,
      "enCours doit etre vide a la fin du cas 3"
    );
  }

  // ---------- CAS 4 : PAS DE RELANCE ----------
  {
    const { fn, etat } = fabriquer(() => Promise.reject(new Error("boom")));
    let exception = null;
    try {
      await fn("modele5");
    } catch (e) {
      exception = e;
    }
    verifier(
      "CAS4-1",
      exception === null,
      "reveillerModele ne doit pas propager l'exception du chat"
    );
    verifier(
      "CAS4-2",
      etat.enCours.size === 0,
      "enCours doit etre vide apres le finally"
    );
  }

  // Resultat final.
  if (echecs > 0) {
    console.error("epreuve ratee : %d cas", echecs);
    process.exit(1);
  } else {
    console.log("epreuve tenue");
    process.exit(0);
  }
})();
