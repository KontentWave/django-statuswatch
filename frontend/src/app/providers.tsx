import { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

const qc = new QueryClient();

export default function Providers({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={qc}>
      {children}
      <Toaster richColors expand position="top-right" />
    </QueryClientProvider>
  );
}
