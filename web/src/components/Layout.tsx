// components/Layout.tsx
import { Link, useNavigate } from 'react-router-dom';
import { clearToken, isAuthenticated } from '../api';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const navigate = useNavigate();
  
  const handleLogout = () => {
    clearToken();
    navigate('/login');
  };
  
  if (!isAuthenticated()) {
    return <>{children}</>;
  }
  
  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-white flex items-center gap-2">
            <span className="text-blue-500">KV</span>
            <span>Listings</span>
          </Link>
          
          <nav className="flex items-center gap-4">
            <Link 
              to="/" 
              className="text-slate-300 hover:text-white transition-colors"
            >
              Dashboard
            </Link>
            <button
              onClick={handleLogout}
              className="text-slate-400 hover:text-white transition-colors text-sm"
            >
              Logout
            </button>
          </nav>
        </div>
      </header>
      
      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
