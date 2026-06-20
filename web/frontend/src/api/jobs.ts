import api from "./client";
import { Job, JobCreateRequest, JobListResponse, Mp4ExportState } from "../types";

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

export async function requestMp4Export(id: string): Promise<Mp4ExportState> {
  const resp = await api.post(`/jobs/${id}/export-mp4`);
  return resp.data;
}

export async function getMp4ExportStatus(id: string): Promise<Mp4ExportState> {
  const resp = await api.get<Mp4ExportState>(`/jobs/${id}/export-mp4/status`);
  return resp.data;
}

export function getMp4ExportDownloadUrl(id: string): string {
  return `/api/jobs/${id}/export-mp4/download`;
}
