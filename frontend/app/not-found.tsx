import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Route } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 text-center bg-[var(--bg)] min-h-[70vh]">
      <Route className="w-16 h-16 text-[var(--ink-muted)] mb-6 opacity-50" />
      <h2 className="font-serif text-4xl font-bold text-[var(--ink)] mb-4 tracking-tight">Dead end</h2>
      <p className="text-[var(--ink-muted)] mb-8 max-w-md">We couldn't find the page you're looking for. Let's get you back on track.</p>
      <Link href="/" className="inline-flex h-[52px] px-8 text-lg items-center justify-center rounded-full font-medium text-white bg-[var(--green)] hover:bg-[var(--green)]/90 shadow-md transition-all active:scale-95">
        Return home
      </Link>
    </div>
  );
}
