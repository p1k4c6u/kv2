// pages/Login.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api';

export function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      await login(password);
      navigate('/');
    } catch (err) {
      setError('Invalid password');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">
            <span className="text-blue-500">KV</span> Listings
          </h1>
          <p className="text-slate-400 mt-2">Estonian Real Estate Dashboard</p>
        </div>
        
        <form onSubmit={handleSubmit} className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-xl font-semibold text-white mb-4">Login</h2>
          
          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-2 rounded mb-4">
              {error}
            </div>
          )}
          
          <div className="mb-4">
            <label htmlFor="password" className="block text-sm text-slate-400 mb-1">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              placeholder="Enter password"
              required
              autoFocus
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded transition-colors"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}
