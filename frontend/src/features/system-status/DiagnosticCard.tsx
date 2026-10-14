import React from "react";
import type { LucideIcon } from "lucide-react";
import { StatusBadge } from "../../components/StatusBadge";
import type { ServiceStatus } from "../../types/system";

interface DiagnosticCardProps {
  title: string;
  subtitle: string;
  status: ServiceStatus | string;
  icon: LucideIcon;
  iconColor?: string;
  details: { label: string; value: string | number }[];
}

export const DiagnosticCard: React.FC<DiagnosticCardProps> = ({
  title,
  subtitle,
  status,
  icon: Icon,
  iconColor = "var(--accent-blue)",
  details,
}) => {
  return (
    <div
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "0.75rem",
        padding: "1.25rem",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        transition: "border-color 0.2s ease, transform 0.2s ease",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              padding: "0.6rem",
              borderRadius: "0.5rem",
              backgroundColor: "rgba(255, 255, 255, 0.04)",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon size={20} color={iconColor} />
          </div>
          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>{title}</h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{subtitle}</p>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      <div
        style={{
          borderTop: "1px solid var(--border-subtle)",
          paddingTop: "0.75rem",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "0.75rem",
        }}
      >
        {details.map((item, idx) => (
          <div key={idx}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block" }}>
              {item.label}
            </span>
            <span
              style={{
                fontSize: "0.9rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                fontFamily: typeof item.value === "number" ? "var(--font-mono)" : "inherit",
              }}
            >
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
