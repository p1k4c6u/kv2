// pages/Listing.tsx
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getListing, ListingDetail } from '../api';
import { ScoreBar } from '../components/ScoreBar';

export function ListingPage() {
  const { id } = useParams<{ id: string }>();
  const [listing, setListing] = useState<ListingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (!id) return;
    
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getListing(id);
        setListing(data);
      } catch (err) {
        setError('Failed to load listing');
      } finally {
        setLoading(false);
      }
    };
    
    load();
  }, [id]);
  
  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-700 rounded w-1/3"></div>
        <div className="h-64 bg-slate-800 rounded"></div>
      </div>
    );
  }
  
  if (error || !listing) {
    return (
      <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-8 rounded text-center">
        <p>{error || 'Listing not found'}</p>
        <Link to="/" className="text-blue-400 hover:underline mt-2 inline-block">
          Back to Dashboard
        </Link>
      </div>
    );
  }
  
  const formatPrice = (price: number | null) => {
    if (!price) return 'Price N/A';
    return new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(price);
  };
  
  const formatDate = (date: string | null) => {
    if (!date) return '-';
    return new Date(date).toLocaleDateString('en-EU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };
  
  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/" className="text-blue-400 hover:underline text-sm flex items-center gap-1">
        &larr; Back to Dashboard
      </Link>
      
      {/* Header */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">
              {listing.title || 'Untitled Listing'}
            </h1>
            <p className="text-3xl font-bold text-white">
              {formatPrice(listing.price_eur)}
              {listing.eur_per_m2 && (
                <span className="text-lg text-slate-400 font-normal ml-2">
                  ({listing.eur_per_m2} EUR/m2)
                </span>
              )}
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-400 mb-1">Score</div>
            <ScoreBar score={listing.score} size="lg" />
          </div>
        </div>
        
        {listing.url && (
          <a 
            href={listing.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-blue-400 hover:underline text-sm"
          >
            View on kv.ee &rarr;
          </a>
        )}
      </div>
      
      {/* Details Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Property Details */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Property Details</h2>
          <dl className="space-y-3">
            {[
              { label: 'Rooms', value: listing.rooms },
              { label: 'Bedrooms', value: listing.bedrooms },
              { label: 'Total Area', value: listing.total_area ? `${listing.total_area} m2` : null },
              { label: 'Floors', value: listing.floors },
              { label: 'Year Built', value: listing.year_built },
              { label: 'Condition', value: listing.condition },
              { label: 'Energy Class', value: listing.energy_class },
              { label: 'Last Seen', value: formatDate(listing.last_seen_at) },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between">
                <dt className="text-slate-400">{label}</dt>
                <dd className="text-white font-medium">{value || '-'}</dd>
              </div>
            ))}
          </dl>
        </div>
        
        {/* AI Analysis */}
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">AI Analysis</h2>
          
          {listing.score !== null ? (
            <div className="space-y-4">
              {listing.summary && (
                <p className="text-slate-300">{listing.summary}</p>
              )}
              
              {listing.breakdown && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-slate-400 mt-4">Score Breakdown</h3>
                  {[
                    { label: 'Price Value', value: listing.breakdown.price_value, max: 25 },
                    { label: 'Location', value: listing.breakdown.location, max: 20 },
                    { label: 'Condition', value: listing.breakdown.condition, max: 20 },
                    { label: 'Size & Layout', value: listing.breakdown.size_layout, max: 15 },
                    { label: 'Investment Potential', value: listing.breakdown.investment_potential, max: 20 },
                  ].map(({ label, value, max }) => (
                    <div key={label} className="flex items-center gap-3">
                      <span className="text-slate-400 text-sm w-40">{label}</span>
                      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${((value || 0) / max) * 100}%` }}
                        />
                      </div>
                      <span className="text-white text-sm w-12 text-right">
                        {value ?? '-'}/{max}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="text-xs text-slate-500 mt-4">
                Analyzed: {formatDate(listing.analyzed_at)}
                {listing.model && ` | Model: ${listing.model}`}
              </div>
            </div>
          ) : (
            <p className="text-slate-400">This listing has not been analyzed yet.</p>
          )}
        </div>
      </div>
      
      {/* Description */}
      {listing.description && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Description</h2>
          <p className="text-slate-300 whitespace-pre-wrap">{listing.description}</p>
        </div>
      )}
    </div>
  );
}
