import { cn } from "@/lib/utils";
import { STATUS_COLORS, JOB_STATUS_COLORS } from "@/lib/constants";

export function StatusBadge({
  status,
  variant = "lead",
}: {
  status: string;
  variant?: "lead" | "job";
}) {
  const colors = variant === "job" ? JOB_STATUS_COLORS : STATUS_COLORS;
  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded text-xs font-medium capitalize",
        colors[status] || "bg-[var(--muted)] text-[var(--muted-foreground)]"
      )}
    >
      {status}
    </span>
  );
}
