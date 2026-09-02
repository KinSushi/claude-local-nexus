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
// 900 s aligne le pont sur le delai du script nexus_agent.py et sur request_timeout de la passerelle.
// Un pont plus court que la passerelle rend une erreur de delai pour un appel qui aurait abouti, mesure le 2026-08-31 par une instance voisine dont deux appels ont echoue a 600 s.
// La valeur reste surchargeable par NEXUS_TIMEOUT_MS.
const DEFAULT_TIMEOUT_MS = Number(process.env.NEXUS_TIMEOUT_MS || 900000);

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
            // Le texte etait deja reporte ; la raison de l'echec d'analyse
            // ne l'etait pas, et c'est elle qui distingue un corps tronque
            // d'un corps qui n'a jamais ete du JSON.
            reject(new Error("reponse LiteLLM illisible (" +
                             err.message.slice(0, 80) + ") : " +
                             text.slice(0, 200)));
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
            // LA CAUSE VOYAGE AVEC LE REFUS.
            //
            // Ce refus disait « reponse illisible » et rien d'autre : ni
            // ce qui a ete recu, ni pourquoi l'analyse a echoue. Une page
            // d'erreur HTML, un corps vide et un JSON tronque rendaient le
            // meme message, et l'on cherchait au mauvais endroit les trois
            // fois. C'est la classe 1 de nexus_traque -- « la cause de
            // l'echec est perdue » -- ecrite ici en JavaScript.
            reject(new Error("reponse illisible (" + err.message.slice(0, 80) +
                             ") : " + text.slice(0, 200)));
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
  // Un plan inconnu honnete vaut mieux qu'une affirmation de confidentialite
  // non mesuree, et le repli le plus dangereux est celui qui rassure.
  const connu = plansConnus && plansConnus.get(alias);
  if (connu) return LIBELLE_PLAN[connu] || connu;
  if (alias.endsWith("-cloud")) return "Ollama Cloud, les donnees sortent";
  if (alias.startsWith("claude-")) return "Anthropic, facture au token";
  return "plan inconnu";
}

// Concurrence des plans, bornee au niveau du SERVEUR.
//
// `nexus_batch` est sequentiel a dessein, et sa description dit pourquoi :
// deux inferences simultanees se disputent la meme bande passante memoire et
// finissent plus tard que si elles s'etaient suivies. Mais cette discipline
// ne valait qu'A L'INTERIEUR d'un appel : rien n'empechait dix appelants d'en
// lancer dix en parallele. La regle existait en paragraphe, pas en mecanisme.
//
// LES DEUX PLANS SATURENT, mais pas pour la meme raison, et c'est pourquoi
// ils ont deux files et deux bornes :
//
//   local  une memoire partagee. Mesure du 2026-08-30, une dizaine d'appels
//          simultanes : 8 reussites, 14 ECHECS, toutes des expirations a
//          600 s. Ont expire un resume de README.md (15 Ko) et une
//          extraction dite triviale -- ce n'est pas la taille qui decide.
//
//   cloud  un debit partage. Le meme jour, une centaine d'appels simultanes
//          ont fait rendre a la passerelle « Client error '429 Too Many
//          Requests' for url https://ollama.com/api/chat ». A SEPT appels
//          simultanes, le meme plan tenait 7 sur 7 sans un echec, et il est
//          revenu de lui-meme en 6,8 s une fois la charge retiree.
//
// La borne cloud est donc plus haute que la locale, et non absente. Elle
// l'etait, sur la foi de ces sept appels reussis : une generalisation de
// sept a cent cinquante, exactement l'erreur que le contrat corrige en
// §112.3.
//
// DEUX FILES SEPAREES, jamais une seule : un appel cloud qui attendrait
// derriere un appel local paierait la lenteur du local, ce qui annulerait
// l'interet meme d'avoir deux plans.
const CONCURRENCE_LOCALE = Number(process.env.NEXUS_LOCAL_CONCURRENCE || 1);
const CONCURRENCE_CLOUD = Number(process.env.NEXUS_CLOUD_CONCURRENCE || 4);

/**
 * Une mecanique, deux instances. Deux copies finiraient par diverger.
 *
 * Le jeton est PRIS dans le meme tick que le test d'admission, jamais apres
 * un `await`. Le premier jet faisait l'inverse -- il incrementait le compteur
 * apres l'attente -- si bien que deux appels partis dans le meme tick
 * voyaient tous deux zero jeton pris et passaient ensemble. Le semaphore
 * aurait ete inoperant precisement sous la charge qui le motive : mesure a
 * 20 appels simultanes la ou la version corrigee en tient 1.
 *
 * A la liberation, le jeton est TRANSMIS au suivant plutot que rendu puis
 * repris : entre les deux gestes, un appel arrive entre-temps se glisserait
 * devant toute la file.
 */
function creerSemaphore(limite) {
  const file = [];
  let pris = 0;
  return {
    limite: limite,
    get pris() { return pris; },
    get attente() { return file.length; },
    async prendre() {
      // Sortie de secours. Sans elle, une anomalie de comptage bloquerait le
      // pont entier, ce qui serait pire que la contention corrigee.
      if (!(limite > 0)) return;
      if (pris < limite) { pris++; return; }
      await new Promise(function (resoudre) { file.push(resoudre); });
      // Le jeton nous a ete transmis : le compteur reste inchange.
    },
    rendre() {
      if (!(limite > 0)) return;
      const suivant = file.shift();
      if (suivant) suivant();
      else pris = Math.max(0, pris - 1);
    },
  };
}

const semaphoreLocal = creerSemaphore(CONCURRENCE_LOCALE);
const semaphoreCloud = creerSemaphore(CONCURRENCE_CLOUD);

/**
 * Le plan local, et lui seul.
 *
 * `planOf` est la seule source : declarer une seconde table serait s'exposer
 * a ce qu'elles divergent. Un plan INCONNU rend false -- serialiser par
 * defaut ce que l'on ne connait pas ralentirait sur une simple lacune de
 * table, et le cout d'un faux negatif est une contention, jamais une panne.
 */
function estPlanLocal(alias) {
  const libelle = planOf(alias);
  return typeof libelle === "string" && /^local\b/i.test(libelle.trim());
}

/** Le plan cloud, lu au meme endroit et pour la meme raison. */
function estPlanCloud(alias) {
  const libelle = planOf(alias);
  return typeof libelle === "string" && /\bcloud\b/i.test(libelle);
}

/**
 * L'entree unique. Anthropic et le plan inconnu ne sont bornes par personne :
 * le premier est facture au jeton et se limite tout seul par le portefeuille,
 * le second n'est pas assez connu pour qu'on lui impose quoi que ce soit.
 */
async function avecJetonDuPlan(alias, fn) {
  const semaphore = estPlanLocal(alias) ? semaphoreLocal
                  : estPlanCloud(alias) ? semaphoreCloud
                  : null;
  if (!semaphore) return fn();
  await semaphore.prendre();
  try {
    return await fn();
  } finally {
    semaphore.rendre();
  }
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

// Ce qu'il faut DIRE d'une reponse, en un seul endroit.
//
// `sansRaisonnement` rend la chaine vide quand un modele ouvre une balise de
// pensee sans la refermer, et ce choix est juste : livrer le brouillon serait
// pire. Mais le vide etait rendu SANS explication, alors que `chat()` detient
// de quoi la donner. Mesure du 2026-08-30 : nexus_compare a affiche
// « ### glm-5.3-cloud » suivi de rien, a cote de « 50.4s 8234 tokens ».
// L'appelant en a conclu « reponse tronquee » -- la conclusion normale quand
// l'outil sait et se tait. Meme famille que le refus qui ne nommait pas
// --racine : le code detient la raison et ne la dit pas.
//
// La regle vit ici et nulle part ailleurs. Elle etait recopiee dans deux
// appelants et absente des deux autres, ce qui est precisement la facon dont
// deux copies finissent par diverger.
function mentionsReponse(result) {
  const mentions = [];
  // Le libelle est repris MOT POUR MOT. « max_tokens » y est le nom du
  // parametre, non une valeur a substituer : un premier jet l'avait pris pour
  // un gabarit et aurait affiche « a undefined tokens », transformant une
  // mention juste en mention cassee.
  if (result.tronquee) mentions.push("REPONSE TRONQUEE a max_tokens");

  const vide = !result.text || !String(result.text).trim();
  const produits = Number(result.tokens_sortie) || 0;
  if (vide && produits > 0) {
    mentions.push("REPONSE VIDE apres retrait du raisonnement (" +
                  produits + " jetons produits)");
  } else if (vide) {
    // Cas different, et il ne faut pas accuser le retrait du raisonnement
    // d'un vide qu'il n'a pas cause : le modele n'a rien emis du tout.
    mentions.push("REPONSE VIDE : le modele n'a produit aucun jeton");
  }

  return mentions.length ? " · " + mentions.join(" · ") : "";
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

// LE REVEIL EXISTAIT POUR LES EMBEDDINGS, JAMAIS POUR LA GENERATION.
//
// CE QUI ETAIT FAUX. `buildIndex` reveille son modele avant sa boucle depuis
// ce matin, et son commentaire explique pourquoi. Le meme remede n'avait
// jamais ete applique au chemin de GENERATION, qu'empruntent nexus_ask,
// nexus_summarize et nexus_context. Cinquieme fois ce jour qu'une lecon
// existe dans le depot, appliquee d'un cote et pas de l'autre.
//
// CE QUE CELA PRODUISAIT, rapporte par une session voisine :
//     Task failed: Echec de nexus_ask : delai depasse apres 600s
//     Task failed: Echec de nexus_context : delai depasse apres 600s
//     Task failed: Echec de nexus_summarize : delai depasse apres 600s
// Ces 600 secondes sont exactement DEFAULT_TIMEOUT_MS. Un modele local dont
// les poids ne sont pas residents paie leur chargement A L'INTERIEUR du
// budget de l'appel -- et ce chargement peut a lui seul le consommer.
//
// Mesures du 2026-08-31 sur cet hote sans GPU : le modele par defaut demande
// 61,8 s rien que pour COMMENCER a repondre quand il est froid ; une sonde
// entiere a pris 233,8 s a froid contre 60,9 s a chaud ; un appel
// d'embeddings a rendu 408 apres 180,3 s a froid, et 2,90 s a chaud.
//
// L'appel de reveil ECHOUE souvent : la passerelle renonce avant que le
// moteur ait fini. Sans consequence -- le moteur, lui, POURSUIT le
// chargement. C'est le declenchement qui compte, pas la reponse.
//
// L'alias est inscrit AVANT l'appel interne : c'est ce qui arrete la
// recursion, `chat()` appelant cette fonction en tete.
// DEUX drapeaux, et non un seul, parce qu'ils repondent a deux questions
// differentes que l'unique Set confondait :
//   _reveilEnCours    un reveil est-il EN TRAIN de se faire ?  (garde d'auto-appel)
//   _modelesReveilles un reveil a-t-il REUSSI ?                (ne pas refaire)
// L'ancien Set unique servait aux deux, donc marquait « reveille » un modele
// dont le reveil venait d'expirer -- voir reveillerModele().
const _reveilEnCours = new Set();
const _modelesReveilles = new Set();

async function reveillerModele(model, timeoutMs) {
  // Un modele distant n'a pas de poids a charger ici : le reveiller serait
  // une depense sans objet, et sur un plan facture, une depense tout court.
  const plan = planOf(model);
  if (!/^local\b/i.test(plan)) return;
  if (_modelesReveilles.has(model)) return;

  // CE QUI ETAIT FAUX, et mesure chez une session voisine : le drapeau etait
  // pose AVANT la tentative. Un reveil qui EXPIRAIT etait donc enregistre
  // comme reussi, et le modele n'etait plus jamais reveille ensuite.
  // qwen3.6-27b-local a ainsi echoue DEUX FOIS SUR DEUX -- le second appel
  // ne beneficiant d'aucun reveil, precisement parce que le premier avait
  // rate. Un drapeau qui ne peut pas rougir ne mesure rien.
  //
  // Mais ce placement n'etait pas QUE un defaut : chat() appelle cette
  // fonction a sa premiere ligne, donc le `chat` ci-dessous la rappelle
  // aussitot. Le drapeau precoce etait aussi la garde d'auto-appel. La
  // deplacer sans la remplacer aurait produit une recursion infinie -- et
  // memoriser une promesse partagee, un interblocage : l'appel interieur
  // attendrait ce que seul l'appel exterieur peut resoudre.
  // D'ou deux drapeaux : celui-ci garde la recursion et la concurrence,
  // l'autre n'enregistre que le succes.
  if (_reveilEnCours.has(model)) return;
  _reveilEnCours.add(model);

  // LE BUDGET VIENT DE L'APPELANT, et non d'un nombre grave dans le code.
  // Mesure ce jour contre le moteur en direct : qwen3.6:27b demande 31 s a
  // froid et 2 s a chaud ; le releve du depot donne 61,8 s pour
  // glm-4.7-flash. Les 15 s ecrites ici ne chargeaient donc PAS un modele de
  // dix-sept gigaoctets : le reveil expirait a coup sur, sur les modeles
  // memes qu'il existait pour couvrir.
  // Un modele qui ne charge pas dans le budget de l'appelant faisait de
  // toute facon echouer l'appel : il n'y a rien de plus a proteger.
  const budget = Math.max(15000, timeoutMs || 0);
  try {
    await chat(model, [{ role: "user", content: "ping" }], 1, budget);
    _modelesReveilles.add(model);
  } catch (err) {
    // PAS de relance. Le reveil est une optimisation, jamais un prerequis :
    // propager l'erreur ici annulerait l'appel reel que chat() s'apprete a
    // faire, et transformerait un chargement lent en panne franche.
    log("reveil de " + model + " sans reponse (" +
        String(err && err.message).slice(0, 60) + ") — le moteur charge encore");
  } finally {
    _reveilEnCours.delete(model);
  }
}

async function chat(model, messages, maxTokens, timeoutMs, temperature) {
  // Une phase MAP peut durer un quart d'heure : perdre dix fenetres deja
  // calculees pour une coupure de socket serait absurde.
  // Le reveil couvre TOUS les chemins de generation en un seul point --
  // nexus_ask, nexus_summarize, nexus_context, mapReduce et les autres --
  // plutot que trois appels a maintenir separement, qu'un quatrieme outil
  // oublierait le jour de sa creation.
  await reveillerModele(model, timeoutMs);
  const t = temperature === undefined ? TEMPERATURE_DEFAUT : temperature;
  const depart = Date.now();
  // Mesure 2026-08-31: max_tokens=12 rend 523 jetons ; num_predict=12 rend exactement 12 jetons avec finish_reason length ; les deux ensemble rendent 523, donc envoyer max_tokens annule la borne qui fonctionnait.
  // Sans cela toute borne de sortie du pont est inerte et une reprise a budget double ne changerait rien.
  const corps = { model, messages };
  if (String(model).startsWith("claude-")) {
    corps.max_tokens = maxTokens || 2048;
  } else {
    corps.num_predict = maxTokens || 2048;
  }
  // le cache exact est neutralise parce qu un second appel servi par le cache mesure le cache et non le modele
  // le depot l a deja mesure dans scripts/nexus_bench.py
  // une reponse cachee porte le message de troncature de l ANCIEN budget
  corps.cache = { "no-cache": true, "no-store": true };
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
  const { body, headers } = await avecJetonDuPlan(model, () => {
    attenteMs = Date.now() - depart;
    return appelReseau();
  });
  let choice = body.choices && body.choices[0];
  if (!choice) throw new Error("aucune reponse du modele " + model);
  let usage = body.usage || {};
  // Une generation coupee par max_tokens remontait comme une reponse
  // normale : l'appelant recevait un texte tronque sans le savoir, et
  // pouvait conclure sur une phrase interrompue.
  let tronquee = choice.finish_reason === "length";
  // Mesure : sur 78 taches, onze bascules pour onze troncatures, exactement
  // un pour un ; a 2000 jetons trois rendus sur douze tronques, a 4000 zero
  // sur cent quarante-quatre.
  const PLAFOND_REPRISE = 16384;
  if (tronquee) {
    const ancienBudget = corps.num_predict ?? corps.max_tokens;
    const nouveauBudget = Math.min(ancienBudget * 2, PLAFOND_REPRISE);
    // Une reprise avec un budget egal reproduirait le meme appel pour le meme resultat.
    if (nouveauBudget > ancienBudget) {
      log("troncature de " + model + " : reprise unique, max_tokens " + ancienBudget + " -> " + nouveauBudget);
      if (corps.num_predict !== undefined) {
        corps.num_predict = nouveauBudget;
      } else {
        corps.max_tokens = nouveauBudget;
      }
      const retour = await appelReseau();
      const secondBody = retour.body;
      choice = secondBody.choices && secondBody.choices[0];
      if (!choice) throw new Error("aucune reponse du modele " + model);
      usage = secondBody.usage || {};
      tronquee = choice.finish_reason === "length";
    }
  }
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
    // Les jetons de SORTIE a part. `tokens` melange entree et sortie, et
    // d'autres appelants le lisent : annoncer « N jetons produits » avec ce
    // total serait faux, et ce depot ne publie pas de chiffre faux.
    tokens_sortie: sortie,
    tronquee,
    // Le cout reel, tel que la passerelle le calcule. Preferable a une
    // affirmation « cout 0 » deduite du nom du modele.
    cout: Number(headers["x-litellm-response-cost-original"] || 0),
    substitue: resolved !== model,
    demande: model,
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

// UNE FRONTIERE DE DECOUPE NE COUPE PAS UN EMOJI EN DEUX.
//
// DEFAUT SIGNALE le 2026-08-31 par une instance voisine, avec differentiel :
//     corpus AVEC emojis (10 sur 184)  -> HTTP 500 « surrogates not allowed »
//     corpus SANS emoji  (0 sur 106)   -> SUCCES, 470 extraits
// Meme modele, meme appel. La seule variable etait la presence d'emojis.
//
// CAUSE : une chaine JavaScript est stockee en UTF-16, et `slice` coupe en
// UNITES DE CODE, pas en points de code. Un emoji en occupe DEUX. La
// frontiere a CHUNK_CHARS = 1400 tombait entre les deux, laissant une moitie
// HAUTE seule -- qui ne peut pas s'encoder en UTF-8. D'ou la « position
// 1425 » de leur message d'erreur.
//
// CE QUE LE CORRECTIF DOIT AUSSI GARANTIR, et c'est ce qui l'a fait eprouver
// avant d'etre greffe : ne RIEN PERDRE. Un `break` sur cas degenere
// abandonnerait la fin du texte SANS LE DIRE -- et l'erreur d'origine, elle,
// se voyait. Une perte silencieuse serait pire que le defaut.
//
// Eprouve par tools/nexus-mcp/epreuve_decoupage.js, 9 cas, dont l'emoji
// EXACTEMENT a la frontiere, l'emoji en tete, et une rafale de 2000 emojis.
function chunkText(text) {
  let start = 0;
  const chunks = [];

  if (text && text.length > 0) {
    while (true) {
      // calcul de la fin brute
      let end = Math.min(start + CHUNK_CHARS, text.length);

      // eviter de couper une paire de substitution en deux
      if (end > start && end < text.length) {
        const prevCode = text.charCodeAt(end - 1);
        if (prevCode >= 0xD800 && prevCode <= 0xDBFF) {
          // le caractere avant la frontiere est une moitie haute
          // on recule d'une unite si cela ne rend pas le segment vide
          if (end - 1 > start) {
            end -= 1;
          } else {
            // impossible de decouper sans rendre le segment vide -> on sort
            break;
          }
        }
      }

      // si le debut tombe sur une moitie basse, on avance d'une unite
      if (start < text.length) {
        const startCode = text.charCodeAt(start);
        if (startCode >= 0xDC00 && startCode <= 0xDFFF) {
          // on decale le debut pour inclure la moitie haute dans le segment precedent
          start += 1;
          // si le decalage rend start >= end, on ajuste end
          if (start >= end) {
            end = Math.min(start + CHUNK_CHARS, text.length);
          }
        }
      }

      // on ajoute le segment
      chunks.push({ start, text: text.slice(start, end) });

      // fin du texte ?
      if (end >= text.length) break;

      // calcul du prochain debut avec recouvrement
      let nextStart = end - CHUNK_OVERLAP;

      // eviter que le recouvrement commence sur une moitie basse
      if (nextStart > start && nextStart < text.length) {
        const nextCode = text.charCodeAt(nextStart);
        if (nextCode >= 0xDC00 && nextCode <= 0xDFFF) {
          // on avance d'une unite pour commencer sur la moitie haute
          nextStart += 1;
        }
      }

      // garantir progression stricte
      if (nextStart <= start) {
        // fallback pour eviter boucle infinie
        nextStart = start + 1;
      }

      start = nextStart;
    }
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
        // LE CHEMIN S'ANCRE SUR LA RACINE DU DEPOT, PAS SUR CELLE DE
        // L'INDEXATION. Relatif a `root`, « src/host/broker.py » indexe
        // depuis src/host devient « broker.py » -- indiscernable d'un
        // « broker.py » de src/compute. Fusionner deux tranches creerait
        // alors des collisions muettes. Ancre sur le depot, chaque chemin
        // est unique par construction, et il reste lisible a l'affichage.
        file: path.relative(WORK_ROOT, file).replace(/\\/g, "/"),
        line: lineOf(content, chunk.start),
        text: chunk.text,
        tokens: tokenize(chunk.text),
      });
      pending.push(chunk.text);
    }
  }

  // LE MODELE EST REVEILLE AVANT D'ETRE MESURE — ET C'EST LE VRAI REMEDE.
  //
  // CE QUI EST MESURE, le 2026-08-31, trois passes du MEME appel : 32
  // extraits vers `all-minilm-local`, le plus leger des modeles declares.
  //
  //     passe 1, modele FROID   HTTP 408    180,3 s   coupe par la passerelle
  //     passe 2, modele CHAUD   HTTP 200      2,90 s
  //     passe 3, modele CHAUD   HTTP 200      0,26 s
  //
  // Le cout reel d'un lot de 32 est de TROIS SECONDES. Ce qui depasse le
  // `request_timeout: 180` de LiteLLM est le CHARGEMENT DES POIDS, paye une
  // seule fois. C'est exactement l'erreur que le contrat documente en
  // 112.3 -- une lecture en une seule phase attribue le chargement au
  // travail, definitivement -- et un premier jet de ce correctif l'a
  // recommise : il rapetissait le lot de 32 a 16 sur une lecture de 127 s
  // contaminee par un chargement partiel. Rapetisser ne sert a RIEN : un
  // lot de UN expirerait identiquement sur un modele froid.
  //
  // Le remede est celui que `nexus_bench.py` applique deja pour le debit :
  // reveiller d'abord, sur un budget separe, pour que le chargement ne soit
  // impute a personne. L'appel de reveil ECHOUE souvent -- la passerelle
  // rend 408 avant qu'Ollama ait fini -- mais Ollama, lui, POURSUIT le
  // chargement. Son echec est donc attendu et sans consequence : c'est le
  // declenchement qui compte, pas la reponse.
  //
  // C'est aussi la cause de l'echec rapporte par une session voisine --
  // « litellm.Timeout: Timeout passed=180, time taken=179.996 » -- qui
  // mettait `nexus_search` hors service alors que rien n'etait casse.
  const vectors = [];
  const BATCH = (() => {
    const brut = Number(process.env.NEXUS_EMBED_BATCH);
    return Number.isInteger(brut) && brut > 0 ? brut : 32;
  })();

  if (pending.length) {
    for (let essai = 1; essai <= 3; essai++) {
      try {
        await embed(embedModel, [pending[0]]);
        if (essai > 1) log("modele d'embedding reveille apres " + essai + " essai(s)");
        break;
      } catch (err) {
        // Un reveil qui echoue n'est pas une panne : la passerelle a
        // renonce, le moteur charge encore. On le DIT plutot que de le
        // taire, pour que trois echecs de suite restent lisibles.
        log("reveil " + essai + "/3 du modele d'embedding : " +
            String(err && err.message).slice(0, 80));
      }
    }
  }

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

  // L'INDEX FUSIONNE, IL N'ECRASE PLUS.
  //
  // CE QUI ETAIT FAUX, signale par une session voisine le 2026-08-31 :
  // indexer `src/host` puis `src/compute` faisait DISPARAITRE src/host.
  // L'objet index etait reconstruit de zero a chaque appel, si bien qu'un
  // arbre trop large pour un seul passage ne pouvait pas etre couvert par
  // tranches -- et rien ne le disait. La recherche rendait simplement zero
  // resultat sur ce qui avait ete indexe trois minutes plus tot.
  //
  // DEUX GARDES, et elles ne sont pas facultatives :
  //
  //   * MODELE. Des vecteurs produits par deux modeles differents ne
  //     vivent pas dans le meme espace : leurs dimensions different, et
  //     meme a dimension egale leurs distances n'ont aucun sens commun.
  //     Les fusionner rendrait des scores calcules sur du vide. On
  //     REMPLACE alors, et on le DIT.
  //   * FORMAT. Un index anterieur porte des chemins relatifs a sa racine
  //     d'indexation, pas au depot. Les melanger produirait exactement les
  //     collisions que le correctif ci-dessus supprime. Un index sans
  //     `version` est donc remplace, et on le dit aussi.
  //
  // Reindexer la MEME racine remplace ses extraits plutot que de les
  // dupliquer : sans cela, chaque passe doublerait le poids de l'index et
  // la recherche rendrait le meme extrait plusieurs fois.
  const VERSION_INDEX = 2;
  const prefixe = path.relative(WORK_ROOT, root).replace(/\\/g, "/");
  // Le nombre d'extraits PERDUS par un remplacement. Compte AVANT que
  // `anciens` ne soit vide : compter apres donnerait toujours zero, un
  // chiffre FAUX plutot qu'une absence de chiffre.
  let perdus = 0;
  let anciens = [];
  let racines = [];
  let motifRemplacement = null;
  try {
  if (fs.existsSync(INDEX_PATH)) {
    const precedent = JSON.parse(fs.readFileSync(INDEX_PATH, "utf8"));
    const recordsArray = Array.isArray(precedent.records) ? precedent.records : null;

    if (precedent.version !== VERSION_INDEX) {
      // format anterieur : les chemins ne sont pas ancrés au depot
      motifRemplacement = "format anterieur (chemins non ancres au depot)";
      perdus = recordsArray ? recordsArray.length : 0;   // cas 2
    } else if (precedent.model !== embedModel) {
      // modele different : vecteurs non comparables
      motifRemplacement = "modele different (" + precedent.model +
        " -> " + embedModel + ") : vecteurs non comparables";
      perdus = recordsArray ? recordsArray.length : 0;   // cas 2
    } else if (recordsArray) {
      // fusion : on conserve les enregistrements qui ne correspondent pas au prefixe
      anciens = precedent.records.filter((r) =>
        !(prefixe === "" || r.file === prefixe || r.file.startsWith(prefixe + "/")));
      racines = Array.isArray(precedent.roots) ? precedent.roots.slice() : [];
      // perdus reste a 0 car aucun remplacement n'est effectue
    }
  }
  } catch (err) {
  // index precedent illisible : on ne peut pas connaitre le nombre d'extraits perdus
  motifRemplacement = "index precedent illisible (" +
    String(err && err.message).slice(0, 60) + "), nombre d'extraits perdus inconnu";
  // perdus reste a 0 (cas 3)
  }
  if (motifRemplacement) {
    log("index REMPLACE et non fusionne — " + motifRemplacement);
  } else if (anciens.length) {
    log("index fusionne : " + anciens.length + " extrait(s) conserve(s) hors " +
        (prefixe || "racine du depot"));
  }
  if (!racines.includes(prefixe)) racines.push(prefixe);

  const tous = anciens.concat(records);
  const index = {
    version: VERSION_INDEX,
    root,
    roots: racines,
    model: embedModel,
    built: new Date().toISOString(),
    files: files.length,
    chunks: tous.length,
    chunks_ajoutes: records.length,
    // CE QUI ETAIT FAUX : le motif de remplacement partait dans `log()`,
    // donc sur stderr, invisible a l'appelant MCP. Il lisait « Index
    // construit » sans savoir qu'il venait de perdre son corpus
    // precedent. Une perte silencieuse est pire que le defaut d'origine :
    // une erreur, elle, se voit.
    remplacement: motifRemplacement,
    extraits_perdus: motifRemplacement ? perdus : 0,
    records: tous,
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


// Adresse du moteur Ollama, surchargeable via la variable d'environnement.
// Valeur par défaut : http://127.0.0.1:11434
const OLLAMA_URL = process.env.NEXUS_OLLAMA_URL || 'http://127.0.0.1:11434';

/**
 * Interroge Ollama sur /api/ps et renvoie la liste des noms de modèles chargés.
 * Aucun rejet n'est propagé ; tout échec est journalisé et une liste vide est
 * retournée. Le délai maximal est de 5 secondes.
 *
 * @returns {Promise<string[]>}
 */
async function modelesResidents() {
  return new Promise((resolve) => {
    const url = new URL('/api/ps', OLLAMA_URL);
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname + url.search,
      method: 'GET',
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        try {
          const body = Buffer.concat(chunks).toString('utf8');
          const data = JSON.parse(body);
          const models = Array.isArray(data.models)
            ? data.models.map((m) => (typeof m === 'object' && m.name ? m.name : String(m)))
            : [];
          resolve(models);
        } catch (err) {
          console.error('Erreur de parsing de la réponse Ollama :', err.message);
          resolve([]);
        }
      });
    });

    req.on('error', (err) => {
      console.error('Echec de la requête Ollama :', err.message);
      resolve([]);
    });

    req.on('timeout', () => {
      req.destroy();
      console.error('Timeout (5 s) lors de l\'appel à Ollama /api/ps');
      resolve([]);
    });

    req.end();
  });
}

// fonction qui récupère la taille (en octets) de chaque modèle
async function poidsDesModeles() {
  return new Promise((resolve) => {
    const url = new URL('/api/tags', OLLAMA_URL);
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname + url.search,
      method: 'GET',
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        try {
          const body = Buffer.concat(chunks).toString('utf8');
          const data = JSON.parse(body);
          const map = new Map();
          if (Array.isArray(data.models)) {
            data.models.forEach((m) => {
              if (m && typeof m.name === 'string' && typeof m.size === 'number') {
                map.set(m.name, m.size);
              }
            });
          }
          resolve(map);
        } catch (err) {
          console.error('Erreur de parsing de la réponse Ollama tags :', err.message);
          resolve(new Map());
        }
      });
    });

    req.on('error', (err) => {
      console.error('Echec de la requête Ollama tags :', err.message);
      resolve(new Map());
    });

    req.on('timeout', () => {
      req.destroy();
      console.error('Timeout (5 s) lors de l\'appel à Ollama /api/tags');
      resolve(new Map());
    });

    req.end();
  });
}


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

async function exigerAliasConnu(model) {
  // un refus en zero seconde qui nomme la voie vaut mieux qu'un aller-retour qui ne propose rien

  // 1. absence ou vide : on ne bloque pas
  if (!model) {
    return;
  }

  // 2. inventaire des alias exposes
  const ensemble = await exposedModels();

  // 3. inventaire vide : symptome reseau, pas preuve d'invalidite
  if (ensemble.size === 0) {
    return;
  }

  // 4. alias connu : on laisse passer
  if (ensemble.has(model)) {
    return;
  }

  // 5. calcul local de la distance de Levenshtein, insensible a la casse
  function distanceLevenshtein(a, b) {
    const aa = a.toLowerCase();
    const bb = b.toLowerCase();
    if (aa === bb) {
      return 0;
    }
    const m = aa.length;
    const n = bb.length;
    if (m === 0) {
      return n;
    }
    if (n === 0) {
      return m;
    }
    let lignePrecedente = new Array(n + 1);
    for (let j = 0; j <= n; j++) {
      lignePrecedente[j] = j;
    }
    let ligneCourante = new Array(n + 1);
    for (let i = 1; i <= m; i++) {
      ligneCourante[0] = i;
      const ca = aa.charCodeAt(i - 1);
      for (let j = 1; j <= n; j++) {
        const cout = ca === bb.charCodeAt(j - 1) ? 0 : 1;
        ligneCourante[j] = Math.min(
          ligneCourante[j - 1] + 1,
          lignePrecedente[j] + 1,
          lignePrecedente[j - 1] + cout
        );
      }
      [lignePrecedente, ligneCourante] = [ligneCourante, lignePrecedente];
    }
    return lignePrecedente[n];
  }

  const proches = [...ensemble]
    .map(alias => ({ alias, distance: distanceLevenshtein(model, alias) }))
    .sort((a, b) => a.distance - b.distance || a.alias.localeCompare(b.alias))
    .slice(0, 5)
    .map(p => p.alias)
    .join(', ');

  throw new Error(`alias refuse : ${model} ; proches : ${proches}`);
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
  let tronquee = false;

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
      tronquee = tronquee || result.tronquee;
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
    return { text: "Le modele n'a rien rendu : ce n'est pas un verdict sur le contenu. Augmenter le budget de sortie ou changer de modele.", windows: windows.length,
             passes: 1, tokens, model, converge: true, tronquee };
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
      tronquee = tronquee || result.tronquee;
      next.push((result.text || "").trim());
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

  return { text: level[0], windows: windows.length, passes, tokens, model, converge, tronquee };
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
        paths: {
          type: "array",
          items: { type: "string" },
          description: "Fichiers a joindre au prompt, relatifs a la racine du depot ou absolus. Le contenu est ajoute au message avec le nom du fichier en tete. Les fichiers susceptibles de contenir des secrets sont exclus par le meme filtre que nexus_summarize et nexus_context."
        },
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
    name: "nexus_charge",
    title: "Rapporter qui occupe la machine",
    description: "Liste les processus significatifs AVEC LE PROJET auquel ils appartiennent, la memoire libre et la memoire disponible pour l inference, et qu elle sert a savoir si la machine peut accueillir un travail local avant de le lancer.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "nexus_livres",
    title: "Chercher dans les 24 livres par sens, en local",
    description:
      "Recherche semantique dans 20 304 fragments de 24 ouvrages techniques, " +
      "dont 7 sur les agents IA. L'index est local (nomic-embed-text), rien ne " +
      "quitte la machine, le cout est nul. Rend le chapitre ET le code source " +
      "quand il existe : une recherche qui ne rend que de la prose fait reecrire, " +
      "une recherche qui rend du code fait adapter.",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "La question, en langage naturel." },
      },
      required: ["question"],
    },
  },
  {
    name: "nexus_verrou",
    title: "Rapporter l etat des verrous de machine partages entre projets",
    description: "Ces verrous sont des mutex nommes, ils servent a eviter que deux projets lancent en meme temps une inference locale ou une copie massive, et cet outil CONSTATE l etat sans prendre ni liberer aucun verrou.",
    inputSchema: { type: "object", properties: {} },
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

/**
 * Le garde était présenté à tort comme une barrière d'exfiltration.
 * En réalité WORK_ROOT est déclaré par le client ; le garde ne fait que
 * borner l'espace que le pont accepte de toucher (rayon d'action) et ne
 * prétend pas empêcher une fuite que l'appelant pourrait provoquer lui‑même.
 * Le message indique la limite actuelle et invite à déclarer une autre racine
 * si l'appelant en a le droit.
 */
function requireInsideRepo(target, quoi) {
  if (!insideRepo(target)) {
    throw new Error(
      quoi + ' hors du depot refuse : ' + target + '. ' +
      'Le pont ne lit que sous ' + WORK_ROOT + ' ; ' +
      'déclarez une autre racine si vous avez le droit.'
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

function exigerTableauNonVide(valeur, nom, minimum, quoi) {
  // Nommer L'ISSUE, pas seulement le symptome. Mesure du 2026-08-30 sur
  // 32 cas de protocole : douze refus nommaient le parametre fautif sans
  // jamais dire ce qu'il fallait fournir. « tableau vide » decrit ; « au
  // moins 1 chemin de fichier attendu » indique par ou passer.
  //
  // Le bon exemple existait deja dans ce fichier, chez nexus_compare : la
  // regle est ici centralisee pour qu'il n'en subsiste aucune copie.
  const tableau = exigerTableau(valeur, nom);
  const seuil = minimum === undefined ? 1 : minimum;
  if (tableau.length < seuil) {
    throw new ErreurProtocole(
      "parametre '" + nom + "' : au moins " + seuil + " " + quoi +
      " attendu, recu " + tableau.length
    );
  }
  return tableau;
}

function exigerEntierPositif(valeur, nom) {
  // `undefined` passe : le parametre est optionnel et un defaut s'applique.
  if (valeur === undefined || valeur === null) return valeur;
  if (!Number.isInteger(valeur) || valeur <= 0) {
    // La VALEUR est montree quand c'est un nombre, jamais son type seul :
    // « recu number » ne dit pas a l'appelant que son -1 est le fautif.
    const recu = typeof valeur === "number" ? String(valeur) : typeof valeur;
    throw new ErreurProtocole(
      "parametre '" + nom + "' : un entier strictement positif est attendu, recu " + recu
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

  // Ces huit outils engagent une inference lourde et doivent etre serialises entre depots,
  // le cout mesure d'une eviction de poids etant de 177 secondes pour 20 Go,
  // tandis que les outils de simple consultation ne doivent pas etre serialises.
  const OUTILS_LOURDS = new Set([
    'nexus_ask',
    'nexus_route',
    'nexus_context',
    'nexus_vision',
    'nexus_summarize',
    'nexus_batch',
    'nexus_compare',
    'nexus_index_build',
    'nexus_search'
  ]);

  async function callToolInterne(name, args) {
    args = args || {};

  // La table des plans est chargee avant tout appel : sans elle, planOf
  // retombe sur le suffixe du nom et peut annoncer un plan faux -- ce qui,
  // sur cette plateforme, est le pire des defauts.
  await chargerPlans();

  if (name === "nexus_ask") {
    // `!args.prompt` laissait passer une chaine d'espaces, et laissait passer
    // un NOMBRE -- la negation d'un nombre non nul etant fausse. Le refus
    // ecrit a la main etait donc moins clair ET moins correct que le helper
    // que tous les autres outils emploient.
    exigerTexte(args.prompt, "prompt");
    exigerEntierPositif(args.max_tokens, "max_tokens");

    // Consommation du parametre optionnel paths : joindre le contenu des
    // fichiers au prompt, avec leur nom en tete. Le filtre de confidentialite
    // est le meme que celui de nexus_summarize et nexus_context.
    let contenuFichiers = "";
    if (args.paths !== undefined) {
      exigerTableau(args.paths, "paths");
      for (const raw of args.paths) {
        const full = requireInsideRepo(resolvePath(raw), "fichier");
        if (isSecretFile(path.basename(full))) continue;
        if (!fs.existsSync(full)) throw new Error("fichier introuvable : " + raw);
        const content = fs.readFileSync(full, "utf8");
        contenuFichiers += `\n\n===== ${raw} =====\n${content}`;
      }
    }

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
    // Un alias inconnu doit echouer ici, en zero seconde et en proposant les plus proches, plutot qu'au serveur apres un aller-retour
    await exigerAliasConnu(model);

    const messages = [];
    if (args.system) messages.push({ role: "system", content: args.system });
    messages.push({ role: "user", content: args.prompt + (contenuFichiers ? "\n\n" + contenuFichiers : "") });
    const result = await chat(model, messages, args.max_tokens || 2048, delaiMs,
                              temperature);

    // Le plan est annonce, pas sous-entendu : ce qui a ete facture et ce
    // qui est sorti de la machine doit se lire sans enquete.
    const coupe = mentionsReponse(result);
    // La TEMPERATURE employee est journalisee : un reglage qui varie
    // sans etre dit rendrait un resultat inexplicable, ce qui est le
    // seul argument serieux contre l'adaptation automatique.
    const tAff = temperature === undefined ? TEMPERATURE_DEFAUT : temperature;
    return `[${result.model} · ${planOf(result.model)}${note} · T=${tAff} · ${result.tokens} tokens${coupe}]\n\n${result.text}`;
  }

  if (name === "nexus_route") {
    exigerTexte(args.prompt, "prompt");
    exigerEntierPositif(args.max_tokens, "max_tokens");
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
    return `[${router} -> ${result.model} · plan ${plane} · ${result.tokens} tokens · ${billed}${mentionsReponse(result)}]\n\n${result.text}`;
  }

  if (name === "nexus_context") {
    // Ce qui était faux : le paramètre mal orthographié 'files' était simplement ignoré parce que seul "paths" était testé.
    // Le script continuait alors avec un tableau vide et ne signalait aucune source de contenu, masquant l’erreur de l’appelant.
    exigerTexte(args.instruction, "instruction");
    if (args.paths !== undefined) exigerTableau(args.paths, "paths");
    if (
        (args.paths === undefined || args.paths.length === 0) &&
        (args.text === undefined || args.text.length === 0)
    ) {
        const recus = Object.keys(args).filter(k => args[k] !== undefined).join(', ');
        throw new ErreurProtocole(`Parametres acceptes: paths, text. Parametres recus: ${recus}`);
    }
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
        // « illisible » ne distinguait pas un droit refuse, un encodage
        // fautif et un fichier disparu. Trois remedes differents, un seul
        // mot, et rien dans le rapport pour choisir.
        sources.push(`${raw} (illisible : ${String(err.message).slice(0, 60)})`);
      }
    }
    // CE QUI ETAIT FAUX : le throw ne transmettait pas les raisons, ne distinguait pas le cas d'absence de chemins, et masquait le nombre de fichiers examinés.
    // Il ne renvoyait que le message générique 'aucun contenu a traiter'.

    if (!corpus.trim()) {
        const totalExamines = sources.length;
        let errorMsg;
        if (sources.length === 0) {
            errorMsg = 'Aucun chemin fourni.';
        } else {
            const limit = 10;
            const displayed = sources.slice(0, limit).join('; ');
            const omitted = sources.length - limit;
            const suffix = omitted > 0 ? ` ... et ${omitted} autres` : '';
            errorMsg = `${totalExamines} chemin(s) examine(s) : ${displayed}${suffix}`;
        }
        throw new Error(errorMsg);
    }

    const approxTokens = Math.round(corpus.length / CHARS_PER_TOKEN);
    const result = await mapReduce(corpus, args.instruction, model, contextTokens,
      (phase, done, total) => log(`${phase} ${done}/${total}`));

    return (
      `[${result.model} · ${planOf(result.model)} · ${result.windows} fenetres, ${result.passes} passes · ` +
      `~${approxTokens} tokens soumis (${corpus.length} car.) en ${contextTokens} de fenetre · ` +
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
    const coupe = mentionsReponse(result);
    return `[${result.model} · ${planOf(result.model)} · image ${kb} Ko${coupe}]\n\n${result.text}`;
  }

  if (name === "nexus_summarize") {
    const paths = exigerTableauNonVide(args.paths, "paths", 1, "chemin de fichier");
    const instruction =
      args.instruction || "Fais une synthese technique fidele, structuree et concise.";
    const model = args.model || DEFAULT_CHAT_MODEL;
    const contextTokens = args.context_tokens || 32768;
    const fenetreChars = mapReduceBudgets(contextTokens).window;
    const fusionner = args.fusionner !== false;
    const parts = [];
    const resumes = [];
    let totalTokens = 0;
    // compte les resumes coupes a max_tokens, sinon la banniere serait morte
    let tronquees = 0;

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
                (paths.length > 1
                  ? // TU NE VOIS QU'UN FICHIER SUR PLUSIEURS, ET TU DOIS LE SAVOIR.
                    //
                    // CE QUI ETAIT FAUX, et c'est la cause AMONT de tout le reste.
                    // Chaque fichier est resume separement, mais recevait la consigne
                    // ENTIERE avec l'ordre « si une information est absente, tu le
                    // dis ». Un modele qui ne voit que le fichier B declarait donc
                    // ABSENT tout ce que demandait la consigne au sujet de A -- une
                    // affirmation fausse, produite avec assurance.
                    //
                    // Mesure d'une session voisine, 2026-08-31, deux fichiers et
                    // quatre points demandes : le resume de A citait parfaitement
                    // les trois points de A et declarait le quatrieme « absent » ;
                    // le resume de B faisait l'inverse. La fusion, batie sur ces
                    // resumes, heritait des faux « absent » -- d'ou une synthese
                    // qui declarait un fichier « not provided » alors qu'il avait
                    // ete lu et correctement resume juste a cote.
                    //
                    // Consequence reelle et couteuse : le modele composait une
                    // integration a partir d'une moitie et INVENTAIT l'autre. Un
                    // rendu appelait ainsi estimate_gguf_vram_mb(params_billions,
                    // bits_per_weight), deux parametres qui n'existent pas.
                    //
                    // Le remede n'est pas de tout donner a chacun -- ce serait
                    // renoncer au decoupage qui fait tenir le contexte -- mais de
                    // DIRE a chacun ce qu'il ne voit pas, et de lui interdire de
                    // conclure sur ce qu'il n'a pas.
                    "TU NE VOIS QU'UN SEUL FICHIER, parmi " + paths.length +
                    " qui sont traites separement. Reponds UNIQUEMENT sur le " +
                    "fichier ci-dessous. Ne declare RIEN absent ou manquant : ce " +
                    "que la consigne demande et que tu ne trouves pas ici se " +
                    "trouve tres probablement dans un autre fichier que tu n'as " +
                    "pas. Sur ces points-la, tais-toi plutot que de conclure."
                  : "Si une information est absente, tu le dis."),
            },
            { role: "user", content: `${instruction}\n\n--- ${raw} ---\n${content}` },
          ],
          1024
        );
        totalTokens += result.tokens;
        if (result.tronquee) tronquees++;
        texte = result.text.trim();
      }
      parts.push(`### ${raw}\n${texte}`);
      resumes.push({ chemin: raw, texte });
    }

    // La fusion annoncée par la description doit exister. Elle ne
    // remplace pas les sections par fichier — les deux servent : la
    // synthèse pour décider, le détail pour vérifier.
    // L'ETAGE DE FUSION NE VOIT PAS LES FICHIERS, ET DOIT LE SAVOIR.
    //
    // CE QUI EST MESURE ICI, le 2026-08-31, sur deux fichiers de ce depot.
    // Consigne : recopier litteralement la ligne 60 de chaque fichier. Les
    // rendus PAR FICHIER etaient exacts. La fusion, qui ne recoit que ces
    // deux resumes d'une ligne, a rendu des paragraphes d'INFERENCE absents
    // de ses entrees : « indiquant qu'il utilise le module JSON pour
    // manipuler des donnees structurees », « semblent etre lies a la gestion
    // ou au suivi de donnees ». De la fabrication, sous le titre
    // « Synthese », et placee AU-DESSUS du detail exact.
    //
    // La cause est structurelle : on passait « Consigne d'origine :
    // <instruction> » a un modele qui n'a pas les fichiers. Somme de repondre
    // a une question dont il n'a pas la matiere, il compose.
    //
    // CE QUI N'EST PAS ETABLI, et qu'il ne faut pas ecrire ici comme s'il
    // l'etait. Une session voisine a d'abord rapporte que la fusion livrait
    // du contenu VIDE, puis a RETRACTE la cause : sa consigne portait une
    // clause d'echappement (« si le fichier arrive vide, ecris VIDE et
    // arrete-toi »), et une clause d'echappement est plus facile a satisfaire
    // qu'une tache -- d'autant plus que la consigne s'allonge. Reste un fait
    // sans explication : sous fusionner:true, deux familles ont declare les
    // fichiers vides la ou fusionner:false rendait leur contenu.
    //
    // Les trois correctifs ci-dessous se justifient par la mesure de CE
    // depot, pas par le rapport retracte. Ils reduisent aussi, sans le
    // prouver, la surface du fait inexplique : un modele a qui l'on dit
    // explicitement qu'il n'a pas les fichiers n'a plus de raison de
    // declarer qu'ils sont vides.
    //   1. la consigne d'origine devient du CONTEXTE, jamais une tache a
    //      refaire, et le systeme dit qu'il ne recoit que des resumes ;
    //   2. le detail par fichier passe AVANT la synthese : une synthese
    //      fausse placee en tete prime sur un detail juste, et c'est la
    //      premiere ligne qu'un lecteur retient ;
    //   3. sous un seuil de matiere, on ne fusionne PAS. Deux resumes d'une
    //      ligne n'ont rien a synthetiser ; les fusionner ne produit que de
    //      la surface d'invention.
    let entete = "";
    const matiere = resumes.map((r) => r.texte || "").join("\n").trim();
    const ASSEZ_DE_MATIERE = 400;
    if (fusionner && resumes.length > 1 && matiere.length >= ASSEZ_DE_MATIERE) {
      const fusion = await chat(
        model,
        [
          {
            role: "system",
            content:
              // INTERDIRE D'INVENTER N'EST PAS INTERDIRE DE SYNTHETISER.
              //
              // Le premier jet de ce correctif serrait si fort contre la
              // fabrication qu'il supprimait la raison d'etre de l'etage :
              // « degage ce qui relie les fichiers entre eux ». Mesure du
              // 2026-08-31, sur deux resumes substantiels : la « synthese »
              // rendue etait une RECONCATENATION quasi mot pour mot des deux
              // resumes, ~7000 jetons pour redire ce qui figurait juste
              // au-dessus. Sur du redondant, c'est du gaspillage ; le lecteur
              // apprend a sauter la section, et le jour ou elle dit quelque
              // chose, il la saute aussi.
              //
              // La distinction juste n'est pas « ne rien ajouter » mais
              // « n'ajouter aucun FAIT ». Rapprocher, opposer, nommer une
              // dependance ou une tension entre deux resumes ne fabrique
              // rien : c'est un travail sur ce qui est deja la, et c'est
              // exactement ce qu'on lui demande.
              "Tu recois des RESUMES de fichiers, jamais les fichiers eux-memes. " +
              "Ton travail est de les RELIER : ce qu'ils ont en commun, ce qui " +
              "les oppose, ce que l'un suppose de l'autre. Ne recopie pas les " +
              "resumes -- ils sont deja affiches au-dessus de toi, les repeter " +
              "ne sert a rien. " +
              "N'affirme aucun FAIT qui ne soit pas dans les resumes fournis : " +
              "pas de detail technique devine, pas de nom de fonction ou de " +
              "champ que tu n'as pas lu. Rapprocher deux resumes n'est pas " +
              "inventer ; ajouter un fait absent, si. " +
              "Si les resumes n'ont aucun rapport entre eux, dis-le en une " +
              "phrase et arrete-toi. " +
              "Ne declare jamais qu'un fichier est vide ou absent : tu n'as pas " +
              "les fichiers, seulement des resumes.",
          },
          {
            role: "user",
            content:
              `Les resumes ci-dessous ont ete produits pour la consigne suivante, ` +
              `donnee pour CONTEXTE seulement. N'essaie pas d'y repondre toi-meme : ` +
              `tu n'as pas les fichiers, seulement ces resumes.\n${instruction}\n\n` +
              resumes.map((r) => `--- ${r.chemin} ---\n${r.texte}`).join("\n\n"),
          },
        ],
        1024
      );
      totalTokens += fusion.tokens;
      if (fusion.tronquee) tronquees++;
      entete =
        `\n\n## Synthese des resumes ci-dessus\n` +
        `(produite a partir des RESUMES, jamais des fichiers)\n` +
        fusion.text.trim();
    } else if (fusionner && resumes.length > 1) {
      // Le silence se lirait comme une fusion reussie. On dit pourquoi il
      // n'y en a pas, et avec quel chiffre.
      entete =
        `\n\n## Pas de synthese\n` +
        `Les resumes tiennent en ${matiere.length} caracteres, sous le seuil de ` +
        `${ASSEZ_DE_MATIERE} : il n'y a rien a synthetiser, et fusionner si peu ` +
        `ne produirait que de l'invention.`;
    }

    const refusSecret = parts
      .filter(p => p.includes("(refuse : fichier susceptible de contenir des secrets)"))
      .map(p => p.split("\n")[0].replace("### ", ""));
    const avertissement = refusSecret.length > 0
      ? `ATTENTION : ${refusSecret.length} fichier(s) écarté(s) par le filtre de confidentialité et NON analysé(s) : ${refusSecret.join(", ")}\n\n`
      : "";
    return (
      avertissement +
      `[${model} · ${planOf(model)} · ${totalTokens} tokens]\n\n` +
      `## Par fichier\n\n` +
      parts.join("\n\n") +
      entete +
      ((typeof tronquees === "number" && tronquees > 0)
        ? `\n\n${tronquees} résumé(s) ont été tronqué(s) à max_tokens.`
        : "")
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
      `  stocke  : ${INDEX_PATH} (local, jamais transmis)` +
      // LA PERTE SE DIT, ET SE CHIFFRE QUAND ON PEUT.
      //
      // Sans cette ligne, l'appelant lit « Index construit » et croit
      // avoir ajoute un corpus, alors qu'il vient d'en detruire un. Une
      // instance voisine l'a vecu : elle a rapporte « en construire un
      // autre ecrase le precedent », juste sur l'effet et faux sur la
      // cause, faute d'avoir ete informee de la condition.
      (index.remplacement
        ? `\n  ATTENTION : l'index precedent a ete REMPLACE, non fusionne.` +
          `\n    motif   : ${index.remplacement}` +
          `\n    perdus  : ${index.extraits_perdus} extrait(s)`
        : ``)
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
    const tasks = exigerTableauNonVide(args.tasks, "tasks", 1, "tache");
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
          `### ${i + 1}. ${result.model} — ${((Date.now() - started) / 1000).toFixed(1)}s${mentionsReponse(result)}\n` +
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
    const models = exigerTableauNonVide(args.models, "models", 2, "modeles");
    exigerEntierPositif(args.max_tokens, "max_tokens");
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
        lignes.push(`  ${model.padEnd(30)} ${seconds.toFixed(1).padStart(7)}s  ${String(result.tokens).padStart(7)} tokens${mentionsReponse(result)}`);
        corps.push(`### ${model}${mentionsReponse(result)}\n${result.text.trim()}`);
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
  if (name === "nexus_charge") {
    return await runPython([path.join(INSTALL_ROOT, "scripts", "nexus_charge.py")]);
  }
  if (name === "nexus_livres") {
    const q = String(args.question || "");
    if (!q) return { content: [{ type: "text", text: "question requise" }] };
    return await runPython(
      [path.join(INSTALL_ROOT, "scripts", "nexus_livres_semantique.py"), "search", q]);
  }

  if (name === "nexus_verrou") {
    return await runPython([path.join(INSTALL_ROOT, "scripts", "nexus_verrou_machine.py")]);
  }

  if (name === "nexus_models") {
    const data = await getJson("/v1/models");
    const ids = (data.data || []).map((d) => d.id).sort();
    // Classer d'apres les litellm_params reels, et non d'apres le suffixe :
    // `releve-locale` etait annonce « facture au token » alors qu'il est
    // local -- l'orchestrateur l'evitait donc pour du confidentiel, ou
    // renoncait au profil coding dont il est le premier candidat.
    const plans = await chargerPlans();
    // LES MODELES RESIDENTS, ENFIN BRANCHES.
    //
    // C'etait l'objet du P2 de la session voisine : ce qui rend le plan local
    // lent n'est pas l'inference, c'est le CHARGEMENT des poids -- 31 s a
    // froid contre 2 s a chaud, mesure sur qwen3.6:27b. L'appelant qui sait
    // ce qui est deja chaud supprime la cause dominante de la latence au lieu
    // d'en subir l'effet.
    //
    // CE QUI ETAIT FAUX : `modelesResidents()` a bien ete ecrite, et jamais
    // appelee. La capacite avait ete annoncee faite ; elle n'existait pas.
    // Aucun humain ne l'a vu, et le seul outil qui l'aurait vu -- eslint --
    // rendait « 0 violation » parce que son flux etait illisible.
    //
    // L'echec ne bloque pas : le moteur peut etre arrete alors que la
    // passerelle repond. Une liste vide est alors dite comme telle, jamais
    // presentee comme « aucun modele chaud ».
    let residents = null;
    try {
      residents = await modelesResidents();
    } catch {
      // La liaison n'etait jamais lue : le motif de l'echec ne change
      // rien ici, seul compte qu'on ne sache pas.
      residents = null;
    }
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
    // « Non mesurable » et « aucun » sont dits SEPAREMENT : confondre les deux
    // ferait croire le moteur vide alors qu'il est injoignable.
    let ligneChauds;
    if (residents === null) {
      ligneChauds = "MODELES CHAUDS — moteur injoignable, etat inconnu\n";
    } else if (residents.length === 0) {
      ligneChauds = "MODELES CHAUDS — aucun : le premier appel paiera le chargement des poids\n";
    } else {
      // Le moteur rend le nom OLLAMA BRUT (ex. phi3.5:latest), inutilisable
      // tel quel : la passerelle n'expose que des alias (ex. phi3.5-local).
      // Chaque resident est donc traduit dans le vocabulaire du reste de la
      // sortie, le nom brut garde entre parentheses ; sans correspondance,
      // le nom brut est affiche et signale non expose.
      const aliasDe = (brut) => {
        const base = String(brut).split(":")[0];
        const exact = base + "-local";
        if (groups.local.includes(exact)) return exact;
        // Variante de suffixe : « releve-locale » expose « releve:... ».
        return groups.local.find((a) => a.startsWith(exact)) || null;
      };
      const affiches = residents.map((brut) => {
        const alias = aliasDe(brut);
        return alias ? alias + " (" + brut + ")" : brut + " (non expose)";
      });
      ligneChauds =
        `MODELES CHAUDS — deja en memoire, repondent sans payer le chargement (${residents.length})\n  ` +
        affiches.join("\n  ") + "\n";
    }

    return (
      ligneChauds +
      `\nLOCAL — aucune donnee ne quitte la machine (${groups.local.length})\n  ` +
      groups.local.join("\n  ") +
      `\n\nOLLAMA CLOUD — les donnees sortent vers ollama.com (${groups.cloud.length})\n  ` +
      groups.cloud.join("\n  ") +
      `\n\nANTHROPIC — facture au token sur le compte API, PAS sur l'abonnement (${groups.anthropic.length})\n  ` +
      groups.anthropic.join("\n  ") +
      `\n\nROUTEURS (${groups.routeurs.length})\n  ` +
      groups.routeurs.join("\n  ")
    );
  }

  // La liste est DEDUITE de TOOLS, jamais recopiee : une liste en dur
  // divergerait le jour ou un outil est ajoute, et un refus qui ment sur ce
  // qui existe est pire qu'un refus muet.
  throw new ErreurProtocole(
    "outil inconnu : " + name + ". Outils connus : " +
    TOOLS.map(function (t) { return t.name; }).sort().join(", ")
  );
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

async function tenirVerrou(classe) {
  // fonction qui attend le verrou en lançant le script python
  return new Promise((resolve, reject) => {
    const { spawn } = require('node:child_process')
    const path = require('path')
    let timer
    let pris = false
    let child

    // spawn du processus, capture des exceptions
    try {
      const python = process.env.NEXUS_PYTHON || 'python'
      const script = path.join(__dirname, '..', '..', 'scripts', 'nexus_verrou_tenir.py')
      child = spawn(python, [script, classe, '--projet', 'mcp', '--attente-s', '900'], { stdio: ['pipe', 'pipe', 'inherit'] })
    } catch (e) {
      log('Erreur lors du spawn du verrou :', e)
      // resolve avec relacher qui ne fait rien
      resolve({ relacher: () => {} })
      return
    }

    // buffer pour accumuler stdout
    let buffer = ''
    const onData = (data) => {
      buffer += data.toString()
      const parts = buffer.split('\n')
      buffer = parts.pop() // conserve le morceau incomplet
      for (const line of parts) {
        if (line.trim() === 'PRIS') {
          pris = true
          clearTimeout(timer)
          resolve({ relacher: () => { child.stdin.end() } })
          child.stdout.removeListener('data', onData)
          return
        }
      }
    }
    child.stdout.on('data', onData)

    // gestion des erreurs du processus
    child.on('error', (err) => {
      log('Erreur du processus verrou :', err)
      clearTimeout(timer)
      resolve({ relacher: () => {} })
    })

    // fermeture du processus sans avoir vu PRIS
    child.on('close', (code) => {
      if (!pris) {
        clearTimeout(timer)
        reject(new Error('Verrou non pris, code 75 (CONTENTION)'))
      }
    })

    // minuteur de 15 minutes qui tue le processus et rejette
    timer = setTimeout(() => {
      if (child && !pris) {
        child.kill()
        reject(new Error('Timeout verrou, code 75 (CONTENTION)'))
      }
    }, 900000)
  })
}

async function callTool(name, args) {
  // appel direct si l'outil n'est pas dans le set bruyant
  if (!OUTILS_LOURDS.has(name)) {
    return callToolInterne(name, args)
  }
  log(`Attente du verrou pour l'outil ${name}`)
  const start = Date.now()
  const verrou = await tenirVerrou('banc')
  const attente = Date.now() - start
  log(`Temps d'attente ${attente} ms`)
  try {
    return await callToolInterne(name, args)
  } finally {
    if (verrou && typeof verrou.relacher === 'function') {
      verrou.relacher()
    }
  }
}

// export uniquement si le module exporte déjà callTool
if (typeof module !== 'undefined' && module.exports && Object.prototype.hasOwnProperty.call(module.exports, 'callTool')) {
  module.exports.callTool = callTool
}