import { Route, Edge, CabEstimateResponse, CabEstimate } from './types';

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
  isCab?: boolean;
  cabData?: CabEstimateResponse;
  selectedTier?: CabEstimate;
  relativeTimeDiff?: number; // negative means faster, positive means slower
  relativeCostDiff?: number; // difference in real fare (e.g. +180)
}

export interface ComparisonSummary {
  fastest: { winner: 'train' | 'cab'; time: number; diffMinutes: number };
  cheapest: { winner: 'train' | 'cab'; fare: number; savings: number };
  shortest: { winner: 'train' | 'cab'; distance: number; diffKm: number };
}

export function dedupeRoutes(routes: Route[]): DedupedRoute[] {
  const map = new Map<string, DedupedRoute>();
  
  for (const route of routes) {
    const pathKey = route.path.join('|');
    const badge = route.optimized_for ? 
      route.optimized_for.charAt(0).toUpperCase() + route.optimized_for.slice(1) 
      : 'Standard';
      
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

export function buildUnifiedRoutes(
  transitRoutes: Route[], 
  cabData?: CabEstimateResponse | null
): { routes: DedupedRoute[]; summary: ComparisonSummary | null } {
  const dedupedTransit = dedupeRoutes(transitRoutes);

  if (!cabData || !cabData.estimates || cabData.estimates.length === 0) {
    return { routes: dedupedTransit, summary: null };
  }

  // Calculate transit baseline metrics
  const minTransitTime = Math.min(...dedupedTransit.map(r => r.totals.time));
  const minTransitFare = Math.min(...dedupedTransit.map(r => r.totals.real_fare));
  const minTransitDistance = Math.min(...dedupedTransit.map(r => r.totals.distance));

  // Calculate cab baseline metrics
  const lowestCabFare = Math.min(...cabData.estimates.map(e => e.fare_low));
  const cabTime = cabData.duration_minutes;
  const cabDistance = cabData.road_distance_km;

  // Comparison summary
  const summary: ComparisonSummary = {
    fastest: {
      winner: cabTime < minTransitTime ? 'cab' : 'train',
      time: Math.min(cabTime, minTransitTime),
      diffMinutes: Math.abs(cabTime - minTransitTime)
    },
    cheapest: {
      winner: lowestCabFare < minTransitFare ? 'cab' : 'train',
      fare: Math.min(lowestCabFare, minTransitFare),
      savings: Math.abs(lowestCabFare - minTransitFare)
    },
    shortest: {
      winner: cabDistance < minTransitDistance ? 'cab' : 'train',
      distance: Math.min(cabDistance, minTransitDistance),
      diffKm: parseFloat(Math.abs(cabDistance - minTransitDistance).toFixed(1))
    }
  };

  // Adjust transit badges based on cab comparison
  const updatedTransit = dedupedTransit.map(route => {
    const badges = [...route.badges];
    // If cab is strictly faster, transit loses generic "Fastest" in favor of "Fastest Transit"
    if (cabTime < minTransitTime) {
      const fastestIdx = badges.indexOf('Fastest');
      if (fastestIdx !== -1) {
        badges[fastestIdx] = 'Fastest Train';
      }
    }
    // If cab has shorter distance, transit loses "Shortest" in favor of "Rail Shortest"
    if (cabDistance < minTransitDistance) {
      const shortestIdx = badges.indexOf('Shortest');
      if (shortestIdx !== -1) {
        badges[shortestIdx] = 'Shortest Rail';
      }
    }
    return {
      ...route,
      badges,
      relativeCostDiff: 0,
      relativeTimeDiff: route.totals.time - cabTime
    };
  });

  // Build Cab Route
  const cabBadges: string[] = ['Direct Ride', '0 Transfers'];
  if (cabTime < minTransitTime) {
    cabBadges.unshift('Fastest');
  } else if (cabTime === minTransitTime) {
    cabBadges.push('Equally Fast');
  }

  if (cabDistance < minTransitDistance) {
    cabBadges.push('Shortest Route');
  }

  if (lowestCabFare <= minTransitFare) {
    cabBadges.push('Cheapest');
  }

  const cabRoute: DedupedRoute = {
    path: [cabData.pickup.name, cabData.dropoff.name],
    edges: [
      {
        from: cabData.pickup.name,
        to: cabData.dropoff.name,
        mode: 'car'
      }
    ],
    totals: {
      distance: cabData.road_distance_km,
      time: cabData.duration_minutes,
      cost: lowestCabFare,
      real_fare: lowestCabFare
    },
    badges: cabBadges,
    isCab: true,
    cabData: cabData,
    relativeTimeDiff: cabTime - minTransitTime,
    relativeCostDiff: lowestCabFare - minTransitFare
  };

  return {
    routes: [...updatedTransit, cabRoute],
    summary
  };
}
