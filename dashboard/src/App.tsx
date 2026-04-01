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

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });

export default function App() {
  return (
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
            </Routes>
          </Layout>
          <Toaster position="top-right" richColors />
        </CrawlStatusProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
