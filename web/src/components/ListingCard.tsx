// components/ListingCard.tsx
import { Link } from 'react-router-dom';
import type { ListingSummary } from '../api';
import { ScoreBar } from './ScoreBar';

interface ListingCardProps {
  listing: ListingSummary;
}

export function ListingCard({ listing }: ListingCardProps) {
  const formatPrice = (price: number | null) => {
    if (!price) return 'Price N/A';
    return new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(price);
  };
  
  return (
    <Link 
      to={`/listing/${listing.listing_id}`}
      className="block bg-slate-800 rounded-lg p-4 hover:bg-slate-750 transition-colors border border-slate-700 hover:border-slate-600"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-medium truncate mb-1">
            {listing.title || 'Untitled Listing'}
          </h3>
          
          <div className="flex items-center gap-4 text-sm text-slate-400 mb-2">
            <span className="text-lg font-semibold text-white">
              {formatPrice(listing.price_eur)}
            </span>
            {listing.eur_per_m2 && (
              <span className="text-slate-500">
                {listing.eur_per_m2} EUR/m2
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-4 text-sm text-slate-400">
            {listing.rooms && (
              <span>{listing.rooms} rooms</span>
            )}
            {listing.total_area && (
              <span>{listing.total_area} m2</span>
            )}
          </div>
          
          {listing.summary && (
            <p className="text-sm text-slate-400 mt-2 line-clamp-2">
              {listing.summary}
            </p>
          )}
        </div>
        
        <div className="flex-shrink-0">
          <ScoreBar score={listing.score} size="md" />
        </div>
      </div>
    </Link>
  );
}
