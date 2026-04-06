import api from "./client";
import { UploadedFile } from "../types";

export async function uploadFile(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);

  const resp = await api.post<UploadedFile>("/uploads", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return resp.data;
}
