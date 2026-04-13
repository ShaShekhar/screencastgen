import api from "./client";
import { ReaderManifest, ReaderStatus } from "../types";

export async function getReaderStatus(jobId: string): Promise<ReaderStatus> {
  const resp = await api.get<ReaderStatus>(`/jobs/${jobId}/reader/status`);
  return resp.data;
}

export async function getReaderManifest(jobId: string): Promise<ReaderManifest> {
  const resp = await api.get<ReaderManifest>(`/jobs/${jobId}/reader/manifest`);
  return resp.data;
}

export function getReaderAudioUrl(jobId: string): string {
  return `/api/jobs/${jobId}/reader/audio`;
}

export function getReaderPageUrl(jobId: string, filename: string): string {
  return `/api/jobs/${jobId}/reader/pages/${filename}`;
}
