// api.ts
// API client for KV Listings backend

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token management
let authToken: string | null = localStorage.getItem('kv_token');

export function setToken(token: string) {
  authToken = token;
  localStorage.setItem('kv_token', token);
}

export function getToken(): string | null {
  return authToken;
}

export function clearToken() {
  authToken = null;
  localStorage.removeItem('kv_token');
}

export function isAuthenticated(): boolean {
  return !!authToken;
}

// API request helper
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  };
  
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  if (response.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }
  
  return response.json();
}

// Types
export interface ListingSummary {
  listing_id: string;
  url: string | null;
  title: string | null;
  price_eur: number | null;
  eur_per_m2: number | null;
  rooms: string | null;
  total_area: string | null;
  last_seen_at: string | null;
  score: number | null;
  summary: string | null;
}

export interface ListingDetail extends ListingSummary {
  bedrooms: string | null;
  floors: string | null;
  year_built: string | null;
  condition: string | null;
  energy_class: string | null;
  description: string | null;
  breakdown: {
    price_value?: number;
    location?: number;
    condition?: number;
    size_layout?: number;
    investment_potential?: number;
  } | null;
  model: string | null;
  analyzed_at: string | null;
}

export interface ListingsResponse {
  listings: ListingSummary[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  total_listings: number;
  analyzed_count: number;
  avg_score: number | null;
  min_score: number | null;
  max_score: number | null;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
}

export interface ListingsParams {
  page?: number;
  per_page?: number;
  sort_by?: 'score' | 'price' | 'date' | 'eur_per_m2';
  sort_order?: 'asc' | 'desc';
  min_score?: number;
  max_price?: number;
  min_rooms?: number;
  only_analyzed?: boolean;
}

// API functions
export async function login(password: string): Promise<{ token: string }> {
  const data = await request<{ token: string }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
  setToken(data.token);
  return data;
}

export async function getListings(params: ListingsParams = {}): Promise<ListingsResponse> {
  const searchParams = new URLSearchParams();
  
  if (params.page) searchParams.set('page', String(params.page));
  if (params.per_page) searchParams.set('per_page', String(params.per_page));
  if (params.sort_by) searchParams.set('sort_by', params.sort_by);
  if (params.sort_order) searchParams.set('sort_order', params.sort_order);
  if (params.min_score !== undefined) searchParams.set('min_score', String(params.min_score));
  if (params.max_price !== undefined) searchParams.set('max_price', String(params.max_price));
  if (params.min_rooms !== undefined) searchParams.set('min_rooms', String(params.min_rooms));
  if (params.only_analyzed !== undefined) searchParams.set('only_analyzed', String(params.only_analyzed));
  
  const query = searchParams.toString();
  return request<ListingsResponse>(`/api/listings${query ? `?${query}` : ''}`);
}

export async function getListing(id: string): Promise<ListingDetail> {
  return request<ListingDetail>(`/api/listings/${id}`);
}

export async function getStats(): Promise<Stats> {
  return request<Stats>('/api/listings/stats');
}

export async function triggerAnalysis(limit?: number): Promise<{ status: string; message: string }> {
  return request('/api/analyze', {
    method: 'POST',
    body: JSON.stringify({ limit }),
  });
}

export async function getAnalysisStatus(): Promise<{ running: boolean }> {
  return request('/api/analyze/status');
}

export async function triggerScrape(area: string): Promise<{ status: string; message: string }> {
  return request('/api/scrape', {
    method: 'POST',
    body: JSON.stringify({ area }),
  });
}

export async function getScrapeStatus(): Promise<{ running: boolean; last_result: any }> {
  return request('/api/scrape/status');
}
