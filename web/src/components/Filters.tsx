// components/Filters.tsx
import type { ListingsParams } from '../api';

interface FiltersProps {
  filters: ListingsParams;
  onChange: (filters: ListingsParams) => void;
}

export function Filters({ filters, onChange }: FiltersProps) {
  const handleChange = (key: keyof ListingsParams, value: any) => {
    onChange({
      ...filters,
      [key]: value,
      page: 1, // Reset to first page when filters change
    });
  };
  
  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <h3 className="text-white font-medium mb-4">Filters</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Max Price */}
        <div>
          <label className="block text-sm text-slate-400 mb-1">Max Price (EUR)</label>
          <input
            type="number"
            placeholder="Any"
            value={filters.max_price || ''}
            onChange={(e) => handleChange('max_price', e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
        
        {/* Min Rooms */}
        <div>
          <label className="block text-sm text-slate-400 mb-1">Min Rooms</label>
          <select
            value={filters.min_rooms || ''}
            onChange={(e) => handleChange('min_rooms', e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">Any</option>
            <option value="1">1+</option>
            <option value="2">2+</option>
            <option value="3">3+</option>
            <option value="4">4+</option>
            <option value="5">5+</option>
          </select>
        </div>
        
        {/* Min Score */}
        <div>
          <label className="block text-sm text-slate-400 mb-1">Min Score</label>
          <select
            value={filters.min_score || ''}
            onChange={(e) => handleChange('min_score', e.target.value ? Number(e.target.value) : undefined)}
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">Any</option>
            <option value="50">50+</option>
            <option value="60">60+</option>
            <option value="70">70+</option>
            <option value="80">80+</option>
            <option value="90">90+</option>
          </select>
        </div>
        
        {/* Sort By */}
        <div>
          <label className="block text-sm text-slate-400 mb-1">Sort By</label>
          <select
            value={`${filters.sort_by || 'score'}-${filters.sort_order || 'desc'}`}
            onChange={(e) => {
              const [sortBy, sortOrder] = e.target.value.split('-') as [ListingsParams['sort_by'], ListingsParams['sort_order']];
              onChange({
                ...filters,
                sort_by: sortBy,
                sort_order: sortOrder,
              });
            }}
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="score-desc">Score (High to Low)</option>
            <option value="score-asc">Score (Low to High)</option>
            <option value="price-asc">Price (Low to High)</option>
            <option value="price-desc">Price (High to Low)</option>
            <option value="date-desc">Newest First</option>
            <option value="eur_per_m2-asc">EUR/m2 (Low to High)</option>
          </select>
        </div>
      </div>
      
      {/* Only Analyzed Toggle — hidden for now; backend param still exists if needed later */}
      {/*
      <div className="mt-4 flex items-center gap-2">
        <input
          type="checkbox"
          id="only-analyzed"
          checked={filters.only_analyzed || false}
          onChange={(e) => handleChange('only_analyzed', e.target.checked)}
          className="w-4 h-4 bg-slate-700 border-slate-600 rounded focus:ring-blue-500"
        />
        <label htmlFor="only-analyzed" className="text-sm text-slate-400">
          Only show analyzed listings
        </label>
      </div>
      */}
    </div>
  );
}
