export interface Node {
  id: number;
  name: string;
  lat: number;
  lng: number;
  type: string;
}

export interface Edge {
  from: string;
  to: string;
  mode: 'train' | 'metro' | 'walking' | 'bike' | 'car' | 'bus';
}

export interface Totals {
  distance: number;
  time: number;
  cost: number;
  real_fare: number;
}

export interface LiveTrain {
  train_number: string;
  route_name: string;
  towards: string;
  destination_code: string;
  line: string;
  departure_time: string;
  expected_departure: string;
  platform: string;
  status: string;
  delay_minutes: number | null;
}

export interface LiveStatus {
  applicable: boolean;
  reason: 'ok' | 'no_relevant_trains' | 'no_train_leg' | 'station_not_in_railradar' | 'api_key_missing' | 'fetch_failed';
  boarding_station?: string;
  alighting_station?: string;
  boarding_code?: string;
  alighting_code?: string;
  line?: string;
  trains_on_board?: number;
  relevant_trains?: number;
  board_time?: string;
}

export interface Route {
  path: string[];
  edges: Edge[];
  totals: Totals;
  optimized_for?: 'time' | 'distance' | 'cost';
  live_trains?: LiveTrain[];
  live_status?: LiveStatus;
}

export interface ApiErrorResponse {
  detail: string;
  error: string;
}

export class OptigoApiError extends Error {
  constructor(public detail: string, public type: string) {
    super(detail);
    this.name = 'OptigoApiError';
  }
}
