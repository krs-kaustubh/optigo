"use client";
import { LiveTrain } from "@/lib/types";
import { DedupedRoute } from "@/lib/route-utils";
import { Activity, Info } from "lucide-react";
import { useState, useEffect } from "react";

export default function RouteDetails({ route }: { route: DedupedRoute }) {
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
