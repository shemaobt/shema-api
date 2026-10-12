// Session-language forms of the concrete coverage elements (beings / places / objects / times).
//
// The aliases table (_spec/registry/<book>.aliases.json, vendored canon — never edited here) names
// every entity in English and Hebrew. The team speaks the SESSION language: in the Terena pilot,
// Portuguese — "Noemi", "Elimeleque", "Rute", "Moabe", "Belém", "fome". Until 2026-09-15 the
// concrete heuristic (src/coverage/concreteMatch.ts) matched only the English/Hebrew keys, so in a
// Portuguese session those beads never filled: the Guide's ledger kept listing every person and
// place as NOT YET TOUCHED, and a session could never read "complete" (found by Marcia in the
// Observation Room, pilot day 4). This table adds the Portuguese forms — the names as the
// Brazilian Bibles spell them plus the variants the recognizer produces — keyed by the English
// name or one of its distinctive words. Pure data + one lookup; no I/O.

const FORMS: Record<string, string[]> = {
  // ── Ruth ──
  naomi: ["noemi", "noemí", "naomi"], elimelech: ["elimeleque", "elimelec"], mahlon: ["malom", "malon", "maalom", "maalon"],
  chilion: ["quiliom", "quilion", "quelion", "quiliã"], orpah: ["orfa"], ruth: ["rute"], boaz: ["boaz"], obed: ["obede"],
  jesse: ["jessé"], david: ["davi"], judges: ["juízes", "juizes"], yhwh: ["senhor jeová", "jeová", "senhor"],
  god: ["deus"], shaddai: ["todo-poderoso", "todo poderoso", "shaddai", "shadai"], bethlehem: ["belém"], judah: ["judá"],
  moab: ["moabe"], ephrathites: ["efrateus", "efratitas", "efrateu", "efratita"], ephrathah: ["efrata"], israel: ["israel"],
  famine: ["fome"], bread: ["pão", "pães"], barley: ["cevada"], wheat: ["trigo"], harvest: ["colheita"], harvesters: ["ceifeiros", "segadores", "ceifeiras"],
  foreman: ["capataz", "encarregado", "feitor"], redeemer: ["resgatador", "remidor", "redentor"],
  // B19 (named "The Nearer Redeemer" since SC-0086): its word "redeemer" is shared with Boaz in P09 S3
  // and P11 S4, so only these distinguishing phrases name him on their own (concreteMatch.ts).
  "the nearer redeemer": ["resgatador mais próximo", "resgatador mais chegado", "remidor mais próximo", "remidor mais chegado", "parente mais próximo", "parente mais chegado"],
  // Whole-name phrases for names whose one-word parts are another being's name or word, so that part
  // no longer counts alone (concreteMatch.ts rule (a)/(b), 2026-09-27): these name the element itself.
  "young men ruth did not go after": ["rapazes", "moços", "jovens"], // B32, P09 S3 only (bachurim, 3:10)
  "young men": ["moços", "rapazes"], // B17, P06/P07 (beside B16 Young Women, "moças")
  "the clan of elimelech": ["clã de elimeleque", "clã do elimeleque", "família de elimeleque", "família do elimeleque"],
  "naomi's dwelling in bethlehem": ["casa da noemi", "casa de noemi"],
  "in the days when the judges judged": ["tempo dos juízes", "dias dos juízes", "época dos juízes", "tempo em que os juízes", "dias em que os juízes"],
  gate: ["portão", "porta"], elders: ["anciãos", "anciões"],
  threshing: ["eira"], sandal: ["sandália", "chinelo"], grain: ["grão", "grãos"], sheaves: ["feixes", "molhos"], ephah: ["efa"],
  gleaning: ["respigar", "respiga", "catar"], hesed: ["bondade"], wing: ["asa", "manto"], favor: ["favor", "graça"], vinegar: ["vinagre"],
  seed: ["semente", "descendência"], son: ["filho"], child: ["menino", "criança"], tamar: ["tamar"], rachel: ["raquel"], leah: ["lia", "léia"],
  night: ["noite"], morning: ["manhã"], evening: ["tarde", "entardecer"], kinsman: ["parente"], inheritance: ["herança"],
  "women of moab": ["moabitas", "mulheres de moabe", "mulheres moabitas"], "women of bethlehem": ["mulheres de belém"],
  // B24 "The Women" (renamed from "Women of Bethlehem" by SC-0088): "the women" of 1:19 and 4:14, "the
  // neighbor-women" of 4:17. "as mulheres" with its article, so "as duas mulheres" (Naomi and Ruth,
  // 1:19) does not name them.
  "the women": ["as mulheres", "mulheres de belém", "vizinhas"], city: ["cidade"], field: ["campo"],
  // PL4 "The Town" (renamed from "The City" by SC-0089; הָעִיר, P07 2:18 and P10 3:15): its Portuguese
  // key again, as the old label had it.
  town: ["cidade"],
  // O13 in P10, labelled "The Cloak" there (src/ingest/referentialForms.ts PASSAGE_LABEL): 3:15 mitpachat,
  // «o manto» / «a capa» in the Brazilian Bibles.
  cloak: ["manto", "capa"],
  "mother's house": ["casa da mãe", "casa de sua mãe"], "hand of the lord": ["mão do senhor"], "roasted grain": ["grão torrado", "grãos torrados"],
  // ── Esther ──
  esther: ["ester"], mordecai: ["mordecai", "mardoqueu"], ahasuerus: ["assuero", "xerxes"], vashti: ["vasti"], haman: ["hamã", "amã"],
  zeresh: ["zeres"], hegai: ["hegai"], hathach: ["hataque"], harbona: ["harbona"], memucan: ["memucã"], bigthana: ["bigtã"], teresh: ["teres"],
  shaashgaz: ["saasgaz"], susa: ["susã", "susa"], persia: ["pérsia"], media: ["média"], medes: ["medos"], persians: ["persas"],
  jews: ["judeus"], jewish: ["judeu", "judia"], purim: ["purim"], india: ["índia"], cush: ["cuxe", "etiópia"], jerusalem: ["jerusalém"],
  babylon: ["babilônia"], banquet: ["banquete", "festa"], law: ["lei"], eunuchs: ["eunucos"], princes: ["príncipes"], provinces: ["províncias"],
  scribes: ["escribas", "secretários"], couriers: ["mensageiros", "correios"], edict: ["decreto", "edito", "carta"], letters: ["cartas"],
  gallows: ["forca"], harem: ["harém", "casa das mulheres"], citadel: ["cidadela", "fortaleza"], "king's gate": ["porta do rei", "portão do rei"],
  annals: ["crônicas", "anais"], officials: ["oficiais", "governadores", "sátrapas"], king: ["rei"], queen: ["rainha"], servants: ["servos"],
  enemies: ["inimigos"], friends: ["amigos"], sons: ["filhos"],
  // ── Jonah ──
  jonah: ["jonas"], amittai: ["amitai"], nineveh: ["nínive", "ninive"], tarshish: ["társis", "tarsis"], joppa: ["jope"], ship: ["navio", "barco"],
  captain: ["capitão"], crew: ["marinheiros", "tripulação"], fish: ["peixe"], worm: ["verme", "bicho"], qiqayon: ["planta", "mamona", "aboboreira"],
  booth: ["cabana", "abrigo"], sackcloth: ["pano de saco", "saco"], ashes: ["cinzas", "cinza"], wind: ["vento"], storm: ["tempestade"], sea: ["mar"],
  "dry land": ["terra seca", "terra firme"], sheol: ["sheol", "sepultura", "abismo"], temple: ["templo"], pit: ["cova"], lots: ["sortes"], cargo: ["carga"],
  fare: ["passagem"], animals: ["animais", "gado"], nobles: ["nobres"], deep: ["profundezas", "profundo"], weeds: ["algas"], people: ["povo"], idol: ["ídolos", "ídolo"],
};

const STOP = new Set(["the", "of", "in", "and", "a", "an", "to", "at", "on", "by", "for", "with", "his", "her", "their", "its", "one", "each", "own"]);

export function normEn(s: string): string {
  return s.toLowerCase().normalize("NFC").replace(/[^\p{L}\p{N}'\s]/gu, " ").replace(/\s+/g, " ").trim();
}
// Diacritics-free twin of a form, so a transcript that dropped an accent still matches.
function bare(s: string): string { return s.normalize("NFD").replace(/\p{M}/gu, ""); }

// The distinctive words of a name/label (stop words and very short words dropped).
export function contentWords(english: string | undefined | null): string[] {
  if (!english) return [];
  return normEn(english).split(" ").filter((w) => w.length >= 3 && !STOP.has(w));
}

// The names one English entry carries: the entry itself, and — for the registry's "Name (gloss)"
// and "Name / Other name" shapes — each name on its own ("The Jews (the Jewish people)" → "The
// Jews", "the Jewish people"). Each variant is then judged whole or descriptive by itself.
export function nameVariants(english: string | undefined | null): string[] {
  if (!english) return [];
  const out = new Set<string>([english.trim()]);
  const paren = english.match(/^([^()]+?)\s*\(([^()]+)\)\s*$/);
  const pieces = paren ? [paren[1], ...paren[2].split(",")] : [english];
  for (const p of pieces) for (const q of p.split(/\s+\/\s+/)) if (q.trim()) out.add(q.trim());
  return [...out];
}

// The session-language forms of the WHOLE name: the whole phrase's entry, plus — when the name has
// a single distinctive word ("Naomi", "The Redeemer", "Famine", "The Jews") — that word's entry,
// since the word then IS the name.
export function wholeForms(english: string | undefined | null): string[] {
  const out = new Set<string>();
  const take = (k: string) => { for (const f of FORMS[k] ?? []) { out.add(f); out.add(bare(f)); } };
  for (const v of nameVariants(english)) {
    take(normEn(v));
    const words = contentWords(v);
    if (words.length === 1) { take(words[0]); take(words[0].replace(/'s$/, "")); }
  }
  return [...out];
}

// The session-language forms of each distinctive word of a MULTI-word (descriptive) name —
// "Young Men Ruth Did Not Go After" → "rute"; "The Nearer Redeemer" → "resgatador". A form derived
// this way names only a part of the element; concreteMatch.ts decides whether it may count alone.
// (A form that is also a whole-name form stays whole — concreteMatch.ts keeps whole keys first.)
export function wordForms(english: string | undefined | null): string[] {
  const out = new Set<string>();
  const take = (k: string) => { for (const f of FORMS[k] ?? []) { out.add(f); out.add(bare(f)); } };
  for (const v of nameVariants(english)) {
    const words = contentWords(v);
    if (words.length <= 1) continue;
    for (const w of words) { take(w); take(w.replace(/'s$/, "")); }
  }
  return [...out];
}

// The session-language forms for an English name/label: the whole phrase's entry plus each
// distinctive word's entry. Returns [] when nothing is known — the English/Hebrew keys still apply.
export function sessionForms(english: string | undefined | null): string[] {
  return [...new Set([...wholeForms(english), ...wordForms(english)])];
}
