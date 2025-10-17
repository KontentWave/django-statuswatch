import { api } from '@/lib/api';
import { STRIPE_PK } from '@/lib/config';
import { toast } from 'sonner';

export default function Home() {
  const loginDemo = async () => {
    try {
      const { data } = await api.post('/auth/token/', {
        username: 'jwt',
        password: 'jwtpass123',
      });
      localStorage.setItem('jwt', data.access);
      toast.success('Logged in (jwt)');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? 'Login failed');
    }
  };

  const ping = async () => {
    const { data } = await api.get('/ping/');
    toast.info(`ping: ${JSON.stringify(data)}`);
  };

  const pay = async () => {
    if (!STRIPE_PK) {
      toast.error('Missing VITE_STRIPE_PUBLIC_KEY');
      return;
    }
    const { data } = await api.post('/pay/create-checkout-session/', {
      amount: 500,
      currency: 'usd',
      name: 'Demo',
    });
    if (data?.url) {
      window.location.href = data.url;
    } else {
      toast.error('No checkout URL from backend');
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 p-6">
      <div className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-3xl font-bold">StatusWatch (dev)</h1>

        <div className="flex gap-3">
          <button
            onClick={loginDemo}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
            title="uses /api/auth/token/"
          >
            Login (jwt/jwtpass123)
          </button>

          <button
            onClick={ping}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
          >
            Ping API
          </button>

          <button
            onClick={pay}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500"
          >
            Pay $5
          </button>
        </div>

        <p className="text-sm text-neutral-400">
          API base: <code>{import.meta.env.VITE_API_BASE}</code>
        </p>
      </div>
    </div>
  );
}
