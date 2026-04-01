import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Building2, Coins, ScrollText, Zap, Lightbulb } from 'lucide-react';
import { useCrawlStatus } from '../context/CrawlStatusContext';
import CrawlPipelineMonitor from './CrawlPipelineMonitor';
import CrawlToast from './CrawlToast';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', Icon: LayoutDashboard },
  { path: '/banks', label: 'Banks', Icon: Building2 },
  { path: '/programs', label: 'Loan Programs', Icon: Coins },
  { path: '/logs', label: 'Crawl Logs', Icon: ScrollText },
  { path: '/strategies', label: 'Strategies', Icon: Zap },
  { path: '/recommendations', label: 'Recommendations', Icon: Lightbulb },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isConnected } = useCrawlStatus();

  return (
    <div className="flex h-screen bg-bg-primary">
      <aside className="w-56 bg-bg-card border-r border-border flex flex-col shrink-0">
        <div className="p-5 border-b border-border">
          <h1 className="text-lg font-bold tracking-widest text-text-heading">CERES</h1>
          <p className="text-[11px] text-text-muted tracking-wide">Financial Intelligence</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV_ITEMS.map(({ path, label, Icon }) => {
            const active = location.pathname === path;
            return (
              <Link key={path} to={path}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] transition-colors ${
                  active
                    ? 'bg-bg-hover text-text-heading font-medium border border-border-light'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-body'
                }`}>
                <Icon size={16} className={active ? 'text-accent-light' : 'opacity-60'} />
                {label}
              </Link>
            );
          })}
        </nav>
        <CrawlPipelineMonitor />
        <div className="p-4 border-t border-border">
          <div className={`flex items-center gap-1.5 text-[11px] ${isConnected ? 'text-text-muted' : 'text-error'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-success animate-pulse-green' : 'bg-error'}`} />
            {isConnected ? 'WebSocket Connected' : 'Reconnecting...'}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">{children}</main>
      <CrawlToast />
    </div>
  );
}
