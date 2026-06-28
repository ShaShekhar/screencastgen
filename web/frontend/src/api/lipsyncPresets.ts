import api from "./client";
import { LipsyncPreset } from "../types";

export async function listLipsyncPresets(): Promise<LipsyncPreset[]> {
  const resp = await api.get<LipsyncPreset[]>("/lipsync-presets");
  return resp.data;
}

export function lipsyncPresetVideoUrl(presetId: string): string {
  return `/api/lipsync-presets/${encodeURIComponent(presetId)}/video`;
}

export function lipsyncPresetAudioUrl(presetId: string): string {
  return `/api/lipsync-presets/${encodeURIComponent(presetId)}/audio`;
}
