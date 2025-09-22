// API functions for MTG card data
import { PAGE_SIZE } from './state.js';

// Fetch card summary with optional query parameters
export async function fetchCardSummary(queryParams = '') {
  const url = `/api/cards/summary${queryParams ? '?' + queryParams : ''}`;
  const res = await fetch(url);
  if (res.ok) {
    return await res.json();
  } else {
    throw new Error('Failed to fetch card summary');
  }
}

// Fetch filtered cards with pagination and sorting
export async function fetchFilteredCards(page = 1, sortBy, sortOrder, colorFilter, typeFilter, previousColorFilter) {
  let queryParams = `page=${page}&page_size=${PAGE_SIZE}&sort_by=${sortBy}&sort_order=${sortOrder}`;
  if (colorFilter) {
    if (colorFilter === 'Many' && previousColorFilter && previousColorFilter !== 'Many') {
      queryParams += `&color=${encodeURIComponent(previousColorFilter)}&many=true`;
    } else {
      queryParams += `&color=${encodeURIComponent(colorFilter)}`;
    }
  }
  if (typeFilter) {
    queryParams += `&type=${encodeURIComponent(typeFilter)}`;
  }

  const res = await fetch(`/api/cards?${queryParams}`);

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }

  return await res.json();
}