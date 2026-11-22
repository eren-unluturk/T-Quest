// Types written from contracts/api/*.yaml (only the fields the app uses).

export interface LoginResponse { token: string; username: string; expires_in: number }

export interface Stop { id: string; name: string; lat: number; lon: number; municipality?: string | null; neighborhood?: string | null; routes?: { id: string; color: string | null; line_id: string | null; short_name: string | null; mode: string }[] }
export interface Vehicle { vehicle_id: string; route_id: string | null; lat: number | null; lon: number | null; current_status: string | null; time: string }
export interface Line { id: string; name: string; mode?: string | null; color?: string | null }

export interface Fact { id: string; kind: string; title: string; body: string; source_url: string | null }
export interface StopFacts { stop_id: string; stop_name: string; facts: Fact[]; fallback: boolean; note: string | null }
export interface ContentItem {
  id: string; title: string; short_description: string | null; category: string | null;
  lat: number | null; lon: number | null; distance_m: number | null;
  source_id: string; source_url: string; license: string; attribution: string; commercial_ok: boolean; needs_verify: boolean;
}
export interface LoadingFact { id: string; body: string; tags: string[]; source_url: string | null; attribution: string }
export interface Fave {
  fact_id: string; kind: string; text: string; place: string | null; line: string | null;
  attribution: string; source_url: string | null; faved_at: string;
}

export interface CategoryRef { slug: string; display_name: string }
export interface LabelType { slug: string; display_name: string }
export interface SpotLabel {
  slug: string; display_name: string; status: 'declared' | 'certified';
  evidence_url: string | null; declaration_note: string | null;
}
export interface Offer {
  id: string; sponsor_id: string; store_id: string | null; title: string; description: string;
  kind: 'discount' | 'free_item' | 'points_item'; discount_pct: number | null; points_cost: number | null;
  min_rank: number; placement: 'local_pick' | 'sponsored_quest'; demo: boolean;
}
export interface Spot {
  id: string; name: string; category: CategoryRef; address: string | null;
  placement_type: 'sponsored' | 'listed'; demo: boolean; sponsor_id: string | null;
  distance_m: number | null; fun_fact: string | null; labels: SpotLabel[]; offers: Offer[];
}
export interface FacetCount { slug: string; display_name: string; count: number }
export interface Nearby {
  stop_id: string; total: number; limit: number; offset: number; spots: Spot[];
  facets: { categories: FacetCount[]; labels: FacetCount[] };
}
export interface RankTier {
  rank: number; name: string; avatar_key: string; min_lifetime_points: number; discount_pct: number;
  free_item: boolean; demo: boolean; offers: Offer[];
}

export interface LineMiles { line_id: string; name: string; color: string | null; miles: number }
export interface Travel {
  total_miles: number; per_line: LineMiles[];
  traveled_segments: { route_id: string; from_stop_id: string; to_stop_id: string; miles: number }[];
  unlocked_spots: { spot_id: string; name: string; stop_id: string | null; fact_count: number }[];
}

export interface MyRank {
  rank: number; name: string; avatar_key: string; discount_pct: number; lifetime_points: number;
  next_rank: number | null; next_rank_name: string | null; next_rank_at: number | null; points_to_next: number | null;
}
export interface MyPoints { balance: number; lifetime: number; recent: { at: string; delta: number; reason: string }[] }
export interface CheckinRequest { stop_id: string; lat: number; lon: number; client_time: string; mode?: 'subway' | 'bus' }
export interface CheckinResult { checkin_id: string; points_awarded: number; first_visit: boolean; new_rank: number | null; badges_unlocked: string[] }
