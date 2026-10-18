/**
 * Environment configuration for NexusAct Frontend.
 */

const envApiBase = import.meta.env.VITE_API_BASE_URL;

export const config = {
  // In production builds (deployed behind reverse proxy/Caddy), default to same-origin relative path ""
  // In local development, fall back to "http://localhost:8000" unless explicitly specified.
  apiBaseUrl:
    envApiBase !== undefined
      ? envApiBase
      : import.meta.env.PROD
        ? ""
        : "http://localhost:8000",
  appName: "NexusAct",
  appSubtitle: "Engineering Brain — Connected Data AI Agent",
};
