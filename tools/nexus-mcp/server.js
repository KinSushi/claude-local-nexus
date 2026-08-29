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

const PROTOCOL_VERSION = "2025-06-18";
const SERVER_INFO = { name: "nexus-local", version: "1.0.0" };

// Racine du depot, par ordre de fiabilite decroissante : reglage explicite,
// racine fournie par Claude Code, puis position du fichier. Aucune de ces
// sources n'est un chemin en dur : le pont doit pouvoir etre repris tel
// quel dans un autre projet.
const REPO_ROOT =
  process.env.NEXUS_ROOT ||
  process.env.CLAUDE_PROJECT_DIR ||
  path.resolve(__dirname, "..", "..");
const LITELLM_URL = process.env.NEXUS_LITELLM_URL || "http://127.0.0.1:4000";
const INDEX_DIR = path.join(REPO_ROOT, ".nexus");
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
const DEFAULT_EMBED_MODEL = process.env.NEXUS_EMBED_MODEL || "qwen3-embedding-8b-local";
// Le plus leger des modeles multimodaux installes : sur CPU, un llava:34b
// mettrait des dizaines de minutes a decrire une capture d'ecran.
const DEFAULT_VISION_MODEL = process.env.NEXUS_VISION_MODEL || "llava-7b-local";
const DEFAULT_TIMEOUT_MS = Number(process.env.NEXUS_TIMEOUT_MS || 600000);

function log(...args) {
  process.stderr.write("[nexus-local] " + args.join(" ") + "\n");
}

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
  const envFile = path.join(REPO_ROOT, ".env");
  if (fs.existsSync(envFile)) {
    for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const m = /^\s*LITELLM_MASTER_KEY\s*=\s*(.*)$/.exec(line);
      if (m && m[1].trim()) {
        cachedKey = m[1].trim();
        return cachedKey;
      }
    }
  }
  // Un Bearer vide produit un 401 opaque, cote serveur, plusieurs couches
  // plus loin. Mieux vaut echouer ici, ou la cause est encore lisible.
  throw new Error(
    "LITELLM_MASTER_KEY introuvable : ni dans l'environnement, ni dans " +
    path.join(REPO_ROOT, ".env")
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
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(new Error("LiteLLM HTTP " + res.statusCode + " : " + text.slice(0, 400)));
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
const TRANSIENT = /socket hang up|ECONNRESET|ECONNREFUSED|EPIPE|ETIMEDOUT|delai depasse|HTTP 5\d\d|HTTP 429/i;

async function withRetry(operation, attempts = 3) {
  let last;
  for (let i = 0; i < attempts; i++) {
    try {
      return await operation();
    } catch (err) {
      last = err;
      if (!TRANSIENT.test(err.message) || i === attempts - 1) throw err;
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

async function chat(model, messages, maxTokens, timeoutMs) {
  // Une phase MAP peut durer un quart d'heure : perdre dix fenetres deja
  // calculees pour une coupure de socket serait absurde.
  const { body, headers } = await withRetry(() => requestJson(
    "/v1/chat/completions",
    { model, messages, max_tokens: maxTokens || 2048 },
    timeoutMs
  ));
  const choice = body.choices && body.choices[0];
  if (!choice) throw new Error("aucune reponse du modele");
  const usage = body.usage || {};
  // Derriere un routeur adaptatif, le corps et x-litellm-model-group ne
  // renvoient que le nom du routeur. Seul x-litellm-adaptive-router-model
  // designe le modele que le routeur a choisi.
  const resolved =
    headers["x-litellm-adaptive-router-model"] ||
    headers["x-litellm-model-group"] ||
    body.model ||
    model;
  return {
    text: (choice.message && choice.message.content) || "",
    model: resolved,
    upstream: headers["x-litellm-model-name"] || "",
    tokens: (usage.prompt_tokens || 0) + (usage.completion_tokens || 0),
  };
}

async function embed(model, inputs) {
  const { body } = await withRetry(() => requestJson(
    "/v1/embeddings", { model, input: inputs }, DEFAULT_TIMEOUT_MS
  ));
  return body.data.map((d) => d.embedding);
}

// ---------------------------------------------------------------------------
// Indexation du dépôt (couche RAG locale)
// ---------------------------------------------------------------------------

const SKIP_DIRS = new Set([
  ".git", "node_modules", ".nexus", "backups", "logs", "__pycache__",
  ".venv", "venv", "dist", "build", ".idea", ".vscode",
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
  const files = walk(root, []);
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
  fs.writeFileSync(INDEX_PATH, JSON.stringify(index), "utf8");
  return index;
}

function loadIndex() {
  if (!fs.existsSync(INDEX_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(INDEX_PATH, "utf8"));
  } catch {
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
const PROFILES = {
  coding: {
    description: "implementation, debogage, refactorisation",
    contextMin: 32768,
    models: ["releve-locale", "glm-4.7-flash-local", "qwen3-coder-30b-local",
             "qwen2.5-coder-32b-local", "kimi-k2.7-code-cloud", "gpt-oss-120b-cloud"],
  },
  reasoning: {
    description: "architecture, raisonnement difficile, arbitrages",
    contextMin: 32768,
    models: ["glm-4.7-flash-local", "gemma4-31b-local", "nemotron-3-ultra-cloud",
             "gpt-oss-120b-cloud"],
  },
  rapide: {
    description: "classification, extraction, transformation courte",
    contextMin: 8192,
    models: ["llama3.2-3b-local", "phi3-mini-local", "gemma4-12b-local",
             "gpt-oss-20b-cloud"],
  },
  multimodal: {
    description: "image, capture d'ecran, OCR",
    contextMin: 8192,
    models: ["llava-7b-local", "llama3.2-vision-11b-local", "qwen3-vl-8b-local"],
  },
};

let cachedExposed = null;
async function exposedModels() {
  if (cachedExposed) return cachedExposed;
  const data = await getJson("/v1/models");
  cachedExposed = new Set((data.data || []).map((d) => d.id));
  return cachedExposed;
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

async function mapReduce(text, instruction, model, contextTokens, onProgress) {
  const budget = windowChars(contextTokens, 2048);
  const windows = splitIntoWindows(text, budget);
  let tokens = 0;

  const MAP_SYSTEM =
    "Tu analyses UN FRAGMENT d'un ensemble plus vaste. Extrais fidelement " +
    "ce qui repond a la consigne, sans rien inventer et sans conclure sur " +
    "l'ensemble : d'autres fragments seront traites separement. Si le " +
    "fragment ne contient rien d'utile, reponds exactement : RIEN.";

  // --- MAP -----------------------------------------------------------
  const mapped = [];
  for (let i = 0; i < windows.length; i++) {
    const result = await chat(
      model,
      [
        { role: "system", content: MAP_SYSTEM },
        {
          role: "user",
          content:
            `Consigne : ${instruction}\n\n` +
            `--- fragment ${i + 1}/${windows.length} ---\n${windows[i]}`,
        },
      ],
      1536
    );
    tokens += result.tokens;
    const body = (result.text || "").trim();
    if (body && body.toUpperCase() !== "RIEN") mapped.push(body);
    if (onProgress) onProgress("map", i + 1, windows.length);
  }

  if (!mapped.length) {
    return { text: "Aucun fragment pertinent.", windows: windows.length,
             passes: 1, tokens, model };
  }

  // --- REDUCE --------------------------------------------------------
  const REDUCE_SYSTEM =
    "Tu fusionnes des analyses partielles d'un meme ensemble. Produis une " +
    "synthese unique, fidele et sans redite. Ne rajoute aucune information " +
    "absente des analyses fournies.";

  let level = mapped;
  let passes = 1;
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
          2048
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
      // Aucune réduction possible : on s'arrête plutôt que de boucler.
      level = [next.join("\n\n")];
      break;
    }
    level = next;
  }

  return { text: level[0], windows: windows.length, passes, tokens, model };
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
      "en local, seul le resultat distille remonte. Chaque fichier est traite separement " +
      "puis les syntheses sont fusionnees.",
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
  return path.isAbsolute(p) ? p : path.join(REPO_ROOT, p);
}

async function callTool(name, args) {
  args = args || {};

  if (name === "nexus_ask") {
    if (!args.prompt) throw new Error("parametre 'prompt' requis");

    // Un modele explicite l'emporte sur un profil : demander un modele
    // precis est une decision, la laisser deduire n'en est pas une.
    let model = args.model;
    let note = "";
    if (!model && args.profile) {
      const resolved = await resolveProfile(args.profile);
      model = resolved.model;
      note = ` · profil ${args.profile}`;
    }
    model = model || DEFAULT_CHAT_MODEL;

    const messages = [];
    if (args.system) messages.push({ role: "system", content: args.system });
    messages.push({ role: "user", content: args.prompt });
    const result = await chat(model, messages, args.max_tokens || 2048);

    // Le plan est annonce, pas sous-entendu : ce qui a ete facture et ce
    // qui est sorti de la machine doit se lire sans enquete.
    const plan = result.model.endsWith("-cloud") ? "Ollama Cloud"
      : result.model.startsWith("claude-") ? "Anthropic, facture au token"
      : "local, cout 0";
    return `[${result.model} · ${plan}${note} · ${result.tokens} tokens]\n\n${result.text}`;
  }

  if (name === "nexus_route") {
    if (!args.prompt) throw new Error("parametre 'prompt' requis");
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
    // On rapporte le modele reellement retenu : une decision de routage
    // qui ne peut pas s'expliquer est operationnellement incomplete (§89).
    const billed = plane === "anthropic" ? "credits API Anthropic" : plane === "cloud" ? "abonnement Ollama Cloud" : "cout 0";
    return `[${router} -> ${result.model} · plan ${plane} · ${result.tokens} tokens · ${billed}]\n\n${result.text}`;
  }

  if (name === "nexus_context") {
    if (!args.instruction) throw new Error("parametre 'instruction' requis");
    const model = args.model || DEFAULT_CHAT_MODEL;
    const contextTokens = args.context_tokens || 32768;

    let corpus = args.text || "";
    const sources = [];
    for (const raw of args.paths || []) {
      const full = resolvePath(raw);
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
      `[${result.model} · local · ${result.windows} fenetres, ${result.passes} passes · ` +
      `~${approxTokens} tokens traites en ${contextTokens} de fenetre · ` +
      `${result.tokens} tokens factures 0]\n` +
      (sources.length ? `Sources : ${sources.join(", ")}\n` : "") +
      `\n${result.text}`
    );
  }

  if (name === "nexus_vision") {
    if (!args.path) throw new Error("parametre 'path' requis");
    const full = resolvePath(args.path);
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
    const { body, headers } = await requestJson("/v1/chat/completions", {
      model,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: args.prompt || "Decris cette image precisement." },
          { type: "image_url", image_url: { url: `data:image/${mime};base64,${encoded}` } },
        ],
      }],
      max_tokens: 1024,
    });
    const choice = body.choices && body.choices[0];
    if (!choice) throw new Error("aucune reponse du modele");
    const served = headers["x-litellm-model-group"] || model;
    const kb = Math.round(fs.statSync(full).size / 1024);
    return `[${served} · local · image ${kb} Ko · cout 0]\n\n${choice.message.content}`;
  }

  if (name === "nexus_summarize") {
    const paths = args.paths || [];
    if (!paths.length) throw new Error("parametre 'paths' requis");
    const instruction =
      args.instruction || "Fais une synthese technique fidele, structuree et concise.";
    const model = args.model || DEFAULT_CHAT_MODEL;
    const parts = [];
    let totalTokens = 0;

    for (const raw of paths) {
      const full = resolvePath(raw);
      // Meme interdiction que pour l'index : une synthese remonte vers
      // l'orchestrateur et quitte donc la machine.
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
      // Le contexte local est etroit : on tronque explicitement plutot
      // que de laisser le modele deborder silencieusement.
      const budget = 24000;
      const truncated = content.length > budget;
      const body = truncated ? content.slice(0, budget) : content;
      const result = await chat(
        model,
        [
          {
            role: "system",
            content:
              "Tu es un analyste technique. Tu resumes fidelement, sans inventer. " +
              "Si une information est absente, tu le dis.",
          },
          { role: "user", content: `${instruction}\n\n--- ${raw} ---\n${body}` },
        ],
        1024
      );
      totalTokens += result.tokens;
      parts.push(
        `### ${raw}${truncated ? " (tronque)" : ""}\n${result.text.trim()}`
      );
    }

    return `[${model} · local · ${totalTokens} tokens · cout 0]\n\n${parts.join("\n\n")}`;
  }

  if (name === "nexus_index_build") {
    const root = args.root ? resolvePath(args.root) : REPO_ROOT;
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
    if (!args.query) throw new Error("parametre 'query' requis");
    const hits = await searchIndex(args.query, args.k || 8, args.model);
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
    const tasks = args.tasks || [];
    if (!tasks.length) throw new Error("parametre 'tasks' requis");
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
    if (!args.prompt) throw new Error("parametre 'prompt' requis");
    const models = args.models || [];
    if (models.length < 2) throw new Error("au moins deux modeles sont requis");
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
    const { spawnSync } = require("node:child_process");
    for (const python of ["python", "python3"]) {
      const run = spawnSync(python,
        [path.join(REPO_ROOT, "scripts", "nexus_capability.py")],
        { encoding: "utf8", timeout: 300000 });
      if (run.status === 0 && run.stdout) return run.stdout;
    }
    throw new Error("profil materiel indisponible : Python introuvable ou en echec");
  }

  if (name === "nexus_savings") {
    const { spawnSync } = require("node:child_process");
    const jours = String(args.jours || 7);
    for (const python of ["python", "python3"]) {
      const run = spawnSync(python,
        [path.join(REPO_ROOT, "scripts", "nexus_savings.py"), "--jours", jours],
        { encoding: "utf8", timeout: 300000 });
      if (run.status === 0 && run.stdout) return run.stdout;
    }
    throw new Error("rapport indisponible : Python introuvable ou en echec");
  }

  if (name === "nexus_models") {
    const data = await getJson("/v1/models");
    const ids = (data.data || []).map((d) => d.id).sort();
    const groups = { local: [], cloud: [], anthropic: [], routeurs: [] };
    for (const id of ids) {
      if (id.startsWith("adaptive-router")) groups.routeurs.push(id);
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

  throw new Error("outil inconnu : " + name);
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

  if (method === "notifications/initialized" || method === "notifications/cancelled") {
    return; // notification : aucune reponse
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
    try {
      const text = await callTool(name, params && params.arguments);
      reply(id, { content: [{ type: "text", text }], isError: false });
    } catch (err) {
      // Erreur d'execution : elle revient dans le resultat, pas en erreur
      // protocole, pour que le modele puisse la lire et s'adapter.
      reply(id, {
        content: [{ type: "text", text: "Echec de " + name + " : " + err.message }],
        isError: true,
      });
    }
    return;
  }

  if (id !== undefined && id !== null) {
    replyError(id, -32601, "methode inconnue : " + method);
  }
}

function main() {
  log("demarrage — depot " + REPO_ROOT + " — passerelle " + LITELLM_URL);
  const rl = readline.createInterface({ input: process.stdin, terminal: false });

  // Une inference locale dure parfois plusieurs minutes. Sortir des la
  // fermeture de stdin avorterait les appels en vol et perdrait leur
  // reponse : on attend qu'ils se terminent.
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
  });
}

main();
