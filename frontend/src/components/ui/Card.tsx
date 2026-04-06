import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "bg-[var(--card)] border border-[var(--border)] rounded-xl",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  className,
}: {
  label: string;
  value: string | number;
  sub?: string;
  className?: string;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <p className="text-sm text-[var(--muted-foreground)]">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && (
        <p className="text-xs text-[var(--muted-foreground)] mt-1">{sub}</p>
      )}
    </Card>
  );
}
