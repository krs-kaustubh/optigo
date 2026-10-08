"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { dedupeRoutes, summarizeLegs, mergeEdges, DedupedRoute } from "@/lib/route-utils";
import { Zap, Ruler, Tag } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ResultsListProps {
  from: number;
  to: number;
  live: boolean;
  selectedRoute: DedupedRoute | null;
  onSelectRoute: (route: DedupedRoute | null) => void;
}

export default function ResultsList({ from, to, live, selectedRoute, onSelectRoute }: ResultsListProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['compare', from, to, live],
    queryFn: () => api.compareRoutes(from, to, live),
    retry: 1
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        {[1,2,3].map(i => (
          <div key={i} className="animate-pulse bg-[var(--surface)] border border-[var(--line)] rounded-[20px] h-36 w-full"></div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[var(--surface)] border border-[var(--line)] p-6 rounded-[24px] text-center shadow-sm">
        <p className="text-[var(--orange)] font-medium mb-2 text-lg">Error finding routes</p>
        <p className="text-[var(--ink-muted)]">{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-[var(--surface)] border border-[var(--line)] p-6 rounded-[24px] text-center shadow-sm">
        <p className="text-[var(--ink)] font-medium">No route found between these stations.</p>
      </div>
    );
  }

  const routes = dedupeRoutes(data);

  return (
    <div className="flex flex-col gap-4">
      <AnimatePresence>
        {routes.map((route, i) => (
          <RouteCard 
            key={route.path.join('|')} 
            route={route} 
            index={i} 
            isSelected={selectedRoute?.path.join('|') === route.path.join('|')}
            onClick={() => onSelectRoute(route)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

function RouteCard({ route, index, isSelected, onClick }: { route: DedupedRoute, index: number, isSelected: boolean, onClick: () => void }) {
  const mergedLegs = mergeEdges(route.edges);
  const summary = summarizeLegs(mergedLegs);
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      onClick={onClick}
      className={`relative p-5 rounded-[24px] cursor-pointer transition-all ${isSelected ? 'bg-[var(--surface)] border-[var(--green)] border-2 shadow-md' : 'bg-[var(--surface)] border border-[var(--line)] hover:border-[var(--ink-muted)] shadow-sm'}`}
    >
      <div className="flex justify-between items-start mb-5">
        <div className="flex flex-wrap gap-2">
          {route.badges.map(b => (
            <span key={b} className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${b === 'Fastest' ? 'bg-[#FFF3E0] text-[#E65100] dark:bg-[#E65100]/20 dark:text-[#FFB74D]' : b === 'Shortest' ? 'bg-[#E3F2FD] text-[#1565C0] dark:bg-[#1565C0]/20 dark:text-[#64B5F6]' : 'bg-[var(--green-soft)] text-[var(--green)]'}`}>
              {b === 'Fastest' && <Zap className="w-3.5 h-3.5" />}
              {b === 'Shortest' && <Ruler className="w-3.5 h-3.5" />}
              {b === 'Cost' && <Tag className="w-3.5 h-3.5" />}
              {b === 'Cost' ? 'Cheapest' : b}
            </span>
          ))}
        </div>
      </div>
      
      <div className="flex justify-between items-end mb-5 font-mono">
        <div className="text-4xl font-bold tracking-tight text-[var(--ink)] leading-none">{route.totals.time}<span className="text-base text-[var(--ink-muted)] font-sans font-medium ml-1">min</span></div>
        <div className="text-xl font-semibold text-[var(--ink)]">₹{route.totals.real_fare}</div>
        <div className="text-lg text-[var(--ink-muted)]">{route.totals.distance.toFixed(1)} km</div>
      </div>

      <div className="w-full h-2 rounded-full overflow-hidden flex gap-0.5 mb-3 bg-[var(--surface-2)]">
        {mergedLegs.map((leg, i) => (
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${(leg.count / route.edges.length) * 100}%` }}
            transition={{ duration: 0.8, delay: 0.2 + (i * 0.1) }}
            key={i} 
            className={`h-full ${leg.mode === 'train' ? 'bg-[var(--green)]' : leg.mode === 'metro' ? 'bg-[var(--orange)]' : 'bg-[var(--ink-muted)]'}`}
          />
        ))}
      </div>
      <p className="text-xs text-[var(--ink-muted)] font-medium uppercase tracking-wider">{summary}</p>
    </motion.div>
  );
}
