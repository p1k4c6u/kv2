// pages/Dashboard.tsx
import { useState, useEffect } from 'react';
import { 
  getListings, 
  getStats, 
  triggerAnalysis, 
  getAnalysisStatus,
  triggerScrape,
  getScrapeStatus,
} from '../api';
import type { ListingSummary, Stats, ListingsParams } from '../api';
import { ListingCard } from '../components/ListingCard';
import { Filters } from '../components/Filters';
import { StatsCard } from '../components/StatsCard';

const SCRAPE_AREAS = ['tallinn', 'tartu', 'harjumaa', 'jõgevamaa'];

export function DashboardPage() {
  const [listings, setListings] = useState<ListingSummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [scrapeArea, setScrapeArea] = useState('tallinn');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<ListingsParams>({
    page: 1,
    per_page: 20,
    sort_by: 'score',
    sort_order: 'desc',
  });
  
  // Load data
  useEffect(() => {
    loadData();
  }, [filters]);
  
  // Check analysis status periodically
  useEffect(() => {
    if (analyzing) {
      const interval = setInterval(async () => {
        const status = await getAnalysisStatus();
        if (!status.running) {
          setAnalyzing(false);
          loadData();
          setMessage({ type: 'success', text: 'Analysis complete!' });
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [analyzing]);

  // Check scrape status periodically
  useEffect(() => {
    if (scraping) {
      const interval = setInterval(async () => {
        const status = await getScrapeStatus();
        if (!status.running) {
          setScraping(false);
          loadData();
          const result = status.last_result;
          if (result?.status === 'error') {
            setMessage({ type: 'error', text: `Scrape failed: ${result.error}` });
          } else {
            setMessage({ type: 'success', text: `Scrape complete — ${result?.listings_found ?? 0} listings found.` });
          }
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [scraping]);
  
  const loadData = async () => {
    setLoading(true);
    try {
      const [listingsRes, statsRes, analysisStatus, scrapeStatus] = await Promise.all([
        getListings(filters),
        getStats(),
        getAnalysisStatus(),
        getScrapeStatus(),
      ]);
      setListings(listingsRes.listings);
      setTotal(listingsRes.total);
      setStats(statsRes);
      setAnalyzing(analysisStatus.running);
      setScraping(scrapeStatus.running);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleAnalyze = async () => {
    try {
      setMessage(null);
      const result = await triggerAnalysis();
      if (result.status === 'started') {
        setAnalyzing(true);
        setMessage({ type: 'success', text: result.message });
      } else if (result.status === 'running') {
        setMessage({ type: 'error', text: result.message });
      } else {
        setMessage({ type: 'success', text: result.message });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to start analysis' });
    }
  };

  const handleScrape = async () => {
    try {
      setMessage(null);
      const result = await triggerScrape(scrapeArea);
      if (result.status === 'started') {
        setScraping(true);
        setMessage({ type: 'success', text: result.message });
      } else if (result.status === 'running') {
        setMessage({ type: 'error', text: result.message });
      } else {
        setMessage({ type: 'error', text: result.message });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to start scrape' });
    }
  };
  
  const totalPages = Math.ceil(total / (filters.per_page || 20));
  
  return (
    <div className="space-y-6">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <div className="flex items-center gap-3">
          {/* Scrape: area selector + button */}
          <select
            value={scrapeArea}
            onChange={(e) => setScrapeArea(e.target.value)}
            disabled={scraping}
            className="bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {SCRAPE_AREAS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded transition-colors flex items-center gap-2"
          >
            {scraping ? (
              <>
                <span className="animate-spin">&#9696;</span>
                Scraping...
              </>
            ) : (
              'Scrape'
            )}
          </button>

          {/* Analyze button */}
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded transition-colors flex items-center gap-2"
          >
            {analyzing ? (
              <>
                <span className="animate-spin">&#9696;</span>
                Analyzing...
              </>
            ) : (
              'Analyze New'
            )}
          </button>
        </div>
      </div>
      
      {/* Messages */}
      {message && (
        <div className={`px-4 py-2 rounded ${
          message.type === 'success' 
            ? 'bg-green-500/10 border border-green-500/50 text-green-400'
            : 'bg-red-500/10 border border-red-500/50 text-red-400'
        }`}>
          {message.text}
        </div>
      )}
      
      {/* Stats */}
      <StatsCard stats={stats} loading={loading && !stats} />
      
      {/* Filters */}
      <Filters filters={filters} onChange={setFilters} />
      
      {/* Listings */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Listings {total > 0 && <span className="text-slate-400 font-normal">({total})</span>}
          </h2>
        </div>
        
        {loading && listings.length === 0 ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-slate-800 rounded-lg p-4 border border-slate-700 animate-pulse">
                <div className="h-4 bg-slate-700 rounded w-2/3 mb-2"></div>
                <div className="h-6 bg-slate-700 rounded w-1/4 mb-2"></div>
                <div className="h-3 bg-slate-700 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        ) : listings.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-8 border border-slate-700 text-center">
            <p className="text-slate-400">No listings found matching your filters.</p>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {listings.map((listing) => (
                <ListingCard key={listing.listing_id} listing={listing} />
              ))}
            </div>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setFilters({ ...filters, page: (filters.page || 1) - 1 })}
                  disabled={filters.page === 1}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded transition-colors"
                >
                  Previous
                </button>
                <span className="text-slate-400 px-4">
                  Page {filters.page || 1} of {totalPages}
                </span>
                <button
                  onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })}
                  disabled={(filters.page || 1) >= totalPages}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
