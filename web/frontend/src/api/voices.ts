import api from "./client";
import { BundledVoice, LanguageOption } from "../types";

export async function listVoices(): Promise<BundledVoice[]> {
  const resp = await api.get<BundledVoice[]>("/voices");
  return resp.data;
}

export function voiceAudioUrl(voiceId: string): string {
  return `/api/voices/${encodeURIComponent(voiceId)}/audio`;
}

export async function listLanguages(): Promise<LanguageOption[]> {
  const resp = await api.get<LanguageOption[]>("/languages");
  return resp.data;
}

export interface PreviewParams {
  text?: string;
  language: string;
  voice_id?: string;
  ref_audio_file_id?: string;
  ref_text?: string;
}

/** Returns a Blob URL of the synthesized preview audio. The caller is
 *  responsible for revoking the URL with URL.revokeObjectURL(). */
export async function previewVoice(params: PreviewParams): Promise<string> {
  const resp = await api.post("/voices/preview", params, {
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data as Blob);
}
