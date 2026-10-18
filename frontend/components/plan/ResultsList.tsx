"use client";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { 
  buildUnifiedRoutes, 
  summarizeLegs, 
  mergeEdges, 
  DedupedRoute, 
  ComparisonSummary 
} from "@/lib/route-utils";
import { Zap, Ruler, Tag, Car, Navigation, ShieldCheck, ChevronRight, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ResultsListProps {
  from: number;
  to: number;
  live: boolean;
  selectedRoute: DedupedRoute | null;
  onSelectRoute: (route: DedupedRoute | null) => void;
}

export default function ResultsList({ from, to, live, selectedRoute, onSelectRoute }: ResultsListProps) {
  const [modeFilter, setModeFilter] = useState<'all' | 'transit' | 'cab'>('all');

  const { data: transitData, isLoading: isTransitLoading, error: transitError } = useQuery({
    queryKey: ['compare', from, to, live],
    queryFn: () => api.compareRoutes(from, to, live),
    retry: 1
  });

  const { data: cabData, isLoading: isCabLoading } = useQuery({
    queryKey: ['cabs', from, to],
    queryFn: () => api.getCabEstimates(from, to),
    retry: 1,
    enabled: Boolean(from && to && from !== to)
  });

  const { routes, summary } = useMemo(() => {
    return buildUnifiedRoutes(transitData || [], cabData);
  }, [transitData, cabData]);

  const filteredRoutes = useMemo(() => {
    if (modeFilter === 'transit') return routes.filter(r => !r.isCab);
    if (modeFilter === 'cab') return routes.filter(r => r.isCab);
    return routes;
  }, [routes, modeFilter]);

  if (isTransitLoading && isCabLoading) {
    return (
      <div className="flex flex-col gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse bg-[var(--surface)] border border-[var(--line)] rounded-[24px] h-40 w-full" />
        ))}
      </div>
    );
  }

  if (transitError && (!cabData || cabData.estimates.length === 0)) {
    return (
      <div className="bg-[var(--surface)] border border-[var(--line)] p-6 rounded-[24px] text-center shadow-sm">
        <p className="text-[var(--orange)] font-medium mb-2 text-lg">Error finding routes</p>
        <p className="text-[var(--ink-muted)]">{transitError instanceof Error ? transitError.message : "Unknown error"}</p>
      </div>
    );
  }

  if (routes.length === 0) {
    return (
      <div className="bg-[var(--surface)] border border-[var(--line)] p-6 rounded-[24px] text-center shadow-sm">
        <p className="text-[var(--ink)] font-medium">No route found between these stations.</p>
      </div>
    );
  }

  const transitCount = routes.filter(r => !r.isCab).length;
  const cabCount = routes.filter(r => r.isCab).length;

  return (
    <div className="flex flex-col gap-5">
      {/* 1. Multimodal Comparison Highlights (Time, Cheapest, Distance) */}
      {summary && (
        <ComparisonMetricStrip 
          summary={summary} 
          routes={routes}
          onSelectRoute={onSelectRoute}
        />
      )}

      {/* 2. Mode Filter Tabs */}
      <div className="flex items-center gap-1.5 p-1 bg-[var(--surface-2)] rounded-full border border-[var(--line)] text-xs font-semibold">
        <button
          onClick={() => setModeFilter('all')}
          className={`flex-1 py-1.5 px-3 rounded-full transition-all text-center ${modeFilter === 'all' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'}`}
        >
          All Options ({routes.length})
        </button>
        <button
          onClick={() => setModeFilter('transit')}
          className={`flex-1 py-1.5 px-3 rounded-full transition-all text-center flex items-center justify-center gap-1 ${modeFilter === 'transit' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'}`}
        >
          Train & Metro ({transitCount})
        </button>
        <button
          onClick={() => setModeFilter('cab')}
          className={`flex-1 py-1.5 px-3 rounded-full transition-all text-center flex items-center justify-center gap-1 ${modeFilter === 'cab' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'}`}
        >
          Cabs & Auto ({cabCount})
        </button>
      </div>

      {/* 3. Unified Routes List */}
      <div className="flex flex-col gap-4">
        <AnimatePresence>
          {filteredRoutes.map((route, i) => (
            route.isCab ? (
              <CabRouteCard
                key="cab-route"
                route={route}
                index={i}
                isSelected={selectedRoute?.isCab === true}
                onClick={() => onSelectRoute(route)}
              />
            ) : (
              <TransitRouteCard 
                key={route.path.join('|')} 
                route={route} 
                index={i} 
                isSelected={!selectedRoute?.isCab && selectedRoute?.path.join('|') === route.path.join('|')}
                onClick={() => onSelectRoute(route)}
              />
            )
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ComparisonMetricStrip({ 
  summary, 
  routes,
  onSelectRoute 
}: { 
  summary: ComparisonSummary; 
  routes: DedupedRoute[];
  onSelectRoute: (r: DedupedRoute) => void;
}) {
  const fastestRoute = routes.find(r => summary.fastest.winner === 'cab' ? r.isCab : (!r.isCab && r.totals.time === summary.fastest.time));
  const cheapestRoute = routes.find(r => summary.cheapest.winner === 'cab' ? r.isCab : (!r.isCab && r.totals.real_fare === summary.cheapest.fare));
  const shortestRoute = routes.find(r => summary.shortest.winner === 'cab' ? r.isCab : (!r.isCab && Math.abs(r.totals.distance - summary.shortest.distance) < 0.2));

  return (
    <div className="grid grid-cols-3 gap-2 p-3 bg-[var(--surface)] border border-[var(--line)] rounded-[20px] shadow-sm">
      {/* Fastest Card */}
      <button 
        onClick={() => fastestRoute && onSelectRoute(fastestRoute)}
        className="flex flex-col items-start p-2 rounded-[14px] hover:bg-[var(--surface-2)] transition-colors text-left"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--orange)] flex items-center gap-1 mb-1">
          <Zap className="w-3 h-3 fill-[var(--orange)]" /> Fastest
        </span>
        <span className="text-sm font-bold text-[var(--ink)] font-mono">
          {summary.fastest.time}m
        </span>
        <span className="text-[11px] text-[var(--ink-muted)] font-medium leading-tight mt-0.5">
          {summary.fastest.winner === 'cab' ? 'Cab' : 'Train'}
          {summary.fastest.diffMinutes > 0 ? ` (-${summary.fastest.diffMinutes}m)` : ''}
        </span>
      </button>

      {/* Cheapest Card */}
      <button 
        onClick={() => cheapestRoute && onSelectRoute(cheapestRoute)}
        className="flex flex-col items-start p-2 rounded-[14px] hover:bg-[var(--surface-2)] transition-colors text-left border-x border-[var(--line)] px-2.5"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--green)] flex items-center gap-1 mb-1">
          <Tag className="w-3 h-3" /> Cheapest
        </span>
        <span className="text-sm font-bold text-[var(--ink)] font-mono">
          ₹{summary.cheapest.fare}
        </span>
        <span className="text-[11px] text-[var(--ink-muted)] font-medium leading-tight mt-0.5">
          {summary.cheapest.winner === 'train' ? 'Train' : 'Cab'}
          {summary.cheapest.savings > 0 ? ` (-₹${summary.cheapest.savings})` : ''}
        </span>
      </button>

      {/* Shortest Card */}
      <button 
        onClick={() => shortestRoute && onSelectRoute(shortestRoute)}
        className="flex flex-col items-start p-2 rounded-[14px] hover:bg-[var(--surface-2)] transition-colors text-left"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#0284C7] dark:text-[#38BDF8] flex items-center gap-1 mb-1">
          <Ruler className="w-3 h-3" /> Shortest
        </span>
        <span className="text-sm font-bold text-[var(--ink)] font-mono">
          {summary.shortest.distance.toFixed(1)} km
        </span>
        <span className="text-[11px] text-[var(--ink-muted)] font-medium leading-tight mt-0.5">
          {summary.shortest.winner === 'cab' ? 'Road' : 'Rail'}
        </span>
      </button>
    </div>
  );
}

function TransitRouteCard({ route, index, isSelected, onClick }: { route: DedupedRoute; index: number; isSelected: boolean; onClick: () => void }) {
  const mergedLegs = mergeEdges(route.edges);
  const summary = summarizeLegs(mergedLegs);
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      onClick={onClick}
      className={`relative p-5 rounded-[24px] cursor-pointer transition-all ${isSelected ? 'bg-[var(--surface)] border-[var(--green)] border-2 shadow-md ring-2 ring-[var(--green)]/20' : 'bg-[var(--surface)] border border-[var(--line)] hover:border-[var(--ink-muted)] shadow-sm'}`}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="flex flex-wrap gap-2">
          {route.badges.map(b => (
            <span key={b} className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
              b.includes('Fastest') ? 'bg-[#FFF3E0] text-[#E65100] dark:bg-[#E65100]/20 dark:text-[#FFB74D]' : 
              b.includes('Shortest') ? 'bg-[#E0F2FE] text-[#0369A1] dark:bg-[#0369A1]/20 dark:text-[#7DD3FC]' : 
              b.includes('Cheapest') || b === 'Cost' ? 'bg-[var(--green-soft)] text-[var(--green)]' : 
              'bg-[var(--surface-2)] text-[var(--ink-muted)]'
            }`}>
              {b.includes('Fastest') && <Zap className="w-3.5 h-3.5 fill-current" />}
              {b.includes('Shortest') && <Ruler className="w-3.5 h-3.5" />}
              {(b.includes('Cheapest') || b === 'Cost') && <Tag className="w-3.5 h-3.5" />}
              {b === 'Cost' ? 'Cheapest' : b}
            </span>
          ))}
        </div>
        <span className="text-xs font-medium text-[var(--ink-muted)] flex items-center gap-1">
          Transit <ChevronRight className="w-3.5 h-3.5" />
        </span>
      </div>
      
      <div className="flex justify-between items-end mb-4 font-mono">
        <div className="text-3xl font-bold tracking-tight text-[var(--ink)] leading-none">
          {route.totals.time}<span className="text-sm text-[var(--ink-muted)] font-sans font-medium ml-1">min</span>
        </div>
        <div className="text-xl font-bold text-[var(--green)]">
          ₹{route.totals.real_fare}
        </div>
        <div className="text-base text-[var(--ink-muted)]">
          {route.totals.distance.toFixed(1)} km
        </div>
      </div>

      <div className="w-full h-2 rounded-full overflow-hidden flex gap-0.5 mb-3 bg-[var(--surface-2)]">
        {mergedLegs.map((leg, i) => (
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${(leg.count / route.edges.length) * 100}%` }}
            transition={{ duration: 0.6, delay: 0.1 + (i * 0.1) }}
            key={i} 
            className={`h-full ${leg.mode === 'train' ? 'bg-[var(--green)]' : leg.mode === 'metro' ? 'bg-[var(--orange)]' : 'bg-[var(--ink-muted)]'}`}
          />
        ))}
      </div>
      <div className="flex justify-between items-center text-xs">
        <p className="text-[var(--ink-muted)] font-medium uppercase tracking-wider">{summary}</p>
        {route.relativeTimeDiff !== undefined && route.relativeTimeDiff < 0 && (
          <span className="text-[var(--orange)] font-semibold flex items-center gap-1">
            <Zap className="w-3 h-3 fill-current" /> {Math.abs(route.relativeTimeDiff)}m faster than road
          </span>
        )}
      </div>
    </motion.div>
  );
}

function CabRouteCard({ route, index, isSelected, onClick }: { route: DedupedRoute; index: number; isSelected: boolean; onClick: () => void }) {
  const cab = route.cabData;
  if (!cab) return null;

  const lowestFare = Math.min(...cab.estimates.map(e => e.fare_low));
  const highestFare = Math.max(...cab.estimates.map(e => e.fare_high));
  const autoTier = cab.estimates.find(e => e.category === 'auto');
  const cabTier = cab.estimates.find(e => e.category === 'cab_mini' || e.category === 'cab_sedan');

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      onClick={onClick}
      className={`relative p-5 rounded-[24px] cursor-pointer transition-all ${
        isSelected 
          ? 'bg-[var(--surface)] border-[var(--amber)] border-2 shadow-md ring-2 ring-[var(--amber)]/20' 
          : 'bg-[var(--surface)] border border-[var(--amber)]/40 hover:border-[var(--amber)] shadow-sm'
      }`}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="flex flex-wrap gap-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 bg-[#FEF3C7] text-[#B45309] dark:bg-[#78350F]/40 dark:text-[#FDE68A]">
            <Car className="w-3.5 h-3.5 fill-current" /> Cabs & Auto
          </span>
          {route.badges.map(b => (
            <span key={b} className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
              b === 'Fastest' ? 'bg-[#FFF3E0] text-[#E65100] dark:bg-[#E65100]/20 dark:text-[#FFB74D]' : 
              b.includes('Shortest') ? 'bg-[#E0F2FE] text-[#0369A1] dark:bg-[#0369A1]/20 dark:text-[#7DD3FC]' : 
              'bg-[var(--surface-2)] text-[var(--ink-muted)]'
            }`}>
              {b === 'Fastest' && <Zap className="w-3.5 h-3.5 fill-current" />}
              {b.includes('Shortest') && <Ruler className="w-3.5 h-3.5" />}
              {b}
            </span>
          ))}
        </div>
        <span className="text-xs font-medium text-[var(--amber)] flex items-center gap-1 font-semibold">
          Doorstep <ChevronRight className="w-3.5 h-3.5" />
        </span>
      </div>
      
      <div className="flex justify-between items-end mb-4 font-mono">
        <div className="text-3xl font-bold tracking-tight text-[var(--ink)] leading-none">
          {route.totals.time}<span className="text-sm text-[var(--ink-muted)] font-sans font-medium ml-1">min</span>
        </div>
        <div className="text-xl font-bold text-[var(--ink)]">
          ₹{lowestFare}<span className="text-sm text-[var(--ink-muted)] font-normal font-sans ml-0.5">– ₹{highestFare}</span>
        </div>
        <div className="text-base text-[var(--ink-muted)]">
          {route.totals.distance.toFixed(1)} km
        </div>
      </div>

      {/* Solid amber line indicating direct continuous road trip with no transfers */}
      <div className="w-full h-2 rounded-full overflow-hidden mb-3 bg-[var(--amber)] shadow-xs" />

      {/* Provider brand chips */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs pt-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="px-2 py-0.5 rounded-md bg-[var(--surface-2)] text-[11px] font-semibold text-[var(--ink)] border border-[var(--line)]">
            Auto ₹{autoTier?.fare_low || 100}+
          </span>
          <span className="px-2 py-0.5 rounded-md bg-[var(--surface-2)] text-[11px] font-semibold text-[var(--ink)] border border-[var(--line)]">
            Cab ₹{cabTier?.fare_low || 180}+
          </span>
          <span className="text-[11px] text-[var(--ink-muted)] font-medium">
            Uber · Ola · Rapido
          </span>
        </div>
        {route.relativeTimeDiff !== undefined && route.relativeTimeDiff < 0 ? (
          <span className="text-[var(--orange)] font-semibold text-[11px] flex items-center gap-1">
            <Zap className="w-3 h-3 fill-current" /> {Math.abs(route.relativeTimeDiff)}m faster than train
          </span>
        ) : (
          <span className="text-[var(--ink-muted)] text-[11px]">
            Direct road · 0 transfers
          </span>
        )}
      </div>
    </motion.div>
  );
}

