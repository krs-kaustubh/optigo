import { Node, Route, ApiErrorResponse, OptigoApiError } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetcher<T>(endpoint: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, init);
  } catch (err) {
    throw new OptigoApiError('Cannot reach the backend. Our data service might be waking up.', 'NetworkError');
  }

  if (!res.ok) {
    let errData: ApiErrorResponse | null = null;
    try {
      errData = await res.json();
    } catch {
      // Ignored
    }
    
    if (errData && errData.error && errData.detail) {
      throw new OptigoApiError(errData.detail, errData.error);
    }
    
    throw new OptigoApiError(`HTTP ${res.status}`, 'UnknownError');
  }

  return res.json();
}

export const api = {
  getNodes: () => fetcher<Node[]>('/nodes'),
  
  compareRoutes: (sourceId: number, targetId: number, live: boolean = true) => 
    fetcher<Route[]>(`/compare?source=${sourceId}&target=${targetId}&live=${live}`)
};
