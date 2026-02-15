/**
 * Deploy a shared config value (e.g. API key) to all users.
 * TODO: Add sidecar endpoint for shared config deployment after AWS migration.
 */
export async function deploySharedKey(
  key: string,
  value: string,
): Promise<void> {
  // Shared config deployment is not yet available via sidecar API.
  // Will be re-enabled after AWS migration adds a /shared-config endpoint.
  throw new Error("Shared config deployment not yet available.");
}

/**
 * Pull all shared config values.
 * Returns a key-value record.
 */
export async function pullSharedConfig(): Promise<Record<string, string>> {
  // TODO: Re-enable via sidecar API after AWS migration
  return {};
}
