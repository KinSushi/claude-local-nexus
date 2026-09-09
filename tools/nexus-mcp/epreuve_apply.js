// L'outil MCP nexus_apply est-il cable dans server.js ? Lecture du CODE REEL.
const fs = require('fs');
const path = require('path');

let source;
try {
  source = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');
} catch {
  console.log('[RATE] source : impossible de lire server.js');
  process.exit(1);
}

let failures = 0;

function report(ok, name, detail) {
  const tag = ok ? '[OK  ]' : '[RATE]';
  console.log(`${tag} ${name} : ${detail}`);
  if (!ok) failures++;
}

// 1. declare
const declareRegex = /name\s*:\s*["']nexus_apply["']/;
if (declareRegex.test(source)) {
  report(true, 'declare', 'outil declare correctement');
} else {
  report(false, 'declare', 'outil non declare');
}

// 2. schema
if (declareRegex.test(source)) {
  const lines = source.split(/\r?\n/);
  const declIdx = lines.findIndex(l => declareRegex.test(l));
  const segment = lines.slice(declIdx + 1, declIdx + 41).join('\n');
  const required = ['texte', 'cible', 'required'];
  const missing = required.filter(w => !segment.includes(w));
  if (missing.length === 0) {
    report(true, 'schema', 'schema present');
  } else {
    report(false, 'schema', 'manque : ' + missing.join(', '));
  }
} else {
  report(false, 'schema', 'declaration introuvable');
}

// 3. handler
const handlerRegex = /if\s*\(\s*name\s*===\s*["']nexus_apply["']\s*\)/;
let handlerIdx = -1;
if (handlerRegex.test(source)) {
  const lines = source.split(/\r?\n/);
  handlerIdx = lines.findIndex(l => handlerRegex.test(l));
  const segment = lines.slice(handlerIdx + 1, handlerIdx + 31).join('\n');
  const hasPy = segment.includes('nexus_appliquer.py');
  const hasVerdict = segment.includes('[0, 1]');
  const missing = [];
  if (!hasPy) missing.push('nexus_appliquer.py');
  if (!hasVerdict) missing.push('[0, 1]');
  if (missing.length === 0) {
    report(true, 'handler', 'handler complet');
  } else {
    report(false, 'handler', 'manque : ' + missing.join(', '));
  }
} else {
  report(false, 'handler', 'condition if (name === "nexus_apply") introuvable');
}

// 4. nettoyage
if (handlerIdx !== -1) {
  const lines = source.split(/\r?\n/);
  const segment = lines.slice(handlerIdx + 1, handlerIdx + 31).join('\n');
  if (segment.includes('unlinkSync')) {
    report(true, 'nettoyage', 'suppression du JSONL effectuee');
  } else {
    report(false, 'nettoyage', 'unlinkSync absent');
  }
} else {
  report(false, 'nettoyage', 'section handler introuvable');
}

// 5. routage creation : un patch de creation doit partir vers nexus_creer
if (handlerIdx !== -1) {
  const lines = source.split(/\r?\n/);
  const segment = lines.slice(handlerIdx + 1, handlerIdx + 31).join('\n');
  if (segment.includes('nexus_creer.py')) {
    report(true, 'routage creation', 'un patch de creation est route vers nexus_creer');
  } else {
    report(false, 'routage creation', 'nexus_creer.py absent : la creation retomberait sur nexus_appliquer');
  }
} else {
  report(false, 'routage creation', 'section handler introuvable');
}

process.exit(failures ? 1 : 0);