import { readdirSync, readFileSync } from "node:fs";
import { basename, join } from "node:path";

import { loadAliases, makeResolver } from "../docs/doctrine/vendor/ingest/aliases.ts";
import { loadCompilationLog } from "../docs/doctrine/vendor/ingest/compilationLog.ts";
import { buildCoverageElements } from "../docs/doctrine/vendor/ingest/coverage.ts";
import { loadForModel } from "../docs/doctrine/vendor/ingest/forModel.ts";
import { buildParsedMap } from "../docs/doctrine/vendor/ingest/parseMap.ts";
import { buildProseGlossIndex } from "../docs/doctrine/vendor/ingest/proseGloss.ts";

const [vendor, ...pericopes] = process.argv.slice(2);

const page = (folder, pericope) =>
  join(
    vendor,
    folder,
    readdirSync(join(vendor, folder)).find(
      (name) => name.startsWith(`${pericope}-`) && name.endsWith(".md"),
    ),
  );

const spines = {};
for (const pericope of pericopes) {
  const map = page("meaning-map", pericope);
  const book = basename(map).split("-")[1].toLowerCase();
  const resolver = makeResolver(
    loadAliases(join(vendor, "registry", `${book}.aliases.json`)),
    buildProseGlossIndex(readFileSync(map, "utf8")),
  );
  const parsed = buildParsedMap(
    loadForModel(page("meaning-coordinates", pericope)),
    loadCompilationLog(page("compilation-log", pericope)).audit,
    resolver,
  );
  spines[pericope] = buildCoverageElements(parsed).map((element) => [element.id, element.kind]);
}
process.stdout.write(JSON.stringify(spines));
