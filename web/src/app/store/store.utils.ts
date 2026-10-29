// UbiFleet — Shared Store State & Helpers
import { signal, computed } from '@angular/core';

// ── État de chargement réutilisable ──
export type LoadingState = 'idle' | 'loading' | 'loaded' | 'error';

// ── État de pagination réutilisable ──
export interface PaginationState {
  page:     number;
  pageSize: number;
  total:    number;
}

export const initialPagination: PaginationState = {
  page:     1,
  pageSize: 20,
  total:    0,
};

// ── État de filtre générique ──
export interface FilterState {
  search:   string;
  agence:   string;
  [key: string]: string | number | boolean | null;
}

export const initialFilter: FilterState = {
  search: '',
  agence: '',
};
