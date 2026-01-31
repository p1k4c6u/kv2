// components/ScoreBar.tsx

interface ScoreBarProps {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
}

export function ScoreBar({ score, size = 'md' }: ScoreBarProps) {
  if (score === null) {
    return (
      <span className="text-slate-500 text-sm">Not analyzed</span>
    );
  }
  
  const percentage = Math.min(100, Math.max(0, score));
  
  // Color based on score
  let colorClass = 'bg-red-500';
  if (score >= 70) colorClass = 'bg-green-500';
  else if (score >= 50) colorClass = 'bg-yellow-500';
  else if (score >= 30) colorClass = 'bg-orange-500';
  
  const heights = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  };
  
  const widths = {
    sm: 'w-16',
    md: 'w-24',
    lg: 'w-32',
  };
  
  return (
    <div className="flex items-center gap-2">
      <span className={`font-bold ${score >= 70 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
        {score}
      </span>
      <div className={`${widths[size]} ${heights[size]} bg-slate-700 rounded-full overflow-hidden`}>
        <div 
          className={`${heights[size]} ${colorClass} rounded-full transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
