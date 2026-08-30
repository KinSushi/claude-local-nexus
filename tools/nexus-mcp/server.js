#!/usr/bin/env node
/**
 * nexus-local — serveur MCP donnant à Claude Code l'accès aux trois plans
 * d'exécution de la plateforme : local, Ollama Cloud et Anthropic.
 *
 * Raison d'être
 * -------------
 * Un abonnement Claude ne peut pas transiter par une passerelle : dès qu'un
 * jeton de passerelle est posé, il remplace la connexion claude.ai et la
 * facturation bascule au token. Router Claude Code vers LiteLLM reviendrait
 * donc à ne plus utiliser l'abonnement du tout.
 *
 * Ce serveur prend le problème par l'autre bout. Claude Code reste sur son
 * abonnement et joue l'orchestrateur ; la passerelle devient un banc de
 * modèles qu'il peut appeler à la demande — un modèle local gratuit pour le
 * volume, un modèle Ollama Cloud pour la puissance, un modèle Claude payant
 * quand sa spécificité le justifie. L'arbitrage cout / confidentialité /
 * capacité redevient une décision explicite, prise appel par appel.
 *
 * Douze outils, organisés en quatre familles :
 *   exécution    nexus_ask, nexus_route, nexus_batch, nexus_compare
 *   contexte     nexus_context, nexus_summarize, nexus_index_build, nexus_search
 *   modalité     nexus_vision
 *   inspection   nexus_models, nexus_profile, nexus_savings
 *
 * Aucune dépendance npm : uniquement la bibliothèque standard de Node.
 * Le transport stdio MCP est du JSON-RPC délimité par des sauts de ligne,
 * donc stdout est réservé au protocole — toute trace part sur stderr.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const https = require("node:https");
const readline = require("node:readline");
const { AsyncLocalStorage } = require("node:async_hooks");

const PROTOCOL_VERSION = "2025-06-18";
// Empreinte du fichier CHARGE, et non un numero de version tenu a la main.
//
// Node lit ce fichier une fois, au demarrage. Une session ouverte avant une
// correction continue donc de servir l'ancien code, indefiniment, et rien
// ne le signale -- observe le 2026-08-30 : une session parallele routait
// encore `coding` vers releve-locale plusieurs heures apres que ce modele
// en eut ete retire, et concluait de bonne foi que le profil pointait vers
// un modele inexecutable.
//
// Un numero fige a la main n'aurait rien change : il aurait ete correct et
// perime en meme temps. L'empreinte, elle, ne peut pas mentir.
const EMPREINTE = (() => {
  try {
    return require("crypto").createHash("sha256")
      .update(require("fs").readFileSync(__filename))
      .digest("hex").slice(0, 12);
  } catch {
    return "inconnue";
  }
})();

const SERVER_INFO = {
  name: "nexus-local",
  version: "1.0.0",
  // Lue par nexus_conformite.py, qui la compare au fichier sur disque.
  empreinte: EMPREINTE,
};

// Racine du depot, par ordre de fiabilite decroissante : reglage explicite,
// racine fournie par Claude Code, puis position du fichier. Aucune de ces
// sources n'est un chemin en dur : le pont doit pouvoir etre repris tel
// quel dans un autre projet.
// CLAUDE_PROJECT_DIR a ete RETIRE de cette chaine, a dessein.
//
// INSTALL_ROOT sert a trouver le .env de la passerelle et les scripts de la
// plateforme (nexus_capability.py, nexus_savings.py). Or CLAUDE_PROJECT_DIR
// designe le projet APPELANT : depuis un depot tiers, INSTALL_ROOT pointait
// donc vers un repertoire ou ne se trouve ni .env ni scripts/, et la lecture
// de la clef comme nexus_models et nexus_savings echouaient -- precisement
// dans le cas que le pont existe pour servir.
//
// __dirname, lui, designe toujours l'installation reelle : un serveur sait
// ou il vit. NEXUS_ROOT reste disponible pour un reglage explicite.
//
// Ne pas confondre avec WORK_ROOT ci-dessous, qui doit suivre le projet
// appelant. Les deux racines sont distinctes et le rester est tout l'enjeu.
const INSTALL_ROOT =
  process.env.NEXUS_ROOT ||
  path.resolve(__dirname, "..", "..");

// Racine du projet dont on lit les fichiers (WORK_ROOT). Priorité :
//   1. NEXUS_WORK_ROOT (explicit)
//   2. CLAUDE_PROJECT_DIR (legacy)
//   3. répertoire courant. Aucun chemin en dur pour éviter que le serveur
//      reste prisonnier d'un projet spécifique.
const WORK_ROOT = process.env.NEXUS_WORK_ROOT ||
  process.env.CLAUDE_PROJECT_DIR ||
  process.cwd();
const LITELLM_URL = process.env.NEXUS_LITELLM_URL || "http://127.0.0.1:4000";
const INDEX_DIR = path.join(WORK_ROOT, ".nexus");
const INDEX_PATH = path.join(INDEX_DIR, "index.json");

// Modèles par défaut. GLM-4.7-Flash est un MoE 30B dont ~3B seulement sont
// actifs : sur un hôte CPU c'est le meilleur compromis latence/qualité, et
// c'est le seul modèle local déclaré à 32K de contexte.
const DEFAULT_CHAT_MODEL = process.env.NEXUS_CHAT_MODEL || "glm-4.7-flash-local";
// qwen3-embedding est retenu sur mesure, pas par principe : sur des paires
// francaises, nomic-embed-text classe la phrase sans rapport AU-DESSUS de la
// paraphrase (0.555 contre 0.520), ce qui rendrait la recherche trompeuse.
// qwen3-embedding separe nettement (0.875 contre 0.417). Il est plus lourd :
// l'indexation est plus lente, la pertinence bien meilleure.
// Modele d'embedding par defaut, choisi sur mesure et non sur la taille.
//
// C'etait qwen3-embedding-8b-local : HUIT gigaoctets de poids pour produire
// des vecteurs. nexus_index_build expirait a 600 s sur le seul dossier
// scripts/, et nexus_search aussi.
//
// Mesure du 2026-08-30, latence et MARGE DISCRIMINANTE -- cos(ancre,
// proche) moins cos(ancre, eloigne), la capacite a separer le sens :
//
//   all-minilm-local          46 Mo    2341 ms   marge 0,289
//   nomic-embed-text-local   274 Mo    2122 ms   marge 0,210
//   bge-m3-local             1,2 Go    2187 ms   marge 0,204
//
// Le plus petit discrimine le MIEUX. La taille ne predisait ni le delai de
// demarrage, ni le debit, ni -- on le voit ici -- la qualite des vecteurs.
//
// La marge prime sur la latence, a dessein : un embedding rapide qui ne
// separe pas rend la recherche inutile. Ici les deux vont dans le meme
// sens, ce qui rend le choix facile ; il ne le sera pas toujours.
const DEFAULT_EMBED_MODEL = process.env.NEXUS_EMBED_MODEL || "all-minilm-local";
// Le plus leger des modeles multimodaux installes : sur CPU, un llava:34b
// mettrait des dizaines de minutes a decrire une capture d'ecran.
const DEFAULT_VISION_MODEL = process.env.NEXUS_VISION_MODEL || "llava-7b-local";
const DEFAULT_TIMEOUT_MS = Number(process.env.NEXUS_TIMEOUT_MS || 600000);

function log(...args) {
  process.stderr.write("[nexus-local] " + args.join(" ") + "\n");
}

// ---------------------------------------------------------------------------
// Annulation
// ---------------------------------------------------------------------------

/**
 * Signal d'annulation de l'appel MCP en cours.
 *
 * `notifications/cancelled` etait accepte puis jete : l'inference continuait
 * jusqu'a son terme. Combine a l'attente sans borne des appels en vol quand
 * stdin se ferme, un serveur devenu orphelin pouvait occuper la passerelle
 * -- partagee avec le reste de la plateforme -- pendant des dizaines de
 * minutes, pour produire une reponse que plus personne n'attend.
 *
 * Le signal voyage par AsyncLocalStorage plutot que par un parametre ajoute
 * aux dizaines de sites d'appel intermediaires : le contexte survit a await,
 * a setTimeout et aux handlers d'evenement de socket, ce qui couvre tout le
 * trajet d'une requete HTTP. Verifie sur cette version de Node, pas suppose.
 */
const contexteAppel = new AsyncLocalStorage();

function signalCourant() {
  const store = contexteAppel.getStore();
  return store ? store.signal : undefined;
}

// Appels en cours, indexes par identifiant JSON-RPC converti en chaine : un
// client qui renvoie `requestId: "3"` la ou il avait emis `id: 3` ne doit pas
// voir son annulation silencieusement perdue.
const appelsEnCours = new Map();

// ---------------------------------------------------------------------------
// Accès à LiteLLM
// ---------------------------------------------------------------------------

let cachedKey = null;
function masterKey() {
  if (cachedKey !== null) return cachedKey;
  if (process.env.LITELLM_MASTER_KEY) {
    cachedKey = process.env.LITELLM_MASTER_KEY;
    return cachedKey;
  }
  const envFile = path.join(INSTALL_ROOT, ".env");
  if (fs.existsSync(envFile)) {
    for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const m = /^\s*LITELLM_MASTER_KEY\s*=\s*(.*)$/.exec(line);
      if (m && m[1].trim()) {
        let valeur = m[1].trim();
        // Guillemets et commentaire de fin de ligne retires, comme le fait
        // deja nexus_test.py. Sans cela, `KEY="sk-..."` partait guillemets
        // compris dans l'en-tete Authorization et produisait un 401 que
        // rien n'explique -- exactement l'echec opaque que le garde-fou
        // plus bas pretend eviter. Le commentaire n'est retire que sur une
        // valeur NON citee : entre guillemets, un `#` appartient a la cle.
        const quote = valeur.slice(0, 1);
        if ((quote === '"' || quote === "'") && valeur.slice(-1) === quote &&
            valeur.length >= 2) {
          valeur = valeur.slice(1, -1);
        } else {
          valeur = valeur.split("#")[0].trim();
        }
        if (!valeur) continue;
        cachedKey = valeur;
        return cachedKey;
      }
    }
  }
  // Un Bearer vide produit un 401 opaque, cote serveur, plusieurs couches
  // plus loin. Mieux vaut echouer ici, ou la cause est encore lisible.
  throw new Error(
    "LITELLM_MASTER_KEY introuvable : ni dans l'environnement, ni dans " +
    // La cle vit avec l'INSTALLATION, jamais dans le projet courant :
    // un projet tiers n'a pas a porter la cle de la passerelle, et l'y
    // chercher ferait echouer le pont partout ailleurs.
    path.join(INSTALL_ROOT, ".env")
  );
}

// Transport choisi d'apres l'URL, et non suppose : une passerelle derriere
// TLS n'est pas une hypothese exotique des lors que ce depot sert de base a
// d'autres projets.
function transportFor(url) {
  const secure = url.protocol === "https:";
  return {
    agent: secure ? https : http,
    port: url.port || (secure ? 443 : 80),
  };
}

function requestJson(pathname, payload, timeoutMs = DEFAULT_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const body = Buffer.from(JSON.stringify(payload), "utf8");
    const url = new URL(pathname, LITELLM_URL);
    const { agent, port } = transportFor(url);
    const req = agent.request(
      {
        hostname: url.hostname,
        port,
        path: url.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": body.length,
          Authorization: "Bearer " + masterKey(),
        },
        // Une annulation doit couper la connexion, pas seulement cesser
        // d'attendre : sans cela l'inference reste engagee cote passerelle.
        signal: signalCourant(),
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        // Une coupure APRES les en-tetes emet l'erreur sur la reponse, pas
        // sur la requete. Sans cet ecouteur, la promesse n'etait jamais
        // reglee : l'appel ne recevait ni resultat ni erreur, la reprise ne
        // voyait rien alors qu'ECONNRESET est justement classe passager, et
        // le compteur d'appels en vol ne redescendait plus a zero — donc le
        // serveur ne pouvait plus se fermer proprement.
        res.on("error", (err) => reject(
          new Error("reponse interrompue : " + err.message)));
        res.on("end", () => {
          // `complete` vaut false si la connexion a ete coupee avant la fin
          // du corps annonce : un JSON tronque parserait parfois sans erreur.
          if (res.complete === false) {
            reject(new Error("reponse interrompue avant la fin du corps"));
            return;
          }
          const text = Buffer.concat(chunks).toString("utf8");
          if (res.statusCode < 200 || res.statusCode >= 300) {
            const erreur = new Error(
              "LiteLLM HTTP " + res.statusCode + " : " + text.slice(0, 400));
            // Le code porte la verite ; le texte du corps peut mentionner
            // ECONNRESET pour une erreur pourtant definitive.
            erreur.statusCode = res.statusCode;
            reject(erreur);
            return;
          }
          try {
            // Les en-tetes portent le modele reellement retenu derriere un
            // routeur adaptatif ; le champ "model" du corps ne renvoie que
            // le nom du routeur. On remonte donc les deux.
            resolve({ body: JSON.parse(text), headers: res.headers });
          } catch (err) {
            reject(new Error("reponse LiteLLM illisible : " + text.slice(0, 200)));
          }
        });
      }
    );
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error("delai depasse apres " + Math.round(timeoutMs / 1000) + "s"));
    });
    req.on("error", reject);
    req.end(body);
  });
}

function getJson(pathname, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const url = new URL(pathname, LITELLM_URL);
    const { agent, port } = transportFor(url);
    const req = agent.request(
      {
        hostname: url.hostname,
        port,
        path: url.pathname,
        method: "GET",
        headers: { Authorization: "Bearer " + masterKey() },
        signal: signalCourant(),
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(new Error("LiteLLM HTTP " + res.statusCode));
            return;
          }
          try {
            resolve(JSON.parse(text));
          } catch (err) {
            reject(new Error("reponse illisible"));
          }
        });
      }
    );
    req.setTimeout(timeoutMs, () => req.destroy(new Error("delai depasse")));
    req.on("error", reject);
    req.end();
  });
}

// Erreurs qui ne disent rien du fond de la requete : un redemarrage de la
// passerelle, une coupure de socket, un delai depasse. Les rejouer est
// legitime ; rejouer un 400 ou un 404 ne le serait pas.
// Erreurs rejouables : celles qui ne disent rien du fond de la requete ET
// dont on sait qu'elle n'a pas ete traitee.
//
// `delai depasse` en est volontairement ABSENT. Le delai porte sur
// l'inactivite du socket, pas sur un traitement : la requete a tres bien pu
// etre executee entierement cote serveur. La rejouer facturerait trois
// generations sur un modele Claude, ou lancerait trois inferences
// concurrentes du meme prompt sur un hote CPU -- exactement la contention
// que nexus_batch dit vouloir eviter.
const REJOUABLE = /socket hang up|ECONNRESET|ECONNREFUSED|EPIPE|ETIMEDOUT/i;

// Codes HTTP rejouables. Le CODE fait foi, jamais le texte : un 400
// definitif dont le corps mentionne ECONNRESET -- frequent quand LiteLLM
// recopie l'erreur amont -- etait rejoue trois fois pour rien.
const CODES_REJOUABLES = new Set([429, 500, 502, 503, 504]);

function estRejouable(err) {
  if (typeof err.statusCode === "number") {
    return CODES_REJOUABLES.has(err.statusCode);
  }
  return REJOUABLE.test(err.message);
}

// Une requete annulee ne doit JAMAIS etre rejouee. L'abort ferme le socket,
// et une socket fermee ressemble a s'y meprendre a un incident passager : la
// reprise relancerait trois inferences apres que le client a demande
// l'arret, ce qui transforme l'annulation en aggravation. Node signale
// l'abort par name=AbortError / code=ABORT_ERR sur la requete ; on interroge
// aussi le signal lui-meme, au cas ou l'erreur remonterait deja reemballee.
function estAnnule(err) {
  if (err && (err.name === "AbortError" || err.code === "ABORT_ERR")) return true;
  const signal = signalCourant();
  return Boolean(signal && signal.aborted);
}

async function withRetry(operation, attempts = 3) {
  let last;
  for (let i = 0; i < attempts; i++) {
    try {
      return await operation();
    } catch (err) {
      last = err;
      if (estAnnule(err) || !estRejouable(err) || i === attempts - 1) throw err;
      // Attente croissante : une passerelle qui redemarre met quelques
      // secondes, pas quelques millisecondes.
      const pause = 2000 * Math.pow(2, i);
      log("incident passager (" + err.message.slice(0, 60) + ") — reprise dans "
          + pause / 1000 + "s");
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
  }
  throw last;
}

/**
 * Plan d'execution d'un alias, et ce qu'il implique.
 *
 * Annoncer « local » sans le verifier serait le pire des defauts pour cette
 * plateforme : l'appelant croirait ses donnees restees sur la machine. Le
 * plan se deduit donc du modele reellement servi, jamais d'une constante.
 */
const LIBELLE_PLAN = {
  local: "local, cout 0",
  cloud: "Ollama Cloud, les donnees sortent",
  anthropic: "Anthropic, facture au token",
  routeur: "routeur",
};

function planOf(alias) {
  if (!alias) return "plan inconnu";
  // La table lue a la source prime toujours ; le suffixe n'est qu'un repli
  // pour le cas ou la passerelle n'aurait pas encore repondu.
  const connu = plansConnus && plansConnus.get(alias);
  if (connu) return LIBELLE_PLAN[connu] || connu;
  if (alias.endsWith("-cloud")) return "Ollama Cloud, les donnees sortent";
  if (alias.startsWith("claude-")) return "Anthropic, facture au token";
  return "local, cout 0";
}

// Concurrence du plan local, bornee au niveau du SERVEUR.
//
// `nexus_batch` est sequentiel a dessein, et sa description dit pourquoi :
// deux inferences simultanees se disputent la meme bande passante memoire et
// finissent plus tard que si elles s'etaient suivies. Mais cette discipline
// ne valait qu'A L'INTERIEUR d'un appel : rien n'empechait dix appelants d'en
// lancer dix en parallele, c'est-a-dire exactement ce que `nexus_batch`
// refuse de faire. La regle existait en paragraphe, pas en mecanisme.
//
// Mesure du 2026-08-30, 34 appels MCP dont une dizaine simultanes :
//
//     plan local   8 reussites, 14 ECHECS -- toutes des expirations a 600 s
//     plan cloud   7 reussites,  0 echec
//
// Ont expire : un resume de README.md (15 Ko), une extraction dite triviale
// via nexus_route, et deux nexus_context. Ce n'est pas la taille des taches
// qui a decide, c'est le nombre d'inferences concurrentes sur un hote a
// memoire partagee dont le moteur ne garde que trois modeles residents.
//
// Le cloud n'est PAS borne : il a rendu 7 sur 7 en parallele, et le brider
// gacherait l'abonnement qui a ete paye pour cela.
const CONCURRENCE_LOCALE = Number(process.env.NEXUS_LOCAL_CONCURRENCE || 1);

const attenteLocale = [];
let jetonsLocauxPris = 0;

/**
 * Execute `fn` en tenant un jeton du plan local, et le rend toujours.
 *
 * Le jeton est PRIS dans le meme tick que le test d'admission, jamais apres
 * un `await`. Le premier jet faisait l'inverse -- il incrementait le compteur
 * apres l'attente -- si bien que deux appels partis dans le meme tick voyaient
 * tous deux zero jeton pris et passaient ensemble. Le semaphore aurait ete
 * inoperant precisement sous la charge qui le motive.
 *
 * A la liberation, le jeton est TRANSMIS au suivant plutot que rendu puis
 * repris : entre les deux gestes, un appel arrive entre-temps se glisserait
 * devant toute la file.
 */
async function avecJetonLocal(fn) {
  // Sortie de secours. Sans elle, une anomalie de comptage bloquerait le pont
  // entier, ce qui serait un defaut bien pire que la contention corrigee.
  if (!(CONCURRENCE_LOCALE > 0)) return fn();

  if (jetonsLocauxPris < CONCURRENCE_LOCALE) {
    jetonsLocauxPris++;
  } else {
    await new Promise((resoudre) => attenteLocale.push(resoudre));
    // Le jeton nous a ete transmis : le compteur reste inchange.
  }
  try {
    return await fn();
  } finally {
    const suivant = attenteLocale.shift();
    if (suivant) suivant();
    else jetonsLocauxPris = Math.max(0, jetonsLocauxPris - 1);
  }
}

/**
 * Le plan local, et lui seul.
 *
 * `planOf` est la seule source : declarer une seconde table serait s'exposer
 * a ce qu'elles divergent. Un plan INCONNU rend false -- serialiser par
 * defaut ce que l'on ne connait pas ralentirait le cloud sur une simple
 * lacune de table, et le cout d'un faux negatif est une contention, jamais
 * une panne.
 */
function estPlanLocal(alias) {
  const libelle = planOf(alias);
  return typeof libelle === "string" && /^local\b/i.test(libelle.trim());
}

// Retire la chaine de pensee que certains modeles laissent dans `content`.
//
// Constate le 30 aout 2026 cote Python : une reponse rendue a l'utilisateur
// contenait tout le raisonnement du modele, puis « </think>702 ». Le chemin
// MCP recopiait content tel quel et avait le meme defaut -- or c'est lui que
// Claude Code appelle. Le raisonnement n'est pas la reponse : le livrer donne
// un brouillon a la place d'un resultat, et le MAP-REDUCE concatenerait ces
// hesitations dans le texte soumis au REDUCE.
const BALISES_PENSEE = ["think", "thinking", "reasoning"];

function sansRaisonnement(texte) {
  if (!texte) return "";
  let s = String(texte);

  // Blocs complets, une balise a la fois : une backreference  serait lue
  // comme un echappement octal dans un template literal, ce que Node refuse.
  for (const b of BALISES_PENSEE) {
    s = s.replace(new RegExp("<\\s*" + b + "\\s*>[\\s\\S]*?<\\s*/\\s*" + b + "\\s*>", "gi"), "");
  }

  // Ouverture sans fermeture : la reponse n'est jamais venue. Rendre le
  // raisonnement brut serait pire que ne rien rendre -- l'appelant croirait
  // tenir un resultat.
  for (const b of BALISES_PENSEE) {
    if (new RegExp("<\\s*" + b + "\\s*>", "i").test(s)) return "";
  }

  // Fermeture sans ouverture : le raisonnement a ete tronque en amont, la
  // reponse est ce qui suit la derniere fermeture.
  let dernier = -1;
  for (const b of BALISES_PENSEE) {
    const re = new RegExp("<\\s*/\\s*" + b + "\\s*>", "gi");
    let m;
    while ((m = re.exec(s)) !== null) {
      const bout = m.index + m[0].length;
      if (bout > dernier) dernier = bout;
    }
  }
  if (dernier >= 0) s = s.slice(dernier);
  return s.trim();
}

// Temperature par defaut des outils du pont.
//
// Le serveur n'en envoyait AUCUNE, si bien que les douze outils tournaient
// au defaut des modeles, environ 0,7 a 0,8. C'est la leçon la plus chere du
// depot, et le seul endroit ou elle n'etait pas appliquee : a 0,7, le banc
// a rendu un document dont TOUTES les mesures etaient inventees, et une
// boucle de repetition de 589 s ; a 0,2, la meme tache a reussi en 11 s.
//
// nexus_agent.py appliquait 0,2 depuis longtemps. Le serveur MCP, qui sert
// bien plus de trafic, ne le faisait pas.
//
// Surchargeable par NEXUS_TEMPERATURE, et par appel pour les rares usages
// ou l'on veut de la variete plutot que de l'exactitude.
const TEMPERATURE_DEFAUT = process.env.NEXUS_TEMPERATURE !== undefined
  ? Number(process.env.NEXUS_TEMPERATURE)
  : 0.2;

// Temperature PAR PROFIL : une valeur unique convient mal a quatre classes
// de taches qui ne demandent pas la meme chose.
//
//   coding      0.1  une implementation doit etre exacte et reproductible ;
//                    la variete n'y apporte rien et coute des defauts
//   rapide      0.0  classification et extraction : il n'y a qu'une bonne
//                    reponse, toute variete est du bruit
//   reasoning   0.4  arbitrages et architecture : explorer plusieurs voies
//                    a un interet reel, la rigueur venant de l'arbitrage
//   multimodal  0.2  DECRIRE une image demande l'exactitude, pas
//                    l'imagination -- c'est meme le cas ou une temperature
//                    haute fait inventer ce qui n'est pas dans l'image
//
// Ce dernier point est un arbitrage contre le banc, qui proposait 0.5 en
// arguant que « l'ambiguite est courante » sur une image. C'est justement
// pourquoi il faut BAISSER la temperature : face a l'ambiguite, on veut un
// modele qui doute, pas un qui comble.
const TEMPERATURE_PROFIL = {
  coding: 0.1,
  rapide: 0.0,
  reasoning: 0.4,
  multimodal: 0.2,
};

// Magasin d'observations : chaque appel devient une mesure.
//
// C'est la brique 8 de docs/architecture/Adaptive-Inference-Controller.md,
// et la seule qui rende les suivantes possibles : sans traces accumulees,
// aucun bandit n'a de quoi selectionner, et le controleur adaptatif reste
// une intention.
//
// Elle est posee AVANT le controleur, a dessein. Un systeme qui apprend
// commence par observer ; l'inverse -- decider puis chercher des donnees --
// est la facon dont on justifie une decision au lieu de la fonder.
//
// Ecriture en append, une ligne JSON par appel, jamais bloquante : perdre
// une observation ne doit pas faire echouer l'appel qu'elle observe.
// Aucun contenu de requete ni de reponse n'y figure -- seulement des
// grandeurs. Le magasin ne doit rien reveler qu'un journal de mesure n'ait
// a connaitre.
const OBSERVATIONS = path.join(INSTALL_ROOT, ".nexus", "temperature",
                               "observations.jsonl");

function observer(evenement) {
  try {
    fs.mkdirSync(path.dirname(OBSERVATIONS), { recursive: true });
    fs.appendFileSync(OBSERVATIONS, JSON.stringify(evenement) + "\n", "utf8");
  } catch {
    // Silencieux a dessein, et c'est l'un des rares cas ou c'est justifie :
    // l'observation est un effet de bord de l'appel, jamais sa raison.
  }
}

async function chat(model, messages, maxTokens, timeoutMs, temperature) {
  // Une phase MAP peut durer un quart d'heure : perdre dix fenetres deja
  // calculees pour une coupure de socket serait absurde.
  const t = temperature === undefined ? TEMPERATURE_DEFAUT : temperature;
  const depart = Date.now();
  const corps = { model, messages, max_tokens: maxTokens || 2048 };
  // Les modeles Anthropic recents rejettent certains parametres
  // d'echantillonnage (16, 85) : on ne leur en impose aucun.
  if (t !== null && !String(model).startsWith("claude-")) corps.temperature = t;
  // L'attente du jeton est mesuree A PART, et retranchee de la duree.
  // `observer()` alimente les relevés dont ce depot tire sa doctrine :
  // compter le temps de file dans `duree_ms` gonflerait la latence et
  // ecraserait le debit, c'est-a-dire fausserait les mesures memes qui ont
  // servi a choisir les modeles.
  let attenteMs = 0;
  const appelReseau = () => withRetry(() => requestJson(
    "/v1/chat/completions",
    corps,
    timeoutMs
  ));
  const { body, headers } = estPlanLocal(model)
    ? await avecJetonLocal(() => {
        attenteMs = Date.now() - depart;
        return appelReseau();
      })
    : await appelReseau();
  const choice = body.choices && body.choices[0];
  if (!choice) throw new Error("aucune reponse du modele " + model);
  const usage = body.usage || {};
  // Une generation coupee par max_tokens remontait comme une reponse
  // normale : l'appelant recevait un texte tronque sans le savoir, et
  // pouvait conclure sur une phrase interrompue.
  const tronquee = choice.finish_reason === "length";
  // Derriere un routeur adaptatif, le corps et x-litellm-model-group ne
  // renvoient que le nom du routeur. Seul x-litellm-adaptive-router-model
  // designe le modele que le routeur a choisi.
  const resolved =
    headers["x-litellm-adaptive-router-model"] ||
    headers["x-litellm-model-group"] ||
    body.model ||
    model;
  // L'observation, avant le retour. Les grandeurs seulement : ni prompt ni
  // reponse, et le debit calcule plutot que suppose.
  // La duree du TRAVAIL, l'attente en file retranchee.
  const dureeMs = Date.now() - depart - attenteMs;
  const sortie = usage.completion_tokens || 0;
  observer({
    t: new Date().toISOString(),
    model: resolved,
    upstream: headers["x-litellm-model-name"] || "",
    temperature: t,
    duree_ms: dureeMs,
    // L'attente est rendue VISIBLE plutot que cachee : c'est elle qui prouve
    // que le semaphore travaille, et elle seule permet de juger si la borne
    // est trop basse.
    attente_ms: attenteMs,
    tokens_in: usage.prompt_tokens || 0,
    tokens_out: sortie,
    // Jetons par seconde, la grandeur qui decide pour une generation
    // longue. Nul quand rien n'a ete produit -- une division par une
    // duree ne dit rien s'il n'y a pas eu de sortie.
    debit_jps: sortie && dureeMs ? Number((sortie / (dureeMs / 1000)).toFixed(2)) : null,
    tronquee,
    repli: headers["x-litellm-attempted-fallbacks"] || "0",
  });

  return {
    text: sansRaisonnement((choice.message && choice.message.content) || ""),
    model: resolved,
    upstream: headers["x-litellm-model-name"] || "",
    tokens: (usage.prompt_tokens || 0) + (usage.completion_tokens || 0),
    tronquee,
    // Le cout reel, tel que la passerelle le calcule. Preferable a une
    // affirmation « cout 0 » deduite du nom du modele.
    cout: Number(headers["x-litellm-response-cost-original"] || 0),
  };
}

async function embed(model, inputs) {
  const { body } = await withRetry(() => requestJson(
    "/v1/embeddings", { model, input: inputs }, DEFAULT_TIMEOUT_MS
  ));
  // Sans cette garde, une reponse mal formee produisait
  // « Cannot read properties of undefined » -- message que l'appelant ne
  // peut ni diagnostiquer ni corriger.
  if (!body || !Array.isArray(body.data)) {
    throw new Error(
      "reponse d'embeddings inattendue du modele " + model +
      " : champ 'data' absent"
    );
  }
  return body.data.map((d) => d.embedding);
}

// ---------------------------------------------------------------------------
// Indexation du dépôt (couche RAG locale)
// ---------------------------------------------------------------------------

const SKIP_DIRS = new Set([
  ".git", "node_modules", ".nexus", "backups", "logs", "__pycache__",
  ".venv", "venv", "dist", "build", ".idea", ".vscode",
  // Repertoires de secrets. Le filtre par nom de fichier ne suffisait
  // pas : il refusait bien `.env`, mais laissait indexer
  // `.config/gh/hosts.yml`, `.docker/config.json` ou `secrets/db.yml`,
  // dont les noms ne declenchent rien.
  ".ssh", ".aws", ".gnupg", ".docker", ".kube", ".azure", ".gcloud",
  "secrets", "secret", "credentials", ".credentials", ".config",
]);

const TEXT_EXT = new Set([
  ".md", ".txt", ".yaml", ".yml", ".json", ".ps1", ".py", ".js", ".ts",
  ".tsx", ".jsx", ".sh", ".sql", ".toml", ".ini", ".cfg", ".env.example",
  ".html", ".css", ".java", ".go", ".rs", ".c", ".h", ".cpp", ".rb",
]);

const MAX_FILE_BYTES = 512 * 1024;
const MAX_IMAGE_BYTES = 32 * 1024 * 1024;
const CHUNK_CHARS = 1400;
const CHUNK_OVERLAP = 200;

// Fichiers a ne JAMAIS indexer. Ce n'est pas une precaution de confort :
// les extraits de l'index remontent vers l'orchestrateur, donc quittent la
// machine. Un secret indexe serait un secret exfiltre. La liste est une
// interdiction explicite, et non le simple effet de bord d'une extension
// non reconnue.
const SECRET_FILES = new Set([
  ".env", ".env.local", ".env.production", ".npmrc", ".netrc",
  "credentials", "id_rsa", "id_ed25519", ".htpasswd",
  // Noms anodins qui portent pourtant des jetons.
  "hosts.yml", "known_hosts", "config.json", "auth.json",
  "credentials.json", "service-account.json", ".dockercfg",
]);
const SECRET_PATTERNS = [
  /^\.env($|\.)/i,
  /\.(pem|key|pfx|p12|keystore|jks|ppk)$/i,
  /(^|[._-])secrets?([._-]|$)/i,
  /(^|[._-])credentials?([._-]|$)/i,
];

function isSecretFile(name) {
  if (name === ".env.example") return false; // modele documentaire, sans valeur
  if (SECRET_FILES.has(name.toLowerCase())) return true;
  return SECRET_PATTERNS.some((pattern) => pattern.test(name));
}

function walk(dir, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(full, out);
    } else if (entry.isFile()) {
      if (isSecretFile(entry.name)) {
        log("ignore (secret potentiel) : " + entry.name);
        continue;
      }
      const ext = path.extname(entry.name).toLowerCase();
      if (!TEXT_EXT.has(ext) && entry.name !== ".env.example") continue;
      try {
        if (fs.statSync(full).size > MAX_FILE_BYTES) continue;
      } catch {
        continue;
      }
      out.push(full);
    }
  }
  return out;
}

function chunkText(text) {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    const end = Math.min(start + CHUNK_CHARS, text.length);
    chunks.push({ start, text: text.slice(start, end) });
    if (end >= text.length) break;
    start = end - CHUNK_OVERLAP;
  }
  return chunks;
}

function lineOf(text, offset) {
  let line = 1;
  for (let i = 0; i < offset && i < text.length; i++) {
    if (text[i] === "\n") line++;
  }
  return line;
}

function tokenize(text) {
  return (text.toLowerCase().match(/[a-z0-9_./-]{2,}/g) || []);
}

function cosine(a, b) {
  // Tronquer silencieusement sur la plus courte donnerait un score
  // plausible mais faux — le pire des resultats pour une recherche.
  if (!a || !b || a.length !== b.length) {
    throw new Error(
      "vecteurs de dimensions differentes (" +
      (a ? a.length : 0) + " contre " + (b ? b.length : 0) +
      ") : reconstruire l'index avec nexus_index_build"
    );
  }
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  if (na === 0 || nb === 0) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

async function buildIndex(root, embedModel) {
  // Une racine invalide faisait echouer readdirSync, le catch renvoyait une
  // liste vide, et l'index EXISTANT etait ecrase par un index a zero
  // extrait -- annonce « Index construit. » sans la moindre erreur. On
  // refuse donc en amont plutot que de detruire en silence.
  let stat;
  try {
    stat = fs.statSync(root);
  } catch {
    throw new Error("racine introuvable : " + root);
  }
  if (!stat.isDirectory()) {
    throw new Error("racine invalide : " + root + " n'est pas un repertoire");
  }

  const files = walk(root, []);
  if (!files.length) {
    throw new Error(
      "aucun fichier indexable sous " + root + " : index inchange. " +
      "Ecraser l'index existant par un index vide serait une perte, pas un resultat."
    );
  }
  const records = [];
  const pending = [];

  for (const file of files) {
    let content;
    try {
      content = fs.readFileSync(file, "utf8");
    } catch {
      continue;
    }
    if (!content.trim()) continue;
    for (const chunk of chunkText(content)) {
      if (!chunk.text.trim()) continue;
      records.push({
        file: path.relative(root, file).replace(/\\/g, "/"),
        line: lineOf(content, chunk.start),
        text: chunk.text,
        tokens: tokenize(chunk.text),
      });
      pending.push(chunk.text);
    }
  }

  // Les embeddings partent par lots : un seul appel par chunk saturerait
  // inutilement Ollama, et un lot unique dépasserait la fenêtre.
  const vectors = [];
  const BATCH = 32;
  for (let i = 0; i < pending.length; i += BATCH) {
    const batch = pending.slice(i, i + BATCH);
    const result = await embed(embedModel, batch);
    vectors.push(...result);
    log("indexation " + Math.min(i + BATCH, pending.length) + "/" + pending.length);
  }

  // Une reponse d'embeddings plus courte que le lot decalerait tous les
  // vecteurs suivants et laisserait la queue sans vecteur -- cle que
  // JSON.stringify supprime silencieusement. L'index serait alors annonce
  // « construit », et la recherche renverrait des scores faux ou echouerait
  // entierement. Mieux vaut refuser d'ecrire.
  if (vectors.length !== records.length) {
    throw new Error(
      "embeddings incomplets : " + vectors.length + " vecteurs pour " +
      records.length + " extraits. Index non ecrit."
    );
  }

  for (let i = 0; i < records.length; i++) {
    records[i].vector = vectors[i];
  }

  const index = {
    root,
    model: embedModel,
    built: new Date().toISOString(),
    files: files.length,
    chunks: records.length,
    records,
  };
  fs.mkdirSync(INDEX_DIR, { recursive: true });
  // Ecriture atomique : une interruption pendant writeFileSync laisserait
  // un index tronque, que loadIndex ne saurait pas distinguer d'un index
  // valide. Le renommage, lui, est indivisible.
  const provisoire = INDEX_PATH + ".tmp";
  fs.writeFileSync(provisoire, JSON.stringify(index), "utf8");
  fs.renameSync(provisoire, INDEX_PATH);
  return index;
}

// Index garde en memoire entre deux recherches. Il etait relu et reparse a
// chaque appel : mesure a 54 994 octets par extrait, un index complet du
// depot represente pres de 100 Mo de JSON reanalyses pour repondre a une
// question -- plus long que l'embedding de la requete lui-meme.
//
// L'invalidation se fait sur (mtime, taille) du fichier, jamais sur une
// duree : une reconstruction par nexus_index_build doit etre visible a la
// recherche suivante, et une expiration au temps rendrait le moment ou
// l'ancien index cesse de repondre imprevisible. La taille complete le
// mtime parce que la resolution de l'horodatage ne separe pas toujours deux
// ecritures rapprochees.
let indexCache = null;

function loadIndex() {
  let stat;
  try {
    stat = fs.statSync(INDEX_PATH);
  } catch {
    indexCache = null;
    return null;
  }
  if (indexCache &&
      indexCache.mtimeMs === stat.mtimeMs &&
      indexCache.size === stat.size) {
    return indexCache.index;
  }
  try {
    const index = JSON.parse(fs.readFileSync(INDEX_PATH, "utf8"));
    indexCache = { mtimeMs: stat.mtimeMs, size: stat.size, index };
    return index;
  } catch {
    // Un index illisible ne doit pas laisser en place le precedent : la
    // recherche repondrait sur un etat que le disque ne contient plus.
    indexCache = null;
    return null;
  }
}

async function searchIndex(query, k, embedModel) {
  const index = loadIndex();
  if (!index) {
    throw new Error("aucun index : appeler d'abord nexus_index_build");
  }
  // La requete DOIT etre encodee par le modele qui a construit l'index.
  // Deux modeles differents ne partagent pas d'espace vectoriel : les
  // scores seraient silencieusement faux, ou les dimensions incompatibles.
  const model = embedModel || index.model;
  if (embedModel && embedModel !== index.model) {
    throw new Error(
      "index construit avec " + index.model + " mais recherche demandee avec " +
      embedModel + " : reconstruire l'index ou utiliser le meme modele"
    );
  }
  const [queryVector] = await embed(model, [query]);
  const expected = index.records.length ? index.records[0].vector.length : 0;
  if (expected && queryVector.length !== expected) {
    throw new Error(
      "dimensions incompatibles (" + queryVector.length + " contre " + expected +
      ") : reconstruire l'index avec nexus_index_build"
    );
  }
  const queryTokens = new Set(tokenize(query));

  // Récupération hybride : la similarité vectorielle seule rate les
  // identifiants exacts (noms de fichiers, de fonctions, de variables),
  // que le recouvrement lexical retrouve (§57).
  const scored = index.records.map((record) => {
    const semantic = cosine(queryVector, record.vector);
    let overlap = 0;
    for (const token of new Set(record.tokens)) {
      if (queryTokens.has(token)) overlap++;
    }
    const lexical = queryTokens.size ? overlap / queryTokens.size : 0;
    return { record, score: 0.75 * semantic + 0.25 * lexical, semantic, lexical };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k || 8);
}

// ---------------------------------------------------------------------------
// Définition des outils
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Profils d'exécution
// ---------------------------------------------------------------------------

/**
 * Un profil décrit une CLASSE DE TÂCHE, pas un modèle. C'est ce qui permet
 * de demander « du code » plutôt que « qwen3-coder », et de laisser la
 * plateforme arbitrer selon ce qui est réellement disponible et exécutable.
 *
 * L'ordre des candidats est un ordre de préférence, pas une exigence : le
 * premier réellement exposé l'emporte. Les modèles distants viennent en
 * dernier, pour qu'on n'engage une dépense qu'à défaut d'alternative locale.
 *
 * Repris des profils décrits dans execution-profiles.txt, ajustés à ce que
 * la machine sait faire : `coding` demandait 64K, seul `releve-locale` les
 * offre ici, il vient donc en tête.
 */
// Budgets de latence, repris de Latency-budget.txt : une cible et une limite
// dure par profil, pour que le delai d'un appel decoule du travail demande au
// lieu d'un reglage unique.
//
// Ces nombres sont des DECISIONS de politique, pas des mesures -- et il faut
// le dire, le depot distinguant les deux avec soin. Leur logique : « rapide »
// sert la classification et l'extraction, un modele qui y met plus de deux
// minutes n'est pas rapide, quoi qu'il reponde ; « coding » et « reasoning »
// portent un travail long, ou couper tot gaspille ce qui est deja calcule.
// La cible n'est pas encore exploitee : elle attend une mesure de latence par
// modele, que la plateforme ne conserve pas.
//
// CAPACITE « tools ». Le moteur declare, pour chaque modele, s'il sait
// appeler un outil. Releve du 2026-08-30 : dix-neuf modeles installes sur
// cinquante-quatre ne le savent pas, et six d'entre eux figurent dans ces
// profils.
//
//   coding      codestral-22b, deepseek-coder-33b
//   rapide      phi3-mini, qui est aussi ultime-recourse
//   multimodal  llava-7b, llava-34b, llava-13b -- ses TROIS premiers
//
// Ce n'est un defaut que pour les usages qui appellent reellement un
// outil : decrire une image n'en demande aucun, et nexus_vision fonctionne
// donc tres bien avec llava. Les candidats sont annotes plutot que
// reordonnes, pour que le choix soit informe sans etre force.
//
// Le repere se lit « outils=oui/non » a cote de chaque candidat concerne.
const PROFILES = {
  coding: {
    latency: { target_ms: 30000, hard_limit_ms: 600000 },
    description: "implementation, debogage, refactorisation",
    contextMin: 32768,
    // Ordre etabli par la mesure (.nexus/latences.json, 2026-08-30), a
    // specialisation egale. Il l'etait auparavant a l'estime, et cela
    // coutait cher : les deux premiers etaient releve-locale et
    // glm-4.7-flash-local, soit le MEME modele mesure a 61,8 s -- le plus
    // lent du banc en tete d'un profil que le premier expose emporte (109).
    // qwen3-coder-30b reste en tete : il est le meilleur sur les DEUX
    // mesures, 2,4 s au demarrage et 20,22 j/s en generation.
    // glm-4.7-flash remonte en deuxieme : son debit mesure (19,85 j/s) est
    // le second de l'hote, et son demarrage lent ne se paie qu'une fois.
    models: ["qwen3-coder-30b-local",      // 2,4 s, 20,22 j/s
             "glm-4.7-flash-local",        // 61,8 s, 19,85 j/s
             "codestral-22b-local",        // 2,8 s, debit non mesure, outils=non
             "qwen2.5-coder-32b-local",    // 3,4 s, debit non mesure
             "deepseek-coder-33b-local",   // 3,9 s, debit non mesure, outils=non
             "kimi-k2.7-code-cloud", "gpt-oss-120b-cloud"],
  },
  reasoning: {
    latency: { target_ms: 60000, hard_limit_ms: 900000 },
    description: "architecture, raisonnement difficile, arbitrages",
    contextMin: 32768,
    // Ordre corrige une seconde fois, et par la mesure qui manquait.
    //
    // Il avait d'abord ete etabli sur le DEMARRAGE, ce qui mettait
    // qwen2.5-32b-local en tete (3,8 s) et reléguait glm-4.7-flash-local
    // en dernier local (61,8 s). Le banc de debit renverse ce classement :
    //
    //   glm-4.7-flash-local     19,85 j/s
    //   qwen2.5-32b-local       moins de 1,7 j/s (256 jetons non rendus
    //                           en 150 s)
    //
    // Douze fois plus lent en generation. Or le raisonnement produit de
    // longues sorties : c'est le debit qui domine, le demarrage n'etant
    // paye qu'une fois. Le classement par demarrage etait donc une
    // regression, introduite le matin meme en croyant corriger.
    //
    // qwen2.5-32b n'est pas ecarte pour autant -- c'est un generaliste, la
    // ou les deux premiers sont des specialistes du code -- mais il passe
    // en dernier candidat local, ou son debit pese moins.
    models: ["qwen3-coder-30b-local",      // 2,4 s au demarrage, 20,22 j/s
             "glm-4.7-flash-local",        // 61,8 s, mais 19,85 j/s
             "gemma4-31b-local",           // 41,6 s, debit non mesure
             "qwen2.5-32b-local",          // 3,8 s, moins de 1,7 j/s
             "nemotron-3-ultra-cloud", "gpt-oss-120b-cloud"],
  },
  rapide: {
    latency: { target_ms: 5000, hard_limit_ms: 120000 },
    description: "classification, extraction, transformation courte",
    contextMin: 8192,
    // gemma4-12b-local est retire de ce profil : 51,5 s mesurees, dans une
    // liste nommee « rapide » et dont le budget vise 5 s. Il y figurait par
    // supposition -- douze milliards de parametres, donc suppose leger --
    // et c'est le plus lent du banc entier.
    models: ["llama3.2-3b-local",          // 2,3 s
             "llama3.2-1b-local",          // 2,3 s
             "phi3-mini-local",            // 2,5 s, outils=non
             "qwen2.5-coder-7b-local",     // 2,5 s
             "gpt-oss-20b-cloud"],
  },
  multimodal: {
    latency: { target_ms: 60000, hard_limit_ms: 900000 },
    description: "image, capture d'ecran, OCR",
    contextMin: 8192,
    // Deja dans le bon ordre, la mesure le confirme : llava-7b 2,8 s,
    // llava-13b 4,1 s, llama3.2-vision-11b 9,5 s, qwen3-vl-8b 38,2 s.
    // llava-34b (3,1 s) est intercale : plus gros et pourtant plus rapide
    // que les deux derniers.
    models: ["llava-7b-local",             // 2,8 s, outils=non
             "llava-34b-local",            // 3,1 s, outils=non
             "llava-13b-local",            // 4,1 s, outils=non
             "llama3.2-vision-11b-local",  // 9,5 s
             "qwen3-vl-8b-local"],         // 38,2 s
  },
};

let cachedExposed = null;
// Duree de validite des inventaires mis en cache. Sans elle, un inventaire
// vide lu une seule fois au demarrage de la passerelle restait vrai pour
// toute la duree du processus -- et un `Set` vide etant truthy, le cache ne
// se reparait jamais. Deux outils du meme serveur se contredisaient alors.
const CACHE_MS = 60000;
let cacheExpire = 0;
let plansConnus = null;
let plansExpire = 0;

async function exposedModels() {
  if (cachedExposed && cachedExposed.size && Date.now() < cacheExpire) {
    return cachedExposed;
  }
  const data = await getJson("/v1/models");
  const ensemble = new Set((data.data || []).map((d) => d.id));
  // Un inventaire vide n'est pas mis en cache : c'est un symptome, pas un
  // etat stable.
  if (ensemble.size) {
    cachedExposed = ensemble;
    cacheExpire = Date.now() + CACHE_MS;
  }
  return ensemble;
}

/**
 * Plan d'execution de chaque alias, lu a la source.
 *
 * `/v1/model/info` renvoie les `litellm_params` reels : le fournisseur et
 * l'`api_base`. C'est la seule source qui fasse autorite. Deduire le plan du
 * suffixe du nom se trompait des qu'un alias sortait de la convention --
 * `releve-locale` etait classe « Anthropic, facture au token » alors qu'il
 * est 100 % local, et c'est le premier candidat du profil `coding`.
 */
async function chargerPlans() {
  if (plansConnus && Date.now() < plansExpire) return plansConnus;
  try {
    const data = await getJson("/v1/model/info");
    const items = data.data || data || [];
    const table = new Map();
    for (const m of items) {
      const alias = m.model_name;
      const params = m.litellm_params || {};
      const raw = String(params.model || "");
      const base = String(params.api_base || "");
      if (!alias) continue;
      if (raw.startsWith("auto_router/")) table.set(alias, "routeur");
      else if (raw.startsWith("anthropic/")) table.set(alias, "anthropic");
      else if (base.includes("ollama.com")) table.set(alias, "cloud");
      else table.set(alias, "local");
    }
    if (table.size) {
      plansConnus = table;
      plansExpire = Date.now() + CACHE_MS;
    }
  } catch (err) {
    log("plans indisponibles (" + err.message.slice(0, 60) + ") — repli sur le nom");
  }
  return plansConnus;
}

async function resolveProfile(profile) {
  const spec = PROFILES[profile];
  if (!spec) {
    throw new Error(
      "profil inconnu : " + profile + " (attendus : " +
      Object.keys(PROFILES).join(", ") + ")"
    );
  }
  const exposed = await exposedModels();
  for (const candidate of spec.models) {
    if (exposed.has(candidate)) return { model: candidate, spec };
  }
  throw new Error(
    "aucun modele du profil '" + profile + "' n'est expose : " +
    spec.models.join(", ")
  );
}

const PLANES_DOC =
  "Trois plans d'execution sont accessibles, et le choix engage cout et confidentialite :\n" +
  "  *-local  : gratuit, aucune donnee ne quitte la machine, hote CPU (lent sur les gros modeles).\n" +
  "  *-cloud  : couvert par l'abonnement Ollama Cloud, les donnees sortent vers ollama.com.\n" +
  "  claude-* : FACTURE AU TOKEN sur les credits API Anthropic. Ce n'est PAS l'abonnement\n" +
  "             claude.ai : une passerelle ne peut pas emprunter la connexion d'abonnement.\n" +
  "             A ne choisir que si la tache le justifie vraiment.";

// ---------------------------------------------------------------------------
// Contexte distribué : atteindre 1M à partir de fenêtres de 64K
// ---------------------------------------------------------------------------

/**
 * Aucun modèle local n'offre 1M de contexte, et lui en allouer coûterait
 * une mémoire dont la machine ne dispose pas. On obtient l'équivalent
 * autrement : le corpus est découpé en fenêtres qui tiennent réellement,
 * chaque fenêtre est traitée séparément (phase MAP), puis les résultats
 * sont fusionnés par paliers jusqu'à tenir dans une seule fenêtre
 * (phase REDUCE).
 *
 * Le contexte effectif n'est donc plus borné par le modèle mais par le
 * temps qu'on accepte d'y passer — ce qui, en local, ne coûte rien d'autre.
 */

// ~4 caractères par token : approximation usuelle, volontairement
// prudente. Mieux vaut sous-remplir une fenêtre que la faire déborder.
const CHARS_PER_TOKEN = 4;

function windowChars(contextTokens, reservedForOutput) {
  const usable = Math.max(contextTokens - reservedForOutput, 1024);
  // 85 % : la consigne, le prompt système et les marqueurs occupent le reste.
  return Math.floor(usable * CHARS_PER_TOKEN * 0.85);
}

function splitIntoWindows(text, budget) {
  const windows = [];
  let start = 0;
  while (start < text.length) {
    let end = Math.min(start + budget, text.length);
    if (end < text.length) {
      // On coupe sur une frontière naturelle plutôt qu'au milieu d'un mot
      // ou d'une ligne de code, pour ne pas amputer le sens.
      const slice = text.slice(start, end);
      const breakAt = Math.max(
        slice.lastIndexOf("\n\n"),
        slice.lastIndexOf("\n"),
        slice.lastIndexOf(". ")
      );
      if (breakAt > budget * 0.5) end = start + breakAt + 1;
    }
    windows.push(text.slice(start, end));
    start = end;
  }
  return windows;
}

// Pour que la fusion converge, il faut qu'au moins trois analyses tiennent
// ensemble dans une fenetre. Si chaque analyse pesait autant qu'une fenetre,
// chaque palier recopierait ses entrees sans jamais reduire : la boucle
// s'arretait alors sur `next.length >= level.length` et rendait une simple
// concatenation -- plus volumineuse que le corpus d'origine -- en la
// presentant comme une synthese. Le plafond de sortie derive donc du budget
// reel au lieu d'etre la constante 1536.
const REDUCTION_FACTOR = 3;

function mapReduceBudgets(contextTokens) {
  const window = windowChars(contextTokens, 2048);
  const mapTokens = Math.floor(window / CHARS_PER_TOKEN / REDUCTION_FACTOR);
  return { window, mapTokens };
}

// Plancher de contexte du plan local, MESURE et non grave dans le code.
//
// Il depend de la machine hote : nexus_capability.py la mesure,
// nexus_generate en deduit le max_input_tokens de chaque modele, et la
// passerelle l'expose. Une constante ecrite ici deviendrait fausse a la
// premiere migration vers une machine plus capable, et il faudrait la
// retrouver a la main dans deux fichiers.
//
// Le MINIMUM et non la moyenne : une fenetre doit tenir dans le plus etroit
// des modeles qui peuvent la recevoir, faute de quoi celui-la rame jusqu'au
// delai sans rendre ni erreur ni troncature.
const CONTEXTE_LOCAL_REPLI = 8192;
let contexteLocalCache = null;

async function contexteLocalMinimal() {
  const force = process.env.NEXUS_CONTEXTE_LOCAL;
  if (force) return Number(force);
  if (contexteLocalCache !== null) return contexteLocalCache;
  let valeur = CONTEXTE_LOCAL_REPLI;
  try {
    const reponse = await fetch(`${LITELLM_URL}/model/info`, {
      headers: { Authorization: `Bearer ${masterKey()}` },
    });
    const donnees = await reponse.json();
    const contextes = (donnees.data || [])
      .filter((m) => String(m.model_name || "").endsWith("-local"))
      .map((m) => (m.model_info || {}).max_input_tokens)
      .filter((c) => c);
    if (contextes.length) valeur = Math.min(...contextes);
  } catch {
    // Passerelle muette : on garde le repli plutot que de lever. Le
    // decoupage doit rester possible meme sans elle.
  }
  contexteLocalCache = valeur;
  return valeur;
}

async function mapReduce(text, instruction, model, contextTokens, onProgress) {
  // Le budget suit le plus PETIT contexte des plans qui peuvent recevoir une
  // fenetre.
  //
  // Depuis que le MAP repartit entre plans, une fenetre taillee pour 32 768
  // jetons -- le defaut ici -- peut atterrir sur un modele local, dont six
  // sur sept plafonnent a 8 192. Mesure du 30 aout 2026 cote Python, sur le
  // meme genre de depassement : aucune reponse au bout de 300 s, ni erreur
  // ni troncature, le modele rame jusqu'au delai. Le rattrapage sauvait le
  // resultat mais masquait le gaspillage.
  //
  // Mieux vaut plus de fenetres que des fenetres qu'un plan sur deux ne peut
  // pas lire.
  if (model.startsWith("adaptive-router") && !model.endsWith("-cloud")) {
    contextTokens = Math.min(contextTokens, await contexteLocalMinimal());
  }
  const { window: budget, mapTokens } = mapReduceBudgets(contextTokens);
  if (mapTokens < 256) {
    // En dessous, une analyse ne tient plus en quelques phrases utiles :
    // mieux vaut le dire que rendre un resultat degrade sans le signaler.
    throw new Error(
      `fenetre de ${contextTokens} tokens trop etroite pour une fusion par paliers ` +
      `(il en faut ~5700). Choisissez un modele a plus grand contexte, ou passez ` +
      `par nexus_search pour ne remonter que les passages utiles.`
    );
  }
  const windows = splitIntoWindows(text, budget);
  let tokens = 0;

  const MAP_SYSTEM =
    "Tu analyses UN FRAGMENT d'un ensemble plus vaste. Extrais fidelement " +
    "ce qui repond a la consigne, sans rien inventer et sans conclure sur " +
    "l'ensemble : d'autres fragments seront traites separement. Si le " +
    "fragment ne contient rien d'utile, reponds exactement : RIEN.";

  // --- MAP -----------------------------------------------------------
  // Les fenetres sont independantes : les traiter une par une faisait payer
  // la latence autant de fois qu'il y a de fragments.
  //
  // Elles se repartissent entre les DEUX plans, qui travaillent ensemble :
  // ils ne se disputent rien, le local etant borne par la machine et le
  // cloud par le reseau.
  const PLAFOND_FILS = { cloud: 3, local: 2 };
  const slots = new Array(windows.length);
  let termines = 0;

  // Les ouvriers piochent dans une FILE COMMUNE plutot que de recevoir une
  // part decidee d'avance.
  //
  // Un ratio fixe suppose connu le rapport de debit entre les plans, rapport
  // qui change avec la machine, le modele et la charge. Une file ne suppose
  // rien : chaque ouvrier prend la fenetre suivante des qu'il est libre, donc
  // le plan rapide en traite naturellement davantage.
  //
  // Verifie en laboratoire, latences controlees : avec un plan trente fois
  // plus rapide, il prend 18 fenetres sur 20 sans qu'aucun ratio ne lui soit
  // souffle. Les durees relevees en conditions reelles ont ete ecartees, le
  // cache exact de la passerelle et la charge concurrente les rendant
  // incomparables.
  //
  // L'equilibre se mesure donc a l'execution au lieu de se deviner. Et si un
  // plan s'effondre, l'autre vide la file sans qu'aucune regle ne l'ait prevu.
  let prochaine = 0;
  const parPlan = {};

  async function mapOuvrier(modele) {
    // Increment puis lecture en un seul tour synchrone : la boucle
    // evenementielle est monothreadee, deux ouvriers ne peuvent pas obtenir
    // le meme indice.
    for (let i = prochaine++; i < windows.length; i = prochaine++) {
      const result = await chat(
        modele,
        [
          { role: "system", content: MAP_SYSTEM },
          {
            role: "user",
            content:
              `Consigne : ${instruction}

` +
              `--- fragment ${i + 1}/${windows.length} ---
${windows[i]}`,
          },
        ],
        mapTokens
      );
      tokens += result.tokens;
      const body = (result.text || "").trim();
      // Ecriture a indice fixe : l'ordre des fragments est preserve meme si
      // les reponses reviennent dans le desordre. Un REDUCE qui recolle des
      // fragments melanges produit un resume incoherent.
      if (body && body.toUpperCase() !== "RIEN") slots[i] = body;
      parPlan[modele] = (parPlan[modele] || 0) + 1;
      termines += 1;
      // Avancement reel et non indice de fenetre, sinon la jauge reculerait
      // des qu'une reponse rapide devance une lente.
      if (onProgress) onProgress("map", termines, windows.length);
    }
  }

  const ouvriers = [];
  if (model.startsWith("adaptive-router")) {
    for (let w = 0; w < PLAFOND_FILS.cloud; w++) ouvriers.push(mapOuvrier("adaptive-router-cloud"));
    for (let w = 0; w < PLAFOND_FILS.local; w++) ouvriers.push(mapOuvrier("adaptive-router-local"));
  } else {
    // Un modele nomme explicitement par l'appelant n'est jamais substitue.
    for (let w = 0; w < 4; w++) ouvriers.push(mapOuvrier(model));
  }
  await Promise.all(ouvriers);

  // Les reponses RIEN laissent des trous : on retombe sur un tableau dense,
  // dans le meme ordre que la version sequentielle.
  const mapped = slots.filter((s) => s !== undefined);

  if (!mapped.length) {
    return { text: "Aucun fragment pertinent.", windows: windows.length,
             passes: 1, tokens, model, converge: true };
  }

  // --- REDUCE --------------------------------------------------------
  const REDUCE_SYSTEM =
    "Tu fusionnes des analyses partielles d'un meme ensemble. Produis une " +
    "synthese unique, fidele et sans redite. Ne rajoute aucune information " +
    "absente des analyses fournies.";

  let level = mapped;
  let passes = 1;
  let converge = true;
  while (level.length > 1) {
    const next = [];
    let group = [];
    let size = 0;
    const flush = async () => {
      if (!group.length) return;
      if (group.length === 1) {
        next.push(group[0]);
      } else {
        const result = await chat(
          model,
          [
            { role: "system", content: REDUCE_SYSTEM },
            {
              role: "user",
              content:
                `Consigne d'origine : ${instruction}\n\n` +
                group.map((t, i) => `--- analyse ${i + 1} ---\n${t}`).join("\n\n"),
            },
          ],
          mapTokens
        );
        tokens += result.tokens;
        next.push((result.text || "").trim());
      }
      group = [];
      size = 0;
    };
    for (const item of level) {
      if (size + item.length > budget && group.length) await flush();
      group.push(item);
      size += item.length;
    }
    await flush();
    passes++;
    if (onProgress) onProgress("reduce", next.length, level.length);
    if (next.length >= level.length) {
      // Aucune réduction possible : on s'arrête plutôt que de boucler. Ce
      // qu'on rend n'est alors PAS une synthèse mais une concaténation, et
      // l'appelant doit le savoir — sans quoi il accorderait à un collage
      // le crédit d'un texte fusionné et vérifié.
      level = [next.join("\n\n")];
      converge = false;
      break;
    }
    level = next;
  }

  return { text: level[0], windows: windows.length, passes, tokens, model, converge };
}

const TOOLS = [
  {
    name: "nexus_ask",
    title: "Interroger un modele de la passerelle",
    description:
      "Delegue une tache a n'importe quel modele expose par la passerelle LiteLLM. " +
      "Sert a repartir le travail : le volume repetitif part en local (gratuit), " +
      "les taches lourdes vers Ollama Cloud, et Claude n'est sollicite que si sa " +
      "specificite le justifie.\n\n" + PLANES_DOC,
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "La demande adressee au modele." },
        system: { type: "string", description: "Consigne systeme optionnelle." },
        model: {
          type: "string",
          description:
            "Alias LiteLLM. Defaut " + DEFAULT_CHAT_MODEL + " (local, rapide). " +
            "Exemples : qwen3-coder-30b-local, gpt-oss-120b-cloud, claude-haiku-4-5. " +
            "Appeler nexus_models pour l'inventaire a jour.",
        },
        profile: {
          type: "string",
          enum: Object.keys(PROFILES),
          description:
            "Classe de tache, a la place d'un modele : " +
            Object.entries(PROFILES).map(([k, v]) => k + " (" + v.description + ")").join(", ") +
            ". La plateforme retient le premier candidat reellement expose, " +
            "en privilegiant le local.",
        },
        max_tokens: { type: "integer", description: "Longueur maximale de la reponse. Defaut 2048." },
      },
      required: ["prompt"],
    },
  },
  {
    name: "nexus_route",
    title: "Laisser le routeur adaptatif choisir",
    description:
      "Confie la tache au routeur adaptatif de LiteLLM, qui selectionne le modele " +
      "dans le plan demande. A utiliser quand le modele exact importe moins que le " +
      "respect d'une frontiere de cout ou de confidentialite.",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "La demande adressee au routeur." },
        system: { type: "string", description: "Consigne systeme optionnelle." },
        plane: {
          type: "string",
          enum: ["local", "cloud", "anthropic", "all"],
          description:
            "Plan autorise. 'local' garantit qu'aucune donnee ne sort. " +
            "'anthropic' consomme des credits API. 'all' couvre local + cloud, " +
            "jamais Anthropic. Defaut 'local'.",
        },
        max_tokens: { type: "integer", description: "Longueur maximale de la reponse. Defaut 2048." },
      },
      required: ["prompt"],
    },
  },
  {
    name: "nexus_context",
    title: "Traiter un corpus plus grand que toute fenetre",
    description:
      "Traite un ensemble de fichiers dont le volume depasse la fenetre de " +
      "n'importe quel modele. Le corpus est decoupe en fenetres qui tiennent " +
      "reellement, chaque fragment est analyse separement, puis les resultats " +
      "sont fusionnes par paliers jusqu'a une synthese unique.\n\n" +
      "C'est ainsi qu'on atteint l'equivalent d'un contexte de 1M sans " +
      "qu'aucun modele n'en dispose : le plafond n'est plus la fenetre mais " +
      "le temps, qui en local ne coute rien. A preferer a la lecture " +
      "exhaustive des que le corpus depasse quelques dizaines de milliers de " +
      "tokens.",
    inputSchema: {
      type: "object",
      properties: {
        paths: {
          type: "array",
          items: { type: "string" },
          description: "Fichiers a traiter, relatifs a la racine du depot ou absolus.",
        },
        text: { type: "string", description: "Texte brut, alternative a 'paths'." },
        instruction: {
          type: "string",
          description: "Ce qu'il faut extraire, analyser ou verifier dans le corpus.",
        },
        model: { type: "string", description: "Alias LiteLLM. Defaut " + DEFAULT_CHAT_MODEL + "." },
        context_tokens: {
          type: "integer",
          description:
            "Fenetre du modele, en tokens. Defaut 32768. La declarer plus " +
            "grande que la fenetre reelle ferait deborder chaque fragment.",
        },
      },
      required: ["instruction"],
    },
  },
  {
    name: "nexus_vision",
    title: "Analyser une image en local",
    description:
      "Analyse une image avec un modele multimodal local : description, " +
      "lecture de texte, analyse de capture d'ecran, debogage visuel. " +
      "L'image ne quitte pas la machine. Lent sur un hote CPU : compter " +
      "plusieurs minutes selon la taille de l'image.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Chemin de l'image (png, jpg, webp, gif)." },
        prompt: {
          type: "string",
          description: "Question posee sur l'image. Defaut : description generale.",
        },
        model: {
          type: "string",
          description:
            "Alias LiteLLM d'un modele multimodal. Defaut " + DEFAULT_VISION_MODEL +
            ". Alternatives : llama3.2-vision-11b-local, qwen3-vl-8b-local.",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "nexus_summarize",
    title: "Resumer des fichiers",
    description:
      "Lit des fichiers du depot et en produit une synthese via un modele local. " +
      "Sert a reduire le contexte AVANT de raisonner : le volume est absorbe gratuitement " +
      "en local, seul le resultat distille remonte. Chaque fichier est traite separement, " +
      "un fichier plus large que la fenetre passe par une fusion par paliers plutot que " +
      "d'etre tronque, puis une synthese fusionnee est produite au-dessus du detail " +
      "par fichier des qu'il y a plus d'un fichier.",
    inputSchema: {
      type: "object",
      properties: {
        paths: {
          type: "array",
          items: { type: "string" },
          description: "Chemins des fichiers, relatifs a la racine du depot ou absolus.",
        },
        instruction: {
          type: "string",
          description: "Ce qu'il faut extraire ou resumer. Defaut : synthese technique.",
        },
        model: { type: "string", description: "Alias LiteLLM. Defaut " + DEFAULT_CHAT_MODEL + "." },
        context_tokens: {
          type: "number",
          description:
            "Fenetre reelle du modele choisi, en tokens. Defaut 32768. Determine a " +
            "partir de quelle taille un fichier est decoupe.",
        },
        fusionner: {
          type: "boolean",
          description:
            "Produire la synthese fusionnee en tete (defaut true). false economise " +
            "un appel quand seul le detail par fichier est utile.",
        },
      },
      required: ["paths"],
    },
  },
  {
    name: "nexus_index_build",
    title: "Indexer le depot en local",
    description:
      "Construit l'index d'embeddings du depot avec un modele local. " +
      "L'index est stocke dans .nexus/index.json et ne quitte jamais la machine ; " +
      "les fichiers susceptibles de contenir des secrets (.env, cles, certificats) " +
      "sont exclus. A relancer apres des modifications importantes. " +
      "Duree : sur un hote CPU l'indexation d'un depot entier peut prendre " +
      "plusieurs minutes. Restreindre 'root' a un sous-dossier pour un premier essai.",
    inputSchema: {
      type: "object",
      properties: {
        root: { type: "string", description: "Racine a indexer. Defaut : racine du depot." },
        model: { type: "string", description: "Modele d'embedding. Defaut " + DEFAULT_EMBED_MODEL + "." },
      },
    },
  },
  {
    name: "nexus_search",
    title: "Rechercher dans l'index local",
    description:
      "Recherche hybride (semantique + lexicale) dans l'index du depot. " +
      "Renvoie les extraits pertinents avec fichier et ligne, sans charger les fichiers entiers. " +
      "A preferer a la lecture exhaustive quand la question porte sur 'ou se trouve' ou 'comment marche'.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "La question ou les termes recherches." },
        k: { type: "integer", description: "Nombre d'extraits renvoyes. Defaut 8." },
        model: {
          type: "string",
          description:
            "Modele d'embedding. Par defaut celui qui a construit l'index — " +
            "en imposer un autre est refuse, les espaces vectoriels differant.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "nexus_batch",
    title: "Executer plusieurs taches en une fois",
    description:
      "Enchaine plusieurs demandes independantes, chacune pouvant viser un " +
      "modele different. Sert a traiter un lot sans multiplier les allers-" +
      "retours : classification d'une liste, extraction sur plusieurs " +
      "fichiers, meme question posee a plusieurs modeles.\n\n" +
      "L'execution est sequentielle a dessein : sur un hote CPU, deux " +
      "inferences simultanees se disputent la meme bande passante memoire " +
      "et finissent plus tard que si elles s'etaient suivies.",
    inputSchema: {
      type: "object",
      properties: {
        tasks: {
          type: "array",
          description: "Les taches, dans l'ordre d'execution.",
          items: {
            type: "object",
            properties: {
              prompt: { type: "string" },
              model: { type: "string" },
              system: { type: "string" },
              max_tokens: { type: "integer" },
            },
            required: ["prompt"],
          },
        },
        model: {
          type: "string",
          description: "Modele par defaut des taches qui n'en precisent pas.",
        },
      },
      required: ["tasks"],
    },
  },
  {
    name: "nexus_compare",
    title: "Comparer plusieurs modeles sur la meme demande",
    description:
      "Pose la meme question a plusieurs modeles et renvoie leurs reponses " +
      "cote a cote, avec le temps et le cout de chacune. Sert a decider sur " +
      "mesure plutot que sur reputation : avant de promouvoir un modele dans " +
      "un pool de routage, ou pour verifier qu'un modele local suffit la ou " +
      "l'on paie un modele distant.",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "La demande, identique pour tous." },
        models: {
          type: "array",
          items: { type: "string" },
          description: "Alias a comparer. Deux a quatre est un bon ordre de grandeur.",
        },
        system: { type: "string" },
        max_tokens: { type: "integer" },
      },
      required: ["prompt", "models"],
    },
  },
  {
    name: "nexus_profile",
    title: "Connaitre les limites reelles de la machine",
    description:
      "Renvoie le profil materiel mesure — memoire offerte au moteur " +
      "d'inference, CPU, GPU, disque — et le verdict par modele : eligible " +
      "au routage automatique, adressable seulement, ou inexecutable ici.\n\n" +
      "A consulter avant de choisir un gros modele : sur cette machine, un " +
      "modele plus lourd que la memoire du moteur ne renvoie pas d'erreur, " +
      "il pagine et ne repond jamais utilement.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "nexus_savings",
    title: "Mesurer ce que la delegation fait economiser",
    description:
      "Rapporte le volume passe par la passerelle, ventile par plan " +
      "d'execution, et ce que ce volume aurait coute sur Claude. Le trafic " +
      "de l'abonnement n'y figure pas : il ne passe pas par la passerelle. " +
      "Le chiffre mesure donc le volume detourne, pas l'abonnement restant.",
    inputSchema: {
      type: "object",
      properties: {
        jours: { type: "integer", description: "Fenetre d'observation. Defaut 7." },
      },
    },
  },
  {
    name: "nexus_models",
    title: "Lister les modeles disponibles",
    description:
      "Liste les modeles exposes par la passerelle LiteLLM, classes par domaine " +
      "(local / Ollama Cloud / Anthropic) afin de choisir en connaissance de cause " +
      "ou quitte la machine.",
    inputSchema: { type: "object", properties: {} },
  },
];

function resolvePath(p) {
  return path.isAbsolute(p) ? p : path.join(WORK_ROOT, p);
}

/**
 * Refuse tout chemin sortant du depot.
 *
 * Sans cette borne, `nexus_index_build {root:"C:/Users/moi"}` embarquait
 * le repertoire personnel : chaque fragment partait vers /v1/embeddings,
 * atterrissait en clair dans .nexus/index.json, et nexus_search le
 * restituait verbatim a l'orchestrateur -- donc hors de la machine. Un
 * simple `../` suffisait, le filtre ne regardant que le nom de fichier.
 */
function insideRepo(target) {
  const relative = path.relative(WORK_ROOT, path.resolve(target));
  return relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function requireInsideRepo(target, quoi) {
  if (!insideRepo(target)) {
    throw new Error(
      quoi + " hors du depot refuse : " + target + ". " +
      "Le pont ne lit que sous " + WORK_ROOT + " ; ses extraits remontent " +
      "a l'orchestrateur et quitteraient donc la machine."
    );
  }
  return target;
}

/**
 * Faute de PROTOCOLE, par opposition a un echec d'execution.
 *
 * MCP separe les deux, et cette separation porte une information que
 * l'appelant ne peut reconstituer autrement. Un outil qui echoue rend un
 * resultat marque `isError` que le modele peut lire et corriger ; un nom
 * d'outil inexistant ou un argument manquant sont des fautes de l'appelant,
 * que JSON-RPC signale par -32602. Les confondre -- ce que faisait ce
 * serveur -- rendait « le modele a mal appele » indiscernable de « le
 * modele a mal repondu ».
 */
class ErreurProtocole extends Error {
  constructor(message) {
    super(message);
    this.name = "ErreurProtocole";
    this.code = -32602;
  }
}

/**
 * Verifications de type des arguments.
 *
 * Les schemas declarent `array`, mais rien ne le verifiait : `{"paths":"a.md"}`
 * etait itere caractere par caractere et renvoyait un succes vide --
 * `### a (introuvable)`, `### . (illisible)`, `### m`. L'appelant recevait
 * `isError: false` sur une demande qui n'avait aucun sens.
 */
function exigerTableau(valeur, nom) {
  if (!Array.isArray(valeur)) {
    throw new ErreurProtocole(
      "parametre '" + nom + "' : un tableau est attendu, recu " +
      (valeur === undefined ? "rien" : typeof valeur)
    );
  }
  return valeur;
}

function exigerTexte(valeur, nom) {
  if (typeof valeur !== "string" || !valeur.trim()) {
    throw new ErreurProtocole(
      "parametre '" + nom + "' : une chaine non vide est attendue, recu " +
      (valeur === undefined ? "rien" : typeof valeur)
    );
  }
  return valeur;
}

// ---------------------------------------------------------------------------
// Scripts Python du dépôt
// ---------------------------------------------------------------------------

// Interpreteur retenu au premier succes. Reessayer les deux candidats a
// chaque appel doublait l'attente sur une machine ou seul `python` existe,
// et le second essai n'apprenait rien que le premier n'ait deja etabli.
let pythonRetenu = null;

/**
 * Execute un script Python du depot sans geler la boucle d'evenements.
 *
 * `spawnSync` la gelait : un `ping` emis a t+0,7 s n'etait honore qu'a
 * t+10,8 s, et deux interpreteurs a 300 s chacun pouvaient rendre stdin
 * illisible pendant dix minutes -- bien au-dela du delai apres lequel un
 * client MCP conclut que le serveur est mort.
 *
 * ENOENT est le SEUL motif de passer au candidat suivant : un script qui
 * sort en erreur prouve que l'interpreteur existe. L'ancienne version
 * confondait les deux et annoncait « Python introuvable » alors que Python
 * fonctionnait ; la cause reelle etait dans stderr, que le code jetait.
 */
function runPython(args, timeoutMs = 300000) {
  const { spawn } = require("node:child_process");
  const candidats = pythonRetenu ? [pythonRetenu] : ["python", "python3"];

  return new Promise((resolve, reject) => {
    // Un spawn qui echoue emet `error` PUIS `close` (code -4058 sur Windows).
    // Sans ces deux gardes, le `close` du candidat introuvable rejetait la
    // promesse pendant que le candidat suivant demarrait, et memorisait au
    // passage un interpreteur qui n'existe pas -- verifie, pas suppose.
    let regle = false;
    const rendre = (fn, valeur) => { if (!regle) { regle = true; fn(valeur); } };

    const essayer = (rang) => {
      const commande = candidats[rang];
      let abandonne = false;
      const enfant = spawn(commande, args, {
        // Sans PYTHONIOENCODING, Python ecrit dans la page de codes de la
        // console Windows : les accents des rapports revenaient en mojibake
        // et les filets des tableaux en points d'interrogation.
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        // Une annulation ou une fermeture de stdin doit aussi arreter le
        // script : sinon il continue de lire la passerelle pour personne.
        signal: signalCourant(),
      });

      const sortie = [];
      const erreurs = [];
      let expire = false;
      enfant.stdout.on("data", (c) => sortie.push(c));
      enfant.stderr.on("data", (c) => erreurs.push(c));

      const borne = setTimeout(() => {
        expire = true;
        enfant.kill();
      }, timeoutMs);

      enfant.on("error", (err) => {
        clearTimeout(borne);
        if (err.code === "ENOENT" && rang + 1 < candidats.length) {
          abandonne = true;
          essayer(rang + 1);
          return;
        }
        if (err.code === "ENOENT") {
          rendre(reject, new Error(
            "Python introuvable : aucun de " + candidats.join(", ") +
            " n'existe dans le PATH de ce processus"));
          return;
        }
        rendre(reject, err);
      });

      enfant.on("close", (code) => {
        if (abandonne) return;
        clearTimeout(borne);
        const texte = Buffer.concat(sortie).toString("utf8");
        const detail = Buffer.concat(erreurs).toString("utf8").trim();
        if (expire) {
          rendre(reject, new Error(
            path.basename(args[0]) + " interrompu apres " +
            Math.round(timeoutMs / 1000) + "s"));
          return;
        }
        // L'interpreteur a demarre : inutile de retenter l'autre au prochain
        // appel, meme si le script lui-meme a echoue.
        pythonRetenu = commande;
        if (code === 0 && texte) {
          rendre(resolve, texte);
          return;
        }
        // stderr est remonte : c'est la seule chose qui distingue « le
        // script a plante » de « Python n'est pas installe », et le
        // diagnostic tenait entierement dans ces lignes-la.
        rendre(reject, new Error(
          path.basename(args[0]) +
          (code === 0
            ? " s'est termine sans rien ecrire sur stdout"
            : " a echoue (code " + code + ")") +
          (detail ? " : " + detail.slice(0, 500) : "")));
      });
    };
    essayer(0);
  });
}

async function callTool(name, args) {
  args = args || {};

  // La table des plans est chargee avant tout appel : sans elle, planOf
  // retombe sur le suffixe du nom et peut annoncer un plan faux -- ce qui,
  // sur cette plateforme, est le pire des defauts.
  await chargerPlans();

  if (name === "nexus_ask") {
    if (!args.prompt) throw new ErreurProtocole("parametre 'prompt' requis");

    // Un modele explicite l'emporte sur un profil : demander un modele
    // precis est une decision, la laisser deduire n'en est pas une.
    let model = args.model;
    let note = "";
    let delaiMs;
    // La temperature suit le profil quand il y en a un, et reste au defaut
    // sinon. Un appelant qui en fournit une explicitement l'emporte : le
    // reglage s'adapte, il ne s'impose pas.
    let temperature = args.temperature;
    if (!model && args.profile) {
      const resolved = await resolveProfile(args.profile);
      model = resolved.model;
      if (temperature === undefined) {
        temperature = TEMPERATURE_PROFIL[args.profile];
      }
      // La limite dure du profil devient le delai de l'appel. Sans elle, une
      // tache « rapide » pouvait tenir la ligne dix minutes sur le delai
      // global -- et un appelant qui demande la rapidite doit obtenir un
      // echec franc plutot qu'une attente qui n'en finit pas.
      delaiMs = resolved.spec.latency && resolved.spec.latency.hard_limit_ms;
      note = ` · profil ${args.profile}`;
    }
    model = model || DEFAULT_CHAT_MODEL;

    const messages = [];
    if (args.system) messages.push({ role: "system", content: args.system });
    messages.push({ role: "user", content: args.prompt });
    const result = await chat(model, messages, args.max_tokens || 2048, delaiMs,
                              temperature);

    // Le plan est annonce, pas sous-entendu : ce qui a ete facture et ce
    // qui est sorti de la machine doit se lire sans enquete.
    const coupe = result.tronquee ? " · REPONSE TRONQUEE a max_tokens" : "";
    // La TEMPERATURE employee est journalisee : un reglage qui varie
    // sans etre dit rendrait un resultat inexplicable, ce qui est le
    // seul argument serieux contre l'adaptation automatique.
    const tAff = temperature === undefined ? TEMPERATURE_DEFAUT : temperature;
    return `[${result.model} · ${planOf(result.model)}${note} · T=${tAff} · ${result.tokens} tokens${coupe}]\n\n${result.text}`;
  }

  if (name === "nexus_route") {
    exigerTexte(args.prompt, "prompt");
    const plane = args.plane || "local";
    const router = {
      local: "adaptive-router-local",
      cloud: "adaptive-router-cloud",
      anthropic: "adaptive-router-anthropic",
      all: "adaptive-router",
    }[plane];
    if (!router) throw new Error("plan inconnu : " + plane);
    const messages = [];
    if (args.system) messages.push({ role: "system", content: args.system });
    messages.push({ role: "user", content: args.prompt });
    const result = await chat(router, messages, args.max_tokens || 2048);
    // La facturation se deduit du modele SERVI, pas du plan demande.
    // Deduite du plan, elle annoncait « cout 0 » pour plane:"all", dont le
    // pool contient pourtant des modeles Ollama Cloud.
    const billed = planOf(result.model);
    return `[${router} -> ${result.model} · plan ${plane} · ${result.tokens} tokens · ${billed}]\n\n${result.text}`;
  }

  if (name === "nexus_context") {
    exigerTexte(args.instruction, "instruction");
    if (args.paths !== undefined) exigerTableau(args.paths, "paths");
    const model = args.model || DEFAULT_CHAT_MODEL;
    const contextTokens = args.context_tokens || 32768;

    let corpus = args.text || "";
    const sources = [];
    for (const raw of args.paths || []) {
      const full = resolvePath(raw);
      if (!insideRepo(full)) {
        sources.push(`${raw} (refuse : hors du depot)`);
        continue;
      }
      if (isSecretFile(path.basename(full))) {
        sources.push(`${raw} (refuse : secrets)`);
        continue;
      }
      if (!fs.existsSync(full)) {
        sources.push(`${raw} (introuvable)`);
        continue;
      }
      try {
        const content = fs.readFileSync(full, "utf8");
        corpus += `\n\n===== ${raw} =====\n${content}`;
        sources.push(`${raw} (${Math.round(content.length / 1024)} Ko)`);
      } catch (err) {
        sources.push(`${raw} (illisible)`);
      }
    }
    if (!corpus.trim()) throw new Error("aucun contenu a traiter");

    const approxTokens = Math.round(corpus.length / CHARS_PER_TOKEN);
    const result = await mapReduce(corpus, args.instruction, model, contextTokens,
      (phase, done, total) => log(`${phase} ${done}/${total}`));

    return (
      `[${result.model} · ${planOf(result.model)} · ${result.windows} fenetres, ${result.passes} passes · ` +
      `~${approxTokens} tokens traites en ${contextTokens} de fenetre · ` +
      `${result.tokens} tokens factures 0]\n` +
      (sources.length ? `Sources : ${sources.join(", ")}\n` : "") +
      // Le drapeau n'est pas décoratif : sans lui, une concaténation de
      // fragments serait lue comme une synthèse fusionnée, donc traitée
      // comme fiable et complète alors qu'elle est ni l'un ni l'autre.
      (result.converge === false
        ? "\n[!] Fusion non convergente : ce qui suit est la juxtaposition " +
          "des analyses de fragments, pas une synthese unifiee. Les redites " +
          "et contradictions entre fragments n'ont pas ete arbitrees.\n"
        : "") +
      `\n${result.text}`
    );
  }

  if (name === "nexus_vision") {
    exigerTexte(args.path, "path");
    const full = requireInsideRepo(resolvePath(args.path), "image");
    if (!fs.existsSync(full)) throw new Error("image introuvable : " + args.path);
    const extension = path.extname(full).toLowerCase().replace(".", "") || "png";
    const mime = { jpg: "jpeg", jpeg: "jpeg", png: "png", webp: "webp", gif: "gif" }[extension];
    if (!mime) throw new Error("format non pris en charge : ." + extension);

    // Une image se transmet en base64 dans le corps JSON : son empreinte
    // memoire est environ 1,4 fois sa taille sur disque, cote client comme
    // cote serveur. Au-dela, on refuse plutot que de risquer l'epuisement.
    const taille = fs.statSync(full).size;
    if (taille > MAX_IMAGE_BYTES) {
      throw new Error(
        "image trop volumineuse : " + Math.round(taille / 1048576) + " Mo pour " +
        Math.round(MAX_IMAGE_BYTES / 1048576) + " Mo autorises. La redimensionner."
      );
    }
    const encoded = fs.readFileSync(full).toString("base64");
    const model = args.model || DEFAULT_VISION_MODEL;
    // Seul outil qui appelait requestJson en direct : une coupure de socket
    // perdait donc l'encodage base64 d'une image de plusieurs mega-octets et
    // l'inference deja engagee, la ou tous les autres outils rejouent. Passer
    // par chat() aligne aussi la resolution du modele : derriere un routeur
    // adaptatif, x-litellm-model-group ne rend que le nom du routeur, et
    // annoncer un plan faux est le pire defaut de cette plateforme.
    const messages = [{
      role: "user",
      content: [
        { type: "text", text: args.prompt || "Decris cette image precisement." },
        { type: "image_url", image_url: { url: `data:image/${mime};base64,${encoded}` } },
      ],
    }];
    const result = await chat(model, messages, 1024);
    const kb = Math.round(taille / 1024);
    const coupe = result.tronquee ? " · REPONSE TRONQUEE a max_tokens" : "";
    return `[${result.model} · ${planOf(result.model)} · image ${kb} Ko${coupe}]\n\n${result.text}`;
  }

  if (name === "nexus_summarize") {
    const paths = exigerTableau(args.paths, "paths");
    if (!paths.length) throw new ErreurProtocole("parametre 'paths' : tableau vide");
    const instruction =
      args.instruction || "Fais une synthese technique fidele, structuree et concise.";
    const model = args.model || DEFAULT_CHAT_MODEL;
    const contextTokens = args.context_tokens || 32768;
    const fenetreChars = mapReduceBudgets(contextTokens).window;
    const fusionner = args.fusionner !== false;
    const parts = [];
    const resumes = [];
    let totalTokens = 0;

    for (const raw of paths) {
      const full = resolvePath(raw);
      // Meme interdiction que pour l'index : une synthese remonte vers
      // l'orchestrateur et quitte donc la machine.
      if (!insideRepo(full)) {
        parts.push(`### ${raw}
(refuse : hors du depot)`);
        continue;
      }
      if (isSecretFile(path.basename(full))) {
        parts.push(`### ${raw}\n(refuse : fichier susceptible de contenir des secrets)`);
        continue;
      }
      if (!fs.existsSync(full)) {
        parts.push(`### ${raw}\n(introuvable)`);
        continue;
      }
      let content;
      try {
        content = fs.readFileSync(full, "utf8");
      } catch (err) {
        parts.push(`### ${raw}\n(illisible : ${err.message})`);
        continue;
      }
      // Un fichier plus large que la fenêtre passe par la fusion par
      // paliers au lieu d'être tronqué. La troncature à 24 000 caractères
      // rendait un résumé d'apparence normale à partir des seules
      // premières pages : sur un fichier de 3 000 lignes, elle décrivait
      // le premier tiers et taisait le reste. Un résumé partiel non
      // signalé est plus nuisible qu'une erreur, parce qu'il se lit comme
      // un résumé complet.
      let texte;
      if (content.length > fenetreChars) {
        const decoupe = await mapReduce(content, instruction, model, contextTokens);
        totalTokens += decoupe.tokens;
        texte =
          (decoupe.converge === false
            ? "(fusion non convergente : juxtaposition, pas synthese)\n"
            : `(${decoupe.windows} fenetres fusionnees)\n`) + decoupe.text.trim();
      } else {
        const result = await chat(
          model,
          [
            {
              role: "system",
              content:
                "Tu es un analyste technique. Tu resumes fidelement, sans inventer. " +
                "Si une information est absente, tu le dis.",
            },
            { role: "user", content: `${instruction}\n\n--- ${raw} ---\n${content}` },
          ],
          1024
        );
        totalTokens += result.tokens;
        texte = result.text.trim();
      }
      parts.push(`### ${raw}\n${texte}`);
      resumes.push({ chemin: raw, texte });
    }

    // La fusion annoncée par la description doit exister. Elle ne
    // remplace pas les sections par fichier — les deux servent : la
    // synthèse pour décider, le détail pour vérifier.
    let entete = "";
    if (fusionner && resumes.length > 1) {
      const fusion = await chat(
        model,
        [
          {
            role: "system",
            content:
              "Tu fusionnes des resumes de fichiers d'un meme depot en une synthese " +
              "unique. Degage ce qui relie les fichiers entre eux. N'ajoute aucune " +
              "information absente des resumes fournis.",
          },
          {
            role: "user",
            content:
              `Consigne d'origine : ${instruction}\n\n` +
              resumes.map((r) => `--- ${r.chemin} ---\n${r.texte}`).join("\n\n"),
          },
        ],
        1024
      );
      totalTokens += fusion.tokens;
      entete = `## Synthese fusionnee\n${fusion.text.trim()}\n\n## Par fichier\n\n`;
    }

    return (
      `[${model} · ${planOf(model)} · ${totalTokens} tokens]\n\n` +
      entete +
      parts.join("\n\n")
    );
  }

  if (name === "nexus_index_build") {
    const root = args.root
      ? requireInsideRepo(resolvePath(args.root), "racine d'indexation")
      : WORK_ROOT;
    const index = await buildIndex(root, args.model || DEFAULT_EMBED_MODEL);
    return (
      `Index construit.\n` +
      `  racine  : ${index.root}\n` +
      `  fichiers: ${index.files}\n` +
      `  extraits: ${index.chunks}\n` +
      `  modele  : ${index.model}\n` +
      `  stocke  : ${INDEX_PATH} (local, jamais transmis)`
    );
  }

  if (name === "nexus_search") {
    exigerTexte(args.query, "query");
    // k borne : `k: -1` renvoyait l'index entier moins un extrait, soit
    // plusieurs mega-octets deverses dans le contexte de l'appelant --
    // exactement ce que cet outil existe pour eviter.
    const demande = Number.isFinite(args.k) ? Math.trunc(args.k) : 8;
    const k = Math.min(Math.max(demande, 1), 50);
    const hits = await searchIndex(args.query, k, args.model);
    if (!hits.length) return "Aucun resultat.";
    const blocks = hits.map((hit, i) => {
      const r = hit.record;
      return (
        `--- ${i + 1}. ${r.file}:${r.line}  ` +
        `(score ${hit.score.toFixed(3)} | semantique ${hit.semantic.toFixed(3)} | lexical ${hit.lexical.toFixed(3)})\n` +
        r.text.trim()
      );
    });
    return blocks.join("\n\n");
  }

  if (name === "nexus_batch") {
    const tasks = exigerTableau(args.tasks, "tasks");
    if (!tasks.length) throw new ErreurProtocole("parametre 'tasks' : tableau vide");
    const parts = [];
    let total = 0;
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      if (!task.prompt) {
        parts.push(`### ${i + 1}. (ignoree : aucun prompt)`);
        continue;
      }
      const messages = [];
      if (task.system) messages.push({ role: "system", content: task.system });
      messages.push({ role: "user", content: task.prompt });
      const started = Date.now();
      try {
        const result = await chat(
          task.model || args.model || DEFAULT_CHAT_MODEL,
          messages,
          task.max_tokens || 1024
        );
        total += result.tokens;
        parts.push(
          `### ${i + 1}. ${result.model} — ${((Date.now() - started) / 1000).toFixed(1)}s\n` +
          result.text.trim()
        );
      } catch (err) {
        // Une tache qui echoue ne doit pas emporter le lot : les autres
        // resultats gardent leur valeur.
        parts.push(`### ${i + 1}. echec : ${err.message}`);
      }
    }
    return `[${tasks.length} taches · ${total} tokens]\n\n${parts.join("\n\n")}`;
  }

  if (name === "nexus_compare") {
    exigerTexte(args.prompt, "prompt");
    const models = exigerTableau(args.models, "models");
    if (models.length < 2) throw new ErreurProtocole("parametre 'models' : au moins deux modeles");
    const messages = [];
    if (args.system) messages.push({ role: "system", content: args.system });
    messages.push({ role: "user", content: args.prompt });

    const lignes = [];
    const corps = [];
    for (const model of models) {
      const started = Date.now();
      try {
        const result = await chat(model, messages.slice(), args.max_tokens || 1024);
        const seconds = (Date.now() - started) / 1000;
        lignes.push(`  ${model.padEnd(30)} ${seconds.toFixed(1).padStart(7)}s  ${String(result.tokens).padStart(7)} tokens`);
        corps.push(`### ${model}\n${result.text.trim()}`);
      } catch (err) {
        lignes.push(`  ${model.padEnd(30)} ${"echec".padStart(8)}  ${err.message.slice(0, 60)}`);
        corps.push(`### ${model}\n(echec : ${err.message})`);
      }
    }
    return `Comparaison sur ${models.length} modeles\n\n${lignes.join("\n")}\n\n${corps.join("\n\n")}`;
  }

  if (name === "nexus_profile") {
    return await runPython([path.join(INSTALL_ROOT, "scripts", "nexus_capability.py")]);
  }

  if (name === "nexus_savings") {
    const jours = String(args.jours || 7);
    return await runPython(
      [path.join(INSTALL_ROOT, "scripts", "nexus_savings.py"), "--jours", jours]);
  }

  if (name === "nexus_models") {
    const data = await getJson("/v1/models");
    const ids = (data.data || []).map((d) => d.id).sort();
    // Classer d'apres les litellm_params reels, et non d'apres le suffixe :
    // `releve-locale` etait annonce « facture au token » alors qu'il est
    // local -- l'orchestrateur l'evitait donc pour du confidentiel, ou
    // renoncait au profil coding dont il est le premier candidat.
    const plans = await chargerPlans();
    const groups = { local: [], cloud: [], anthropic: [], routeurs: [] };
    for (const id of ids) {
      const plan = plans && plans.get(id);
      if (plan === "routeur" || id.startsWith("adaptive-router")) groups.routeurs.push(id);
      else if (plan === "local") groups.local.push(id);
      else if (plan === "cloud") groups.cloud.push(id);
      else if (plan === "anthropic") groups.anthropic.push(id);
      else if (id.endsWith("-local")) groups.local.push(id);
      else if (id.endsWith("-cloud")) groups.cloud.push(id);
      else groups.anthropic.push(id);
    }
    return (
      `LOCAL — aucune donnee ne quitte la machine (${groups.local.length})\n  ` +
      groups.local.join("\n  ") +
      `\n\nOLLAMA CLOUD — les donnees sortent vers ollama.com (${groups.cloud.length})\n  ` +
      groups.cloud.join("\n  ") +
      `\n\nANTHROPIC — facture au token sur le compte API, PAS sur l'abonnement (${groups.anthropic.length})\n  ` +
      groups.anthropic.join("\n  ") +
      `\n\nROUTEURS (${groups.routeurs.length})\n  ` +
      groups.routeurs.join("\n  ")
    );
  }

  throw new ErreurProtocole("outil inconnu : " + name);
}

// ---------------------------------------------------------------------------
// Boucle JSON-RPC sur stdio
// ---------------------------------------------------------------------------

function send(message) {
  process.stdout.write(JSON.stringify(message) + "\n");
}

function reply(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function replyError(id, code, message) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

async function handle(message) {
  const { id, method, params } = message;

  if (method === "initialize") {
    const requested = params && params.protocolVersion;
    reply(id, {
      protocolVersion: requested === PROTOCOL_VERSION ? requested : PROTOCOL_VERSION,
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
      instructions:
        "Banc de modeles a trois plans : local (gratuit, prive), Ollama Cloud " +
        "(abonnement Ollama) et Anthropic (credits API, distincts de l'abonnement " +
        "claude.ai). Claude Code garde son abonnement et orchestre. Deleguer le " +
        "volume en local, reduire le contexte via nexus_search et nexus_summarize, " +
        "et ne monter en gamme que lorsque la tache le justifie.",
    });
    return;
  }

  if (method === "notifications/initialized") {
    return; // notification : aucune reponse
  }

  if (method === "notifications/cancelled") {
    // Accepter cette notification puis la jeter -- ce que faisait ce
    // serveur -- laissait l'inference courir jusqu'a son terme sur une
    // passerelle partagee, alors meme que le client avait renonce a la
    // reponse. L'annulation est desormais reelle : le socket est coupe et
    // le script Python eventuel recoit un kill.
    const cible = params && params.requestId;
    const controleur =
      cible === undefined ? undefined : appelsEnCours.get(String(cible));
    if (controleur) {
      log("annulation de l'appel " + cible +
          (params.reason ? " : " + String(params.reason).slice(0, 120) : ""));
      controleur.abort();
    }
    return;
  }

  if (method === "ping") {
    reply(id, {});
    return;
  }

  if (method === "tools/list") {
    reply(id, { tools: TOOLS });
    return;
  }

  if (method === "tools/call") {
    const name = params && params.name;
    const controleur = new AbortController();
    const cle = String(id);
    appelsEnCours.set(cle, controleur);
    try {
      const text = await contexteAppel.run(
        { signal: controleur.signal },
        () => callTool(name, params && params.arguments));
      reply(id, { content: [{ type: "text", text }], isError: false });
    } catch (err) {
      // Une requete annulee ne recoit pas de reponse : le client a deja
      // libere son identifiant, et MCP demande explicitement le silence.
      // Repondre reviendrait a lui apprendre l'echec d'un appel qu'il a
      // lui-meme interrompu.
      if (controleur.signal.aborted) {
        log("appel " + name + " (" + cle + ") interrompu");
        return;
      }
      // Faute de protocole : nom d'outil inexistant, argument absent ou du
      // mauvais type. Elle ne se corrige pas en relisant le message, elle
      // se corrige en changeant l'appel -- d'ou -32602 plutot qu'un
      // resultat marque isError, que le client lit comme un echec du
      // modele et non de l'appelant.
      if (err instanceof ErreurProtocole) {
        replyError(id, err.code, err.message);
        return;
      }
      // Erreur d'execution : elle revient dans le resultat, pas en erreur
      // protocole, pour que le modele puisse la lire et s'adapter.
      reply(id, {
        content: [{ type: "text", text: "Echec de " + name + " : " + err.message }],
        isError: true,
      });
    } finally {
      appelsEnCours.delete(cle);
    }
    return;
  }

  if (id !== undefined && id !== null) {
    replyError(id, -32601, "methode inconnue : " + method);
  }
}

function main() {
  log("demarrage — depot " + WORK_ROOT + " — passerelle " + LITELLM_URL);
  const rl = readline.createInterface({ input: process.stdin, terminal: false });

  // Une inference locale dure parfois plusieurs minutes. Sortir des la
  // fermeture de stdin avorterait les appels en vol et perdrait leur
  // reponse : on attend qu'ils se terminent -- mais pas indefiniment. Le
  // client est parti, donc plus personne ne lira le resultat, tandis que
  // l'inference, elle, continue d'occuper la passerelle partagee. Passe ce
  // delai, un serveur orphelin coute plus qu'il ne rapporte.
  const GRACE_MS = Number(process.env.NEXUS_GRACE_MS || 120000);
  let inFlight = 0;
  let closing = false;

  function maybeExit() {
    if (closing && inFlight === 0) process.exit(0);
  }

  rl.on("line", (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let message;
    try {
      message = JSON.parse(trimmed);
    } catch {
      log("message illisible ignore");
      return;
    }
    inFlight++;
    handle(message)
      .catch((err) => {
        log("erreur interne : " + err.message);
        if (message && message.id !== undefined && message.id !== null) {
          replyError(message.id, -32603, err.message);
        }
      })
      .finally(() => {
        inFlight--;
        maybeExit();
      });
  });

  rl.on("close", () => {
    closing = true;
    maybeExit();
    if (inFlight > 0) {
      log(inFlight + " appel(s) en vol — sortie dans au plus "
          + Math.round(GRACE_MS / 1000) + "s");
      setTimeout(() => {
        log("fermeture forcee : " + inFlight + " appel(s) toujours en vol");
        for (const controleur of appelsEnCours.values()) controleur.abort();
        process.exit(0);
      }, GRACE_MS);
    }
  });
}

main();
