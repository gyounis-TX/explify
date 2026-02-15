/**
 * Sharing management — user-to-user sharing relationships.
 *
 * TODO: Migrate to sidecar API endpoints after AWS migration.
 * Currently disabled since direct Supabase client access was removed.
 */

import { getSession, isAuthConfigured } from "./supabase";

export interface ShareRecipient {
  share_id: number;
  recipient_user_id: string;
  recipient_email: string;
  created_at: string;
}

export interface ShareSource {
  share_id: number;
  sharer_user_id: string;
  sharer_email: string;
  created_at: string;
}

export async function lookupUserByEmail(
  email: string,
): Promise<{ user_id: string; email: string } | null> {
  throw new Error("Sharing is not yet available. Coming soon.");
}

export async function addShareRecipient(
  recipientEmail: string,
): Promise<void> {
  throw new Error("Sharing is not yet available. Coming soon.");
}

export async function removeShareRecipient(shareId: number): Promise<void> {
  throw new Error("Sharing is not yet available. Coming soon.");
}

export async function getMyShareRecipients(): Promise<ShareRecipient[]> {
  if (!isAuthConfigured()) return [];
  const session = await getSession();
  if (!session) return [];
  // TODO: Call sidecar API endpoint
  return [];
}

export async function getMyShareSources(): Promise<ShareSource[]> {
  if (!isAuthConfigured()) return [];
  const session = await getSession();
  if (!session) return [];
  // TODO: Call sidecar API endpoint
  return [];
}
