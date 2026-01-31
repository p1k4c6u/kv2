// components/StatsCard.tsx
import { Stats } from '../api';

interface StatsCardProps {
  stats: Stats | null;
  loading?: boolean;
}

export function StatsCard({ stats, loading }: StatsCardProps) {
  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-2"></div>
        <div className="h-8 bg-slate-700 rounded w-1/2"></div>
      </div>
    );
  }
  
  if (!stats) return null;
  
  const formatNumber = (n: number | null) => {
    if (n === null) return '-';
    return new Intl.NumberFormat('en-EU').format(Math.round(n));
  };
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <p className="text-sm text-slate-400">Total Listings</p>
        <p className="text-2xl font-bold text-white">{formatNumber(stats.total_listings)}</p>
      </div>
      
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <p className="text-sm text-slate-400">Analyzed</p>
        <p className="text-2xl font-bold text-white">
          {formatNumber(stats.analyzed_count)}
          <span className="text-sm text-slate-500 ml-1">
            ({stats.total_listings > 0 ? Math.round((stats.analyzed_count / stats.total_listings) * 100) : 0}%)
          </span>
        </p>
      </div>
      
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <p className="text-sm text-slate-400">Avg Score</p>
        <p className="text-2xl font-bold text-white">
          {stats.avg_score ? stats.avg_score.toFixed(1) : '-'}
          <span className="text-sm text-slate-500">/100</span>
        </p>
      </div>
      
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <p className="text-sm text-slate-400">Avg Price</p>
        <p className="text-2xl font-bold text-white">
          {stats.avg_price ? `${formatNumber(stats.avg_price)} EUR` : '-'}
        </p>
      </div>
    </div>
  );
}
