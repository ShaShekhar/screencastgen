import api from "./client";
import {
  EpubExportState,
  Job,
  JobCreateRequest,
  JobListResponse,
} from "../types";

export async function createJob(req: JobCreateRequest): Promise<Job> {
  const resp = await api.post<Job>("/jobs", req);
  return resp.data;
}

export async function listJobs(
  status?: string,
  limit = 20,
  offset = 0
): Promise<JobListResponse> {
  const params: Record<string, string | number> = { limit, offset };
  if (status) params.status = status;
  const resp = await api.get<JobListResponse>("/jobs", { params });
  return resp.data;
}

export async function getJob(id: string): Promise<Job> {
  const resp = await api.get<Job>(`/jobs/${id}`);
  return resp.data;
}

export async function deleteJob(id: string): Promise<void> {
  await api.delete(`/jobs/${id}`);
}

export async function stopJob(id: string): Promise<void> {
  await api.post(`/jobs/${id}/stop`);
}

export function getDownloadUrl(id: string): string {
  return `/api/jobs/${id}/download`;
}

export async function requestEpubExport(id: string): Promise<EpubExportState> {
  const resp = await api.post<EpubExportState>(`/jobs/${id}/export-epub`);
  return resp.data;
}

export async function getEpubExportStatus(id: string): Promise<EpubExportState> {
  const resp = await api.get<EpubExportState>(`/jobs/${id}/export-epub/status`);
  return resp.data;
}

export function getEpubExportDownloadUrl(id: string): string {
  return `/api/jobs/${id}/export-epub/download`;
}
