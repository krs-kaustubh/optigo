import { Route, Edge } from './types';

export interface MergedLeg {
  mode: string;
  count: number;
}

export function mergeEdges(edges: Edge[]): MergedLeg[] {
  if (!edges || edges.length === 0) return [];
  const merged: MergedLeg[] = [];
  
  let currentMode = edges[0].mode;
  let currentCount = 1;

  for (let i = 1; i < edges.length; i++) {
    if (edges[i].mode === currentMode) {
      currentCount++;
    } else {
      merged.push({ mode: currentMode, count: currentCount });
      currentMode = edges[i].mode;
      currentCount = 1;
    }
  }
  merged.push({ mode: currentMode, count: currentCount });
  
  return merged;
}

export function summarizeLegs(merged: MergedLeg[]): string {
  const modes = merged.map(m => m.mode.charAt(0).toUpperCase() + m.mode.slice(1));
  const uniqueModes = Array.from(new Set(modes));
  const changes = merged.length > 1 ? `${merged.length - 1} change${merged.length - 1 > 1 ? 's' : ''}` : 'Direct';
  
  return `${uniqueModes.join(' · ')} · ${changes}`;
}

export interface DedupedRoute extends Route {
  badges: string[];
}

export function dedupeRoutes(routes: Route[]): DedupedRoute[] {
  const map = new Map<string, DedupedRoute>();
  
  for (const route of routes) {
    const pathKey = route.path.join('|');
    const badge = route.optimized_for ? 
      route.optimized_for.charAt(0).toUpperCase() + route.optimized_for.slice(1) 
      : 'Unknown';
      
    if (map.has(pathKey)) {
      const existing = map.get(pathKey)!;
      if (!existing.badges.includes(badge)) {
        existing.badges.push(badge);
      }
    } else {
      map.set(pathKey, { ...route, badges: [badge] });
    }
  }
  
  return Array.from(map.values());
}
