import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useCrawlStatus } from '../context/CrawlStatusContext';
import CrawlPipelineMonitor from './CrawlPipelineMonitor';
import CrawlToast from './CrawlToast';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/banks', label: 'Banks', icon: '🏦' },
  { path: '/programs', label: 'Loan Programs', icon: '💰' },
  { path: '/logs', label: 'Crawl Logs', icon: '📋' },
  { path: '/strategies', label: 'Strategies', icon: '🎯' },
  { path: '/recommendations', label: 'Recommendations', icon: '💡' },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isConnected } = useCrawlStatus();

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b">
          <h1 className="text-xl font-bold text-gray-900">CERES</h1>
          <p className="text-sm text-gray-500">Ops Dashboard</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map(({ path, label, icon }) => (
            <Link key={path} to={path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}>
              <span>{icon}</span>{label}
            </Link>
          ))}
        </nav>
        <CrawlPipelineMonitor />
        <div className="p-4 border-t">
          <div className={`flex items-center gap-2 text-xs ${isConnected ? 'text-green-600' : 'text-red-500'}`}>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            {isConnected ? 'Connected' : 'Reconnecting...'}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">{children}</main>
      <CrawlToast />
    </div>
  );
}
