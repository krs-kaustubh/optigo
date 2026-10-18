"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { DedupedRoute } from "@/lib/route-utils";
import { Node } from "@/lib/types";

// Base unit is 50px
const GRID_SIZE = 50;
const OFFSET_X = 50;
const OFFSET_Y = 50;

const SCHEMATIC_LAYOUT: Record<string, { x: number, y: number, align: 'start' | 'middle' | 'end', offX: number, offY: number }> = {
  "Vashi": { x: 0, y: 0, align: 'middle', offX: 0, offY: -15 },
  "Sanpada": { x: 1, y: 0, align: 'middle', offX: 0, offY: -15 },
  "Juinagar": { x: 2, y: 0, align: 'start', offX: 10, offY: -10 },
  "Nerul": { x: 3, y: 1, align: 'start', offX: 12, offY: -10 },
  "Seawoods-Darave": { x: 4, y: 2, align: 'end', offX: -15, offY: 5 },
  "Belapur CBD": { x: 5, y: 3, align: 'start', offX: 15, offY: 0 },
  "Kharghar": { x: 6, y: 4, align: 'start', offX: 15, offY: 5 },
  "Mansarovar": { x: 7, y: 5, align: 'start', offX: 15, offY: 5 },
  "Khandeshwar": { x: 8, y: 6, align: 'start', offX: 15, offY: 5 },
  "Panvel": { x: 9, y: 7, align: 'start', offX: 15, offY: 5 },
  
  "RBI": { x: 5, y: 2, align: 'end', offX: -15, offY: -5 },
  "Belpada": { x: 6, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Utsav Chowk": { x: 7, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Kendriya Vihar": { x: 8, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Kharghar Village": { x: 9, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Central Park": { x: 10, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Pethpada": { x: 11, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Amandoot": { x: 12, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Pethali-Taloja": { x: 13, y: 2, align: 'middle', offX: 0, offY: -15 },
  "Pendhar": { x: 14, y: 2, align: 'start', offX: 15, offY: 5 },
  
  "Sagar Sangam": { x: 4, y: 4, align: 'end', offX: -15, offY: 5 },
  "Targhar": { x: 4, y: 5, align: 'end', offX: -15, offY: 5 },
  "Bamandongri": { x: 4, y: 6, align: 'end', offX: -15, offY: 5 },
  "Kharkopar": { x: 4, y: 7, align: 'end', offX: -15, offY: 5 },
};

// Define the static polylines for the network
const LINES = [
  // Harbour
  {
    mode: 'train',
    color: 'var(--green)',
    path: ["Vashi", "Sanpada", "Juinagar", "Nerul", "Seawoods-Darave", "Belapur CBD", "Kharghar", "Mansarovar", "Khandeshwar", "Panvel"]
  },
  // Uran (from Seawoods)
  {
    mode: 'train',
    color: 'var(--green)',
    path: ["Seawoods-Darave", "Sagar Sangam", "Targhar", "Bamandongri", "Kharkopar"]
  },
  // Uran (from Belapur)
  {
    mode: 'train',
    color: 'var(--green)',
    path: ["Belapur CBD", "Sagar Sangam"]
  },
  // Metro
  {
    mode: 'metro',
    color: 'var(--orange)',
    path: ["Belapur CBD", "RBI", "Belpada", "Utsav Chowk", "Kendriya Vihar", "Kharghar Village", "Central Park", "Pethpada", "Amandoot", "Pethali-Taloja", "Pendhar"]
  },
  // Walk
  {
    mode: 'walk',
    color: 'var(--ink-muted)',
    dashed: true,
    path: ["Kharghar", "Belpada"]
  }
];

export default function SchematicMap({ route, nodes }: { route?: DedupedRoute, nodes?: Node[] }) {
  const [mobileLegendVisible, setMobileLegendVisible] = useState(true);

  const handleMapInteraction = () => {
    if (mobileLegendVisible) {
      setMobileLegendVisible(false);
    }
  };
  
  const getPoint = (name: string) => {
    const layout = SCHEMATIC_LAYOUT[name];
    if (!layout) return null;
    return { x: layout.x * GRID_SIZE + OFFSET_X, y: layout.y * GRID_SIZE + OFFSET_Y };
  };

  const createD = (path: string[]) => {
    const points = path.map(getPoint).filter(Boolean);
    if (points.length === 0) return "";
    let d = `M ${points[0]!.x} ${points[0]!.y}`;
    for (let i = 1; i < points.length; i++) {
      d += ` L ${points[i]!.x} ${points[i]!.y}`;
    }
    return d;
  };

  const isCab = Boolean(route?.isCab);
  const p1 = route && route.path.length >= 2 ? getPoint(route.path[0]) : null;
  const p2 = route && route.path.length >= 2 ? getPoint(route.path[route.path.length - 1]) : null;

  // Calculate road curve bezier coordinates if cab route
  let roadPathD = "";
  let roadMidPoint = { x: 0, y: 0 };
  if (isCab && p1 && p2) {
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const curveFactor = dist > 250 ? 55 : 35;
    const nx = -dy / (dist || 1);
    const ny = dx / (dist || 1);
    const cpX = midX + nx * curveFactor;
    const cpY = midY + ny * curveFactor;
    roadPathD = `M ${p1.x} ${p1.y} Q ${cpX} ${cpY} ${p2.x} ${p2.y}`;
    roadMidPoint = { x: (midX + cpX) / 2, y: (midY + cpY) / 2 };
  }

  return (
    <div 
      className="w-full h-full bg-[var(--surface-2)] overflow-hidden relative rounded-[24px] border border-[var(--line)]"
      onTouchStart={handleMapInteraction}
      onClick={handleMapInteraction}
    >
      <TransformWrapper 
        initialScale={1} 
        minScale={0.5} 
        maxScale={4} 
        wheel={{ step: 0.1 }}
        pinch={{ step: 5 }}
        onPanning={handleMapInteraction}
        onZoom={handleMapInteraction}
        onWheel={handleMapInteraction}
      >
        <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="w-full h-full relative flex items-center justify-center p-2 md:p-4">
            {/* We use a fixed viewBox to contain the 14x7 grid (700x350) + padding */}
            <svg viewBox="0 0 820 460" preserveAspectRatio="xMidYMid meet" className="w-full h-full max-w-4xl max-h-full drop-shadow-sm" style={{ touchAction: 'none' }}>
          
          {/* 1. Draw base rail & metro network (faded if route is selected) */}
          {LINES.map((line, i) => (
            <path
              key={`base-${i}`}
              d={createD(line.path)}
              fill="none"
              stroke={line.color}
              strokeWidth="6"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray={line.dashed ? "8 8" : "none"}
              opacity={route ? (isCab ? 0.12 : 0.18) : 0.65}
            />
          ))}

          {/* 2. Draw Road / Cab Express Corridor when a Cab route is selected */}
          {isCab && roadPathD && (
            <g>
              {/* Outer Amber Highway Glow */}
              <motion.path
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.4 }}
                transition={{ duration: 0.7 }}
                d={roadPathD}
                fill="none"
                stroke="#F59E0B"
                strokeWidth="14"
                strokeLinecap="round"
              />
              {/* Main Highway Surface */}
              <motion.path
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.7 }}
                d={roadPathD}
                fill="none"
                stroke="#D97706"
                strokeWidth="7"
                strokeLinecap="round"
              />
              {/* Dashed Center Lane */}
              <motion.path
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.7, delay: 0.1 }}
                d={roadPathD}
                fill="none"
                stroke="#FEF08A"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray="6 6"
              />
              {/* Midpoint Corridor Info Badge */}
              {roadMidPoint.x > 0 && (
                <g transform={`translate(${roadMidPoint.x}, ${roadMidPoint.y})`}>
                  <rect 
                    x="-65" 
                    y="-14" 
                    width="130" 
                    height="28" 
                    rx="14" 
                    fill="var(--surface)" 
                    stroke="#F59E0B" 
                    strokeWidth="2" 
                    className="drop-shadow-md"
                  />
                  <text 
                    x="0" 
                    y="4" 
                    textAnchor="middle" 
                    fill="var(--ink)" 
                    fontSize="11" 
                    fontWeight="bold" 
                    fontFamily="sans-serif"
                  >
                    Road · {route?.totals.time}m · {route?.totals.distance.toFixed(1)} km
                  </text>
                </g>
              )}
            </g>
          )}

          {/* 3. Draw color-coded highlighted segments for Transit Routes */}
          {!isCab && route && route.path.map((stop, i) => {
            if (i === route.path.length - 1) return null;
            const nextStop = route.path[i+1];
            const edge = route.edges[i];
            const stopP1 = getPoint(stop);
            const stopP2 = getPoint(nextStop);
            if (!stopP1 || !stopP2) return null;
            
            const color = edge?.mode === 'train' ? 'var(--green)' : edge?.mode === 'metro' ? 'var(--orange)' : 'var(--ink-muted)';
            const dashed = edge?.mode === 'walking';
            
            return (
              <motion.line
                key={`hl-${i}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                x1={stopP1.x} y1={stopP1.y} x2={stopP2.x} y2={stopP2.y}
                stroke={color}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={dashed ? "8 8" : "none"}
              />
            );
          })}

          {/* 4. Draw Stations */}
          {Object.entries(SCHEMATIC_LAYOUT).map(([name, layout]) => {
            const p = getPoint(name);
            if (!p) return null;
            
            // If there's a selected route, fade out unselected stations
            let isSelected = true;
            if (route) {
              if (isCab) {
                isSelected = name === route.path[0] || name === route.path[route.path.length - 1];
              } else {
                isSelected = route.path.includes(name);
              }
            }
            
            const isStart = route && name === route.path[0];
            const isEnd = route && name === route.path[route.path.length - 1];

            return (
              <g key={name} className="group" opacity={isSelected ? 1 : 0.2} style={{ transition: 'opacity 0.3s' }}>
                <circle
                  cx={p.x} cy={p.y} r={isSelected && route ? "7" : "5.5"}
                  fill="var(--surface)"
                  stroke={
                    isCab && (isStart || isEnd) 
                      ? "#F59E0B" 
                      : isSelected && route 
                        ? "var(--ink)" 
                        : "var(--ink-muted)"
                  }
                  strokeWidth={isCab && (isStart || isEnd) ? "4" : "3"}
                  className={isSelected ? "" : "group-hover:stroke-[var(--green)] group-hover:opacity-100 transition-all cursor-pointer"}
                />
                {(isSelected || !route) && (
                  <text
                    x={p.x + layout.offX}
                    y={p.y + layout.offY}
                    textAnchor={layout.align}
                    fill={isSelected && route ? (isCab ? "#D97706" : "var(--ink)") : "var(--ink-muted)"}
                    className={`font-sans ${isSelected && route ? 'font-bold text-[14px]' : 'font-medium text-[12px]'}`}
                  >
                    {name}
                  </text>
                )}
              </g>
            );
          })}

          {/* 5. Highlight Start / End Pins */}
          {route && p1 && (
            <g>
              <circle cx={p1.x} cy={p1.y} r="9" fill="none" stroke={isCab ? "#F59E0B" : "var(--green)"} strokeWidth="3" opacity={0.6} />
              <circle cx={p1.x} cy={p1.y} r="5" fill={isCab ? "#F59E0B" : "var(--green)"} />
            </g>
          )}
          {route && p2 && (
            <g>
              <circle cx={p2.x} cy={p2.y} r="9" fill="none" stroke={isCab ? "#F59E0B" : "var(--ink)"} strokeWidth="3" opacity={0.6} />
              <circle cx={p2.x} cy={p2.y} r="5" fill={isCab ? "#F59E0B" : "var(--ink)"} />
            </g>
          )}

        </svg>
          </div>
        </TransformComponent>
      </TransformWrapper>

      {/* Multimodal Map Legend - Desktop (compact & fixed) */}
      <div className="hidden sm:flex absolute bottom-3.5 left-3.5 bg-[var(--surface)]/95 backdrop-blur-md px-3 py-2 rounded-[14px] border border-[var(--line)] shadow-sm text-xs flex-col gap-1 pointer-events-none">
        <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--ink-muted)] mb-0.5">Lines</div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-1 rounded-full bg-[var(--green)]" />
          <span className="text-[10px] font-medium text-[var(--ink)]">Harbour & Uran Line</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-1 rounded-full bg-[var(--orange)]" />
          <span className="text-[10px] font-medium text-[var(--ink)]">Metro Line 1</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-1 rounded-full border-t border-dashed border-[var(--ink-muted)]" />
          <span className="text-[10px] font-medium text-[var(--ink-muted)]">Walk Transfer</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-1 rounded-full bg-[#F59E0B]" />
          <span className="text-[10px] font-semibold text-[#D97706] dark:text-[#FDE68A]">Cab / Auto Road</span>
        </div>
      </div>

      {/* Multimodal Map Legend - Mobile (Collapsible / disappears on tap & scroll) */}
      <div className="sm:hidden absolute bottom-3 left-3 z-20">
        {mobileLegendVisible ? (
          <div 
            onClick={() => setMobileLegendVisible(false)}
            className="bg-[var(--surface)]/95 backdrop-blur-md px-2.5 py-1.5 rounded-[12px] border border-[var(--line)] shadow-md text-xs flex flex-col gap-1 cursor-pointer animate-in fade-in duration-200"
          >
            <div className="flex items-center justify-between gap-3 text-[9px] font-bold uppercase tracking-wider text-[var(--ink-muted)]">
              <span>Legend</span>
              <span className="text-[8px] text-[var(--ink-muted)] font-normal">tap to hide</span>
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[9px]">
              <div className="flex items-center gap-1">
                <div className="w-2 h-1 rounded-full bg-[var(--green)] shrink-0" />
                <span className="text-[var(--ink)]">Harbour/Uran</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-1 rounded-full bg-[var(--orange)] shrink-0" />
                <span className="text-[var(--ink)]">Metro 1</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-1 border-t border-dashed border-[var(--ink-muted)] shrink-0" />
                <span className="text-[var(--ink-muted)]">Walk</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-1 rounded-full bg-[#F59E0B] shrink-0" />
                <span className="text-[#D97706] font-medium">Road</span>
              </div>
            </div>
          </div>
        ) : (
          <button 
            type="button"
            onClick={() => setMobileLegendVisible(true)}
            className="bg-[var(--surface)]/90 backdrop-blur-sm px-2 py-1 rounded-full border border-[var(--line)] text-[9px] font-bold text-[var(--ink-muted)] hover:text-[var(--ink)] shadow-xs"
          >
            Legend
          </button>
        )}
      </div>

      <div className="absolute top-3.5 right-3.5 bg-[var(--surface)]/90 backdrop-blur-sm px-2.5 py-1 rounded-full border border-[var(--line)] text-[9px] font-bold uppercase tracking-wider text-[var(--ink)] shadow-xs pointer-events-none">
        {isCab ? 'Road Corridor View' : 'Schematic Transit Map'}
      </div>
    </div>
  );
}
