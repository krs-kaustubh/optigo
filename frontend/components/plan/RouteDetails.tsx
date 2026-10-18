"use client";
import { LiveTrain, CabEstimate } from "@/lib/types";
import { DedupedRoute } from "@/lib/route-utils";
import { Activity, Info, Car, Navigation, Zap, ExternalLink, ShieldCheck, Clock, MapPin } from "lucide-react";
import { useState, useEffect, useMemo } from "react";

export default function RouteDetails({ route }: { route: DedupedRoute }) {
  if (route.isCab && route.cabData) {
    return <CabRouteDetails route={route} />;
  }

  return (
    <div className="flex flex-col gap-8 pb-8">
      {route.live_status && route.live_status.applicable && route.live_trains && (
        <LiveBoard status={route.live_status} trains={route.live_trains} />
      )}
      
      {!route.live_status?.applicable && (
        <div className="bg-[var(--surface-2)] rounded-[16px] p-4 text-sm text-[var(--ink-muted)] flex gap-3 items-center">
          <Info className="w-5 h-5 text-[var(--ink-muted)] shrink-0" />
          <p>Metro-only route: live times aren't available.</p>
        </div>
      )}

      {/* Timeline */}
      <div className="relative pl-6 border-l-[3px] border-[var(--line)] ml-3 space-y-6 mt-4">
        {route.path.map((stop: string, index: number) => {
          const isFirst = index === 0;
          const isLast = index === route.path.length - 1;
          const edgeBefore = index > 0 ? route.edges[index - 1] : null;
          const edgeAfter = index < route.path.length - 1 ? route.edges[index] : null;
          
          let modeColor = 'var(--ink-muted)';
          if (edgeAfter) {
            modeColor = edgeAfter.mode === 'train' ? 'var(--green)' : edgeAfter.mode === 'metro' ? 'var(--orange)' : 'var(--ink-muted)';
          } else if (edgeBefore) {
            modeColor = edgeBefore.mode === 'train' ? 'var(--green)' : edgeBefore.mode === 'metro' ? 'var(--orange)' : 'var(--ink-muted)';
          }

          const isInterchange = edgeBefore && edgeAfter && edgeBefore.mode !== edgeAfter.mode;

          return (
            <div key={`${stop}-${index}`} className="relative">
              <div 
                className={`absolute -left-[31.5px] w-4 h-4 rounded-full border-[3px] border-[var(--surface)] ${isFirst || isLast ? 'w-[22px] h-[22px] -left-[35px]' : ''}`}
                style={{ backgroundColor: modeColor }}
              />
              <div className="flex flex-col -mt-1">
                <span className={`font-medium ${isFirst || isLast ? 'text-lg text-[var(--ink)] font-bold' : 'text-[var(--ink)]'}`}>{stop}</span>
                {isInterchange && (
                  <span className="text-xs text-[var(--ink)] bg-[var(--surface-2)] border border-[var(--line)] font-medium inline-block w-max px-2 py-0.5 rounded-full mt-1.5 shadow-sm">
                    Change to {edgeAfter.mode}
                  </span>
                )}
                {edgeAfter && !isInterchange && (
                  <span className="text-[11px] text-[var(--ink-muted)] font-medium uppercase tracking-wider mt-1">{edgeAfter.mode}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-[var(--surface)] border border-[var(--line)] rounded-[20px] p-5 text-sm flex justify-between items-center font-mono shadow-sm mt-4">
        <div className="flex flex-col items-center"><span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Fare</span><span className="text-xl font-bold">₹{route.totals.real_fare}</span></div>
        <div className="w-px h-8 bg-[var(--line)]"></div>
        <div className="flex flex-col items-center"><span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Time</span><span className="text-xl font-bold">{route.totals.time}m</span></div>
        <div className="w-px h-8 bg-[var(--line)]"></div>
        <div className="flex flex-col items-center"><span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Dist</span><span className="text-xl font-bold">{route.totals.distance.toFixed(1)}<span className="text-sm font-sans">km</span></span></div>
      </div>
      <p className="text-[11px] text-[var(--ink-muted)] text-center -mt-5 font-medium">Fare uses distance slabs; estimated.</p>
    </div>
  );
}

function CabRouteDetails({ route }: { route: DedupedRoute }) {
  const cab = route.cabData!;
  const [tierFilter, setTierFilter] = useState<'all' | 'auto' | 'cab' | 'bike'>('all');

  const filteredEstimates = useMemo(() => {
    if (tierFilter === 'auto') return cab.estimates.filter(e => e.category === 'auto');
    if (tierFilter === 'cab') return cab.estimates.filter(e => e.category === 'cab_mini' || e.category === 'cab_sedan');
    if (tierFilter === 'bike') return cab.estimates.filter(e => e.category === 'bike');
    return cab.estimates;
  }, [cab.estimates, tierFilter]);

  const autoCount = cab.estimates.filter(e => e.category === 'auto').length;
  const cabCount = cab.estimates.filter(e => e.category === 'cab_mini' || e.category === 'cab_sedan').length;
  const bikeCount = cab.estimates.filter(e => e.category === 'bike').length;

  return (
    <div className="flex flex-col gap-6 pb-8">
      {/* 1. Comparison & Doorstep Banner */}
      <div className="p-4 rounded-[20px] bg-[#FEF3C7] border border-[#FDE68A] dark:bg-[#78350F]/30 dark:border-[#B45309]/50 text-xs">
        <div className="flex items-center gap-2 font-bold text-[#92400E] dark:text-[#FDE68A] mb-1.5 text-sm">
          <Car className="w-4 h-4 fill-current" />
          <span>Direct Road Ride · 0 Transfers</span>
        </div>
        <div className="flex flex-col gap-1 text-[var(--ink)]">
          {route.relativeTimeDiff !== undefined && route.relativeTimeDiff < 0 ? (
            <p className="font-semibold text-[var(--orange)]">
              Saves {Math.abs(route.relativeTimeDiff)} minutes compared to taking the train + walking.
            </p>
          ) : (
            <p className="text-[var(--ink-muted)]">
              Doorstep pickup directly from {cab.pickup.name} to {cab.dropoff.name}.
            </p>
          )}
          {route.relativeCostDiff !== undefined && route.relativeCostDiff > 0 && (
            <p className="text-[var(--ink-muted)]">
              Public transit is ₹{route.relativeCostDiff} cheaper, but cab avoids crowded platforms.
            </p>
          )}
        </div>
      </div>

      {/* 2. Pickup & Dropoff Segment */}
      <div className="p-4 rounded-[20px] bg-[var(--surface-2)] border border-[var(--line)] flex flex-col gap-3 text-sm">
        <div className="flex items-center gap-3">
          <div className="w-3.5 h-3.5 rounded-full bg-[var(--amber)] ring-4 ring-[var(--amber)]/20 shrink-0" />
          <div>
            <div className="text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider">Pickup Location</div>
            <div className="font-bold text-[var(--ink)]">{cab.pickup.name}</div>
          </div>
        </div>
        <div className="w-0.5 h-4 bg-[var(--line)] ml-[6.5px]" />
        <div className="flex items-center gap-3">
          <div className="w-3.5 h-3.5 rounded-full bg-[var(--ink)] ring-4 ring-[var(--ink)]/20 shrink-0" />
          <div>
            <div className="text-[11px] font-semibold text-[var(--ink-muted)] uppercase tracking-wider">Dropoff Destination</div>
            <div className="font-bold text-[var(--ink)]">{cab.dropoff.name}</div>
          </div>
        </div>
      </div>

      {/* 3. Category Filter Tabs */}
      <div className="flex items-center gap-1.5 p-1 bg-[var(--surface-2)] rounded-full border border-[var(--line)] text-xs font-semibold">
        <button
          onClick={() => setTierFilter('all')}
          className={`flex-1 py-1 px-2.5 rounded-full transition-all text-center ${tierFilter === 'all' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-xs font-bold' : 'text-[var(--ink-muted)]'}`}
        >
          All ({cab.estimates.length})
        </button>
        {autoCount > 0 && (
          <button
            onClick={() => setTierFilter('auto')}
            className={`flex-1 py-1 px-2.5 rounded-full transition-all text-center ${tierFilter === 'auto' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-xs font-bold' : 'text-[var(--ink-muted)]'}`}
          >
            Auto ({autoCount})
          </button>
        )}
        {cabCount > 0 && (
          <button
            onClick={() => setTierFilter('cab')}
            className={`flex-1 py-1 px-2.5 rounded-full transition-all text-center ${tierFilter === 'cab' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-xs font-bold' : 'text-[var(--ink-muted)]'}`}
          >
            Cabs ({cabCount})
          </button>
        )}
        {bikeCount > 0 && (
          <button
            onClick={() => setTierFilter('bike')}
            className={`flex-1 py-1 px-2.5 rounded-full transition-all text-center ${tierFilter === 'bike' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-xs font-bold' : 'text-[var(--ink-muted)]'}`}
          >
            Bike ({bikeCount})
          </button>
        )}
      </div>

      {/* 4. Provider Estimates Cards */}
      <div className="flex flex-col gap-3">
        {filteredEstimates.map((est, i) => {
          const isUber = est.provider === 'Uber';
          const isOla = est.provider === 'Ola';
          const isRapido = est.provider === 'Rapido';
          const isAutoStand = est.provider === 'Auto Rickshaw';

          return (
            <div 
              key={`${est.provider}-${est.tier}-${i}`}
              className="p-4 rounded-[20px] bg-[var(--surface)] border border-[var(--line)] hover:border-[var(--amber)] shadow-xs transition-all flex flex-col gap-3"
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-base text-[var(--ink)]">{est.tier}</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                      isUber ? 'bg-black text-white dark:bg-neutral-800' :
                      isOla ? 'bg-[#10B981] text-white' :
                      isRapido ? 'bg-[#F59E0B] text-black font-extrabold' :
                      'bg-[#FEF3C7] text-[#92400E] dark:bg-[#78350F]/50 dark:text-[#FDE68A]'
                    }`}>
                      {est.provider}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)] mt-1">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" /> ETA ~{est.eta_minutes}m
                    </span>
                    <span>·</span>
                    <span>{est.duration_minutes}m ride</span>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xl font-bold font-mono text-[var(--ink)]">
                    ₹{est.fare_low}
                    {est.fare_high > est.fare_low && (
                      <span className="text-xs font-normal text-[var(--ink-muted)] font-sans ml-1">
                        – ₹{est.fare_high}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-[var(--ink-muted)] uppercase font-semibold">
                    {est.fare_source}
                  </span>
                </div>
              </div>

              {est.note && (
                <p className="text-xs text-[var(--ink-muted)] bg-[var(--surface-2)] p-2.5 rounded-[12px] leading-relaxed">
                  {est.note}
                </p>
              )}

              {/* One-Tap Deep Link Button */}
              {est.deeplink && (
                <a
                  href={est.deeplink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`mt-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-[14px] text-xs font-bold transition-all ${
                    isUber ? 'bg-neutral-900 text-white hover:bg-black dark:bg-neutral-100 dark:text-neutral-950' :
                    isOla ? 'bg-[#059669] text-white hover:bg-[#047857]' :
                    isRapido ? 'bg-[#F59E0B] text-black hover:bg-[#D97706]' :
                    'bg-[var(--surface-2)] text-[var(--ink)] border border-[var(--line)] hover:bg-[var(--surface)]'
                  }`}
                >
                  <span>
                    {isUber ? 'Book on Uber' : isOla ? 'Book on Ola' : isRapido ? 'Book on Rapido' : 'Locate Auto Stand'}
                  </span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          );
        })}
      </div>

      {/* 5. Metrics Strip */}
      <div className="bg-[var(--surface)] border border-[var(--line)] rounded-[20px] p-5 text-sm flex justify-between items-center font-mono shadow-sm mt-2">
        <div className="flex flex-col items-center">
          <span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Starting</span>
          <span className="text-xl font-bold">₹{route.totals.real_fare}</span>
        </div>
        <div className="w-px h-8 bg-[var(--line)]" />
        <div className="flex flex-col items-center">
          <span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Drive Time</span>
          <span className="text-xl font-bold">{route.totals.time}m</span>
        </div>
        <div className="w-px h-8 bg-[var(--line)]" />
        <div className="flex flex-col items-center">
          <span className="text-[var(--ink-muted)] font-sans text-xs uppercase tracking-wider mb-1">Road Dist</span>
          <span className="text-xl font-bold">{route.totals.distance.toFixed(1)}<span className="text-sm font-sans">km</span></span>
        </div>
      </div>

      {/* 6. Disclaimer */}
      {cab.disclaimer && (
        <p className="text-[11px] text-[var(--ink-muted)] text-center leading-relaxed">
          {cab.disclaimer}
        </p>
      )}
    </div>
  );
}

function LiveBoard({ status, trains }: { status: any, trains: LiveTrain[] }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(interval);
  }, []);

  if (status.reason !== 'ok' && status.reason !== 'no_relevant_trains') {
    return (
      <div className="bg-[var(--surface-2)] rounded-[16px] p-4 text-sm text-[var(--ink-muted)]">
        Live times unavailable: {status.reason.replace(/_/g, ' ')}. The route still works.
      </div>
    );
  }

  if (trains.length === 0) {
    return (
      <div className="bg-[var(--surface-2)] rounded-[16px] p-4 text-sm text-[var(--ink-muted)] font-medium text-center">
        No upcoming trains found right now.
      </div>
    );
  }

  const getCountdown = (expected: string) => {
    const diff = Math.floor((new Date(expected).getTime() - now.getTime()) / 60000);
    if (diff < 0) return 'Departed';
    if (diff === 0) return 'Now';
    return `in ${diff} min`;
  };

  const updatedTime = new Date(status.board_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="border border-[var(--line)] rounded-[20px] overflow-hidden bg-[var(--surface)] shadow-sm">
      <div className="bg-[var(--surface-2)] px-5 py-3.5 flex justify-between items-center border-b border-[var(--line)]">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-[var(--orange)] animate-pulse shadow-[0_0_8px_var(--orange)]" />
          <span className="font-bold text-sm text-[var(--ink)]">Live at {status.boarding_station}</span>
        </div>
        <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--ink-muted)]">Updated {updatedTime}</span>
      </div>
      <div className="divide-y divide-[var(--line)]">
        {trains.map((t, i) => (
          <div key={i} className={`p-5 flex items-center justify-between ${i === 0 ? 'bg-[var(--orange-soft)]/10' : ''}`}>
            <div>
              <div className="font-mono text-2xl font-bold text-[var(--ink)] leading-none mb-1">{t.departure_time}</div>
              <div className="text-sm font-medium text-[var(--ink-muted)]">to {t.towards}</div>
            </div>
            <div className="text-right flex flex-col items-end gap-1.5">
              <span className={`text-sm font-bold ${getCountdown(t.expected_departure) === 'Departed' ? 'text-[var(--ink-muted)] line-through' : 'text-[var(--orange)]'}`}>
                {getCountdown(t.expected_departure)}
              </span>
              <div className="flex gap-2 mt-1">
                <span className="text-[11px] bg-[var(--surface-2)] border border-[var(--line)] text-[var(--ink)] px-2 py-0.5 rounded font-mono font-medium">PF {t.platform}</span>
                {t.delay_minutes ? (
                  <span className="text-[11px] bg-red-100 text-red-700 px-2 py-0.5 rounded font-bold">{t.delay_minutes}m delay</span>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
