"use client";
import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 text-center bg-[var(--bg)] min-h-[70vh]">
      <AlertTriangle className="w-16 h-16 text-[var(--orange)] mb-6" />
      <h2 className="font-serif text-4xl font-bold text-[var(--ink)] mb-4 tracking-tight">Something went wrong</h2>
      <p className="text-[var(--ink-muted)] mb-8 max-w-md">We hit a snag on our end. Please try again.</p>
      <Button onClick={() => reset()} size="lg" className="bg-[var(--green)] hover:bg-[var(--green)]/90 text-white shadow-md">
        Try again
      </Button>
    </div>
  );
}
