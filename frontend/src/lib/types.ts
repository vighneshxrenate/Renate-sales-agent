export interface LeadEmail {
  id: string;
  email: string;
  email_type: string | null;
  source: string | null;
  verified: boolean;
}

export interface LeadPhone {
  id: string;
  phone: string;
  phone_type: string | null;
}

export interface HiringPosition {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  job_type: string | null;
  experience_level: string | null;
  salary_range: string | null;
  posted_date: string | null;
  source_url: string | null;
}

export interface Lead {
  id: string;
  company_name: string;
  location: string | null;
  website: string | null;
  industry: string | null;
  company_size: string | null;
  description: string | null;
  source: string;
  source_url: string;
  confidence_score: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  emails: LeadEmail[];
  phones: LeadPhone[];
  positions: HiringPosition[];
}

export interface LeadListResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
}

export interface ScrapeJob {
  id: string;
  source: string;
  keywords: string | null;
  location_filter: string | null;
  status: string;
  triggered_by: string;
  total_pages: number | null;
  pages_scraped: number;
  leads_found: number;
  leads_new: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScrapeJobListResponse {
  jobs: ScrapeJob[];
  total: number;
  page: number;
  per_page: number;
}

export interface DailyReport {
  id: string;
  report_date: string;
  total_leads_found: number;
  new_leads: number;
  leads_by_source: Record<string, number>;
  leads_by_location: Record<string, number>;
  top_hiring_positions: Array<{ title: string; count: number }>;
  scrape_jobs_run: number;
  scrape_jobs_failed: number;
  email_sent: boolean;
  created_at: string;
}

export interface ReportListResponse {
  reports: DailyReport[];
  total: number;
  page: number;
  per_page: number;
}

export interface LeadStats {
  total: number;
  by_source: Record<string, number>;
  by_status: Record<string, number>;
}
