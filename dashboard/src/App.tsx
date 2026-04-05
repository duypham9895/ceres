import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { CrawlStatusProvider } from './context/CrawlStatusContext';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Banks from './pages/Banks';
import BankDetail from './pages/BankDetail';
import LoanPrograms from './pages/LoanPrograms';
import CrawlLogs from './pages/CrawlLogs';
import Strategies from './pages/Strategies';
import Recommendations from './pages/Recommendations';
import Jobs from './pages/Jobs';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#666' }}>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}

function NotFound() {
  return (
    <div style={{ padding: '4rem', textAlign: 'center' }}>
      <h1 style={{ fontSize: '3rem', marginBottom: '1rem' }}>404</h1>
      <p style={{ color: '#888', marginBottom: '2rem' }}>Page not found</p>
      <a href="/" style={{ color: '#3b82f6' }}>← Back to Overview</a>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <CrawlStatusProvider>
            <Layout>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/banks" element={<Banks />} />
                <Route path="/banks/:id" element={<BankDetail />} />
                <Route path="/programs" element={<LoanPrograms />} />
                <Route path="/logs" element={<CrawlLogs />} />
                <Route path="/strategies" element={<Strategies />} />
                <Route path="/recommendations" element={<Recommendations />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Layout>
            <Toaster position="top-right" richColors />
          </CrawlStatusProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
