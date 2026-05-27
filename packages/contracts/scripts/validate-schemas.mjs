import { readdir, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const schemasDir = join(root, "schemas");
const files = (await readdir(schemasDir)).filter((file) =>
  file.endsWith(".schema.json"),
);

if (files.length === 0) {
  throw new Error("No schema files found.");
}

const seenIds = new Set();

for (const file of files) {
  const path = join(schemasDir, file);
  const schema = JSON.parse(await readFile(path, "utf8"));

  for (const key of ["$schema", "$id", "title", "type"]) {
    if (!schema[key]) {
      throw new Error(`${file} is missing required schema metadata: ${key}`);
    }
  }

  if (seenIds.has(schema.$id)) {
    throw new Error(`${file} duplicates schema id ${schema.$id}`);
  }

  seenIds.add(schema.$id);

  if (schema.type !== "object") {
    throw new Error(`${file} root type must be object.`);
  }
}

console.log(`Validated ${files.length} schema files.`);
