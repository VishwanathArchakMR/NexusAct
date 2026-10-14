import React from "react";
import type { ServiceStatus } from "../types/system";

interface StatusBadgeProps {
  status: ServiceStatus | string;
  label?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label }) => {
  const norm = (status || "").toUpperCase();
  const isSuccess = norm === "ONLINE" || norm === "READY" || norm === "HEALTHY" || norm === "OK";
  const isWarning = norm === "DEGRADED" || norm === "INITIALIZED";
  const isLoading = norm === "LOADING";

  let bg = "var(--status-error-bg)";
  let color = "var(--status-error-text)";
  let border = "var(--status-error-border)";
  let dotColor = "#ef4444";

  if (isSuccess) {
    bg = "var(--status-success-bg)";
    color = "var(--status-success-text)";
    border = "var(--status-success-border)";
    dotColor = "#10b981";
  } else if (isWarning || isLoading) {
    bg = "var(--status-warning-bg)";
    color = "var(--status-warning-text)";
    border = "var(--status-warning-border)";
    dotColor = "#f59e0b";
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.45rem",
        padding: "0.2rem 0.65rem",
        borderRadius: "9999px",
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.03em",
        backgroundColor: bg,
        color: color,
        border: `1px solid ${border}`,
      }}
    >
      <span
        style={{
          width: "0.5rem",
          height: "0.5rem",
          borderRadius: "50%",
          backgroundColor: dotColor,
          display: "inline-block",
        }}
      />
      {label || norm}
    </span>
  );
};
