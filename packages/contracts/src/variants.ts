import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

export type VariantDefinition = {
  id: string;
  label: string;
  enabled: boolean;
  description: string;
  agentOverrides: Record<string, Record<string, unknown>>;
};

type RegistryYaml = {
  variants: Record<
    string,
    {
      label: string;
      enabled: boolean;
      description?: string;
      agentOverrides?: Record<string, Record<string, unknown>>;
    }
  >;
};

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const registryPath = join(packageRoot, "variants", "registry.yaml");

let cachedRegistry: VariantDefinition[] | null = null;

export function loadVariantRegistry(): VariantDefinition[] {
  if (cachedRegistry) {
    return cachedRegistry;
  }

  const raw = readFileSync(registryPath, "utf8");
  const parsed = parse(raw) as RegistryYaml;

  cachedRegistry = Object.entries(parsed.variants)
    .map(([id, entry]) => ({
      id,
      label: entry.label,
      enabled: entry.enabled,
      description: entry.description ?? "",
      agentOverrides: entry.agentOverrides ?? {},
    }))
    .sort((a, b) => a.id.localeCompare(b.id));

  return cachedRegistry;
}

export function getEnabledVariantIds(): string[] {
  return loadVariantRegistry()
    .filter((variant) => variant.enabled)
    .map((variant) => variant.id)
    .sort();
}

export function assertVariantsAllowed(ids: string[]): void {
  const registry = loadVariantRegistry();
  const byId = new Map(registry.map((variant) => [variant.id, variant]));

  for (const id of ids) {
    const variant = byId.get(id);
    if (!variant) {
      throw new Error(`Unknown variant: ${id}`);
    }
    if (!variant.enabled) {
      throw new Error(`Variant is disabled: ${id}`);
    }
  }
}

/** @internal Test helper — clears in-memory registry cache. */
export function _resetVariantRegistryCacheForTests(): void {
  cachedRegistry = null;
}
