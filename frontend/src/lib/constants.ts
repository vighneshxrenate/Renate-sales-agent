export const SOURCES = [
  { value: "linkedin", label: "LinkedIn" },
  { value: "naukri", label: "Naukri" },
  { value: "indeed", label: "Indeed" },
  { value: "glassdoor", label: "Glassdoor" },
  { value: "google_jobs", label: "Google Jobs" },
  { value: "career_page", label: "Career Page" },
] as const;

export const STATUSES = [
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "disqualified", label: "Disqualified" },
] as const;

export const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-500/20 text-blue-400",
  contacted: "bg-yellow-500/20 text-yellow-400",
  qualified: "bg-green-500/20 text-green-400",
  disqualified: "bg-red-500/20 text-red-400",
};

export const JOB_STATUS_COLORS: Record<string, string> = {
  pending: "bg-[var(--muted)] text-[var(--muted-foreground)]",
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-[var(--muted)] text-[var(--muted-foreground)]",
};

export const EMAIL_SOURCE_LABELS: Record<string, string> = {
  scraped: "Website",
  pattern_guess: "Pattern",
  dns: "DNS",
  apollo: "Apollo",
};

export const EMAIL_TYPE_LABELS: Record<string, string> = {
  generic: "Generic",
  personal: "Personal",
  hr: "HR",
  careers: "Careers",
};

export const SOURCE_COLORS: Record<string, string> = {
  linkedin: "#0a66c2",
  naukri: "#4a90d9",
  indeed: "#2164f3",
  glassdoor: "#0caa41",
  google_jobs: "#4285f4",
  career_page: "#8b5cf6",
};
