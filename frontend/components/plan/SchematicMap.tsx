"use client";

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

  return (
    <div className="w-full h-full bg-[var(--surface-2)] overflow-hidden relative rounded-[24px] border border-[var(--line)]">
      <TransformWrapper 
        initialScale={1} 
        minScale={0.5} 
        maxScale={4} 
        wheel={{ step: 0.1 }}
        pinch={{ step: 5 }}
        alignmentAnimation={{ animationTime: 200 }}
      >
        <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="w-full h-full relative flex items-center justify-center p-2 md:p-4">
            {/* We use a fixed viewBox to contain the 14x7 grid (700x350) + padding */}
            <svg viewBox="0 0 800 450" preserveAspectRatio="xMidYMid meet" className="w-full h-full max-w-4xl max-h-full drop-shadow-sm" style={{ touchAction: 'none' }}>
          
          {/* 1. Draw base network (faded) */}
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
              opacity={route ? 0.15 : 0.6}
            />
          ))}

          {/* Draw color-coded highlighted segments */}
          {route && route.path.map((stop, i) => {
            if (i === route.path.length - 1) return null;
            const nextStop = route.path[i+1];
            const edge = route.edges[i];
            const p1 = getPoint(stop);
            const p2 = getPoint(nextStop);
            if (!p1 || !p2) return null;
            
            const color = edge.mode === 'train' ? 'var(--green)' : edge.mode === 'metro' ? 'var(--orange)' : 'var(--ink-muted)';
            const dashed = edge.mode === 'walking';
            
            return (
              <motion.line
                key={`hl-${i}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
                stroke={color}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={dashed ? "8 8" : "none"}
              />
            );
          })}

          {/* 3. Draw Stations */}
          {Object.entries(SCHEMATIC_LAYOUT).map(([name, layout]) => {
            const p = getPoint(name);
            if (!p) return null;
            
            // If there's a selected route, fade out unselected stations
            const isSelected = route ? route.path.includes(name) : true;
            
            return (
              <g key={name} className="group" opacity={isSelected ? 1 : 0.25} style={{ transition: 'opacity 0.3s' }}>
                <circle
                  cx={p.x} cy={p.y} r="6"
                  fill="var(--surface)"
                  stroke={isSelected && route ? "var(--ink)" : "var(--ink-muted)"}
                  strokeWidth="3"
                  className={isSelected ? "" : "group-hover:stroke-[var(--green)] group-hover:opacity-100 transition-all cursor-pointer"}
                />
                {(isSelected || !route) && (
                  <text
                    x={p.x + layout.offX}
                    y={p.y + layout.offY}
                    textAnchor={layout.align}
                    fill={isSelected && route ? "var(--ink)" : "var(--ink-muted)"}
                    className={`font-sans ${isSelected && route ? 'font-bold text-[14px]' : 'font-medium text-[12px]'}`}
                  >
                    {name}
                  </text>
                )}
              </g>
            );
          })}

          {/* 4. Highlight start/end points */}
          {route && (
            <>
              {getPoint(route.path[0]) && (
                <circle cx={getPoint(route.path[0])!.x} cy={getPoint(route.path[0])!.y} r="8" fill="var(--surface)" stroke="var(--ink)" strokeWidth="4" />
              )}
              {getPoint(route.path[route.path.length-1]) && (
                <circle cx={getPoint(route.path[route.path.length-1])!.x} cy={getPoint(route.path[route.path.length-1])!.y} r="8" fill="var(--surface)" stroke="var(--ink)" strokeWidth="4" />
              )}
            </>
          )}

        </svg>
          </div>
        </TransformComponent>
      </TransformWrapper>
      <div className="absolute top-4 right-4 bg-[var(--surface)]/90 backdrop-blur-sm px-3 py-1.5 rounded-full border border-[var(--line)] text-[10px] font-bold uppercase tracking-wider text-[var(--ink)] shadow-sm pointer-events-none">
        Network Map
      </div>
    </div>
  );
}
