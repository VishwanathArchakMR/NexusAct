/**
 * API client for fetching telemetry and health from the FastAPI backend.
 */

import { config } from "../config/env";
import type { LivenessData, ReadinessData, SystemStatusData } from "../types/system";

export class ApiError extends Error {
  statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

export async function fetchLiveness(): Promise<LivenessData> {
  const url = `${config.apiBaseUrl}/api/v1/health`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new ApiError(res.status, `Liveness check failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchReadiness(): Promise<ReadinessData> {
  const url = `${config.apiBaseUrl}/api/v1/ready`;
  const res = await fetch(url);
  // Readiness might return 503 if FalkorDB is offline; parse JSON body honestly
  if (res.status === 200 || res.status === 503) {
    return res.json();
  }
  throw new ApiError(res.status, `Readiness check failed with status ${res.status}`);
}

export async function fetchSystemStatus(): Promise<SystemStatusData> {
  const url = `${config.apiBaseUrl}/api/v1/system/status`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new ApiError(res.status, `System status fetch failed with status ${res.status}`);
  }
  return res.json();
}
