"use client";
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { Sun, Moon, Route as RouteIcon } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function Header() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-line bg-background/80 backdrop-blur-md">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 group">
          <RouteIcon className="w-5 h-5 text-primary" />
          <span className="font-serif font-bold text-lg tracking-tight group-hover:text-primary transition-colors">
            Optigo
          </span>
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/plan" className="text-sm font-medium hover:text-primary transition-colors hidden sm:block">
            Plan a route
          </Link>
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 rounded-full hover:bg-surface-2 transition-colors relative w-8 h-8 flex items-center justify-center overflow-hidden"
            aria-label="Toggle theme"
          >
            {mounted && (
              <>
                <Moon
                  className={`w-4 h-4 absolute transition-all duration-300 ${
                    theme === "dark" ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-50"
                  }`}
                />
                <Sun
                  className={`w-4 h-4 absolute transition-all duration-300 ${
                    theme === "dark" ? "opacity-0 rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
                  }`}
                />
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
