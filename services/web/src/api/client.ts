/**
 * SelenePlan API Client
 * Automatically attaches in-memory Bearer token and extracts trace_id from errors.
 */

import { useAuthStore } from "@/auth/store";
import type { ProductMetadata, ProductStats, VerifyResult } from "./types";

export class ApiError extends Error {
  status: number;
  traceId?: string;

  constructor(message: string, status: number, traceId?: string) {
    super(message);
    this.status = status;
    this.traceId = traceId;
    this.name = "ApiError";
  }
}

export async function fetchWithAuth<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = useAuthStore.getState().accessToken;
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("Content-Type", "application/json");

  const baseUrl = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8000";
  const url = `${baseUrl}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let traceId: string | undefined = response.headers.get("X-Trace-Id") || undefined;
    let errorMsg = `API request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) errorMsg = errorJson.detail;
      if (errorJson.trace_id) traceId = errorJson.trace_id;
    } catch {
      // Body not JSON
    }
    throw new ApiError(errorMsg, response.status, traceId);
  }

  return response.json();
}

export const api = {
  getProductMetadata: (productId: string) =>
    fetchWithAuth<ProductMetadata>(`/v1/products/${productId}`),

  getProductStats: (productId: string) =>
    fetchWithAuth<ProductStats>(`/v1/products/${productId}/stats`),

  verifyArtifact: (artifactId: string) =>
    fetchWithAuth<VerifyResult>("/internal/v1/verify-artifact", {
      method: "POST",
      body: JSON.stringify({ artifact_id: artifactId }),
    }),
};
