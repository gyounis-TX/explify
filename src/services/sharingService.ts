/**
 * Sharing management — user-to-user sharing relationships.
 * Delegates to sidecar API endpoints.
 */

import { sidecarApi } from "./sidecarApi";

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

export async function addShareRecipient(recipientEmail: string): Promise<void> {
  await sidecarApi.addShareRecipient(recipientEmail);
}

export async function removeShareRecipient(shareId: number): Promise<void> {
  await sidecarApi.removeShareRecipient(shareId);
}

export async function getMyShareRecipients(): Promise<ShareRecipient[]> {
  return sidecarApi.getShareRecipients();
}

export async function getMyShareSources(): Promise<ShareSource[]> {
  return sidecarApi.getShareSources();
}
