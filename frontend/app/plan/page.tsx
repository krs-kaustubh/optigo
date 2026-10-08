"use client";
import { useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import PlannerCard from "@/components/plan/PlannerCard";
import ResultsList from "@/components/plan/ResultsList";
import SchematicMap from "@/components/plan/SchematicMap";
import RouteDetails from "@/components/plan/RouteDetails";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { DedupedRoute } from "@/lib/route-utils";

function PlanContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const fromParam = searchParams.get("from");
  const toParam = searchParams.get("to");
  
  const [from, setFrom] = useState<number | null>(fromParam ? parseInt(fromParam, 10) : null);
  const [to, setTo] = useState<number | null>(toParam ? parseInt(toParam, 10) : null);
  const [live, setLive] = useState(true);
  const [selectedRoute, setSelectedRoute] = useState<DedupedRoute | null>(null);

  const handleSearch = (newFrom: number, newTo: number, newLive: boolean) => {
    setFrom(newFrom);
    setTo(newTo);
    setLive(newLive);
    setSelectedRoute(null);
    router.push(`/plan?from=${newFrom}&to=${newTo}`);
  };

  const { data: nodes, isLoading: nodesLoading } = useQuery({
    queryKey: ['nodes'],
    queryFn: api.getNodes
  });

  return (
    <div className="absolute inset-0 top-[57px] flex flex-col lg:flex-row overflow-hidden bg-[var(--surface-2)]">
      {/* Left Panel */}
      <div className="w-full lg:w-[420px] bg-[var(--bg)] border-r border-[var(--line)] h-full overflow-y-auto relative z-20 shrink-0">
        <div className="p-4 sticky top-0 z-10 bg-[var(--bg)]/90 backdrop-blur-md border-b border-[var(--line)]">
          <PlannerCard 
            nodes={nodes} 
            isLoading={nodesLoading}
            initialFrom={from}
            initialTo={to}
            initialLive={live}
            onSearch={handleSearch}
          />
        </div>

        <div className="p-4 flex-1">
          {(from && to && from !== to) ? (
            <ResultsList 
              from={from} 
              to={to} 
              live={live} 
              selectedRoute={selectedRoute}
              onSelectRoute={setSelectedRoute} 
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-[var(--ink-muted)] text-center p-8 mt-12">
              {from === to && from !== null ? (
                <p className="text-[var(--orange)] font-medium">Source and destination cannot be the same.</p>
              ) : (
                <p>Select your starting and ending stations to find the best routes.</p>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Right Panel (Desktop) */}
      <div className="hidden lg:flex flex-1 bg-[var(--surface-2)] relative overflow-hidden flex-col md:flex-row min-h-0">
        {selectedRoute && (
          <div className="w-full max-w-md bg-[var(--bg)] border-r border-[var(--line)] overflow-y-auto h-full p-6 shadow-xl relative z-10 shrink-0">
            <h3 className="font-serif font-bold text-2xl mb-6">Route details</h3>
            <RouteDetails route={selectedRoute} />
          </div>
        )}
        <div className="flex-1 h-full p-4">
          <SchematicMap route={selectedRoute || undefined} nodes={nodes} />
        </div>
      </div>
      
      {/* Mobile Popup for Route Details & Map */}
      <div className="lg:hidden">
        <BottomSheet isOpen={!!selectedRoute} onClose={() => setSelectedRoute(null)} title="Route details">
          {selectedRoute && (
            <div className="flex flex-col h-[70vh] overflow-y-auto">
              <div className="h-64 shrink-0 border-b border-[var(--line)]">
                <SchematicMap route={selectedRoute} nodes={nodes} />
              </div>
              <div className="p-4">
                <RouteDetails route={selectedRoute} />
              </div>
            </div>
          )}
        </BottomSheet>
      </div>
    </div>
  );
}

export default function PlanPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-[var(--ink-muted)]">Loading planner...</div>}>
      <PlanContent />
    </Suspense>
  );
}
