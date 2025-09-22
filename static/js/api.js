// API functions for MTG card data
import { PAGE_SIZE } from './state.js';

// Fetch card summary with optional query parameters
export async function fetchCardSummary(queryParams = '', signal = null) {
  const url = `/api/cards/summary${queryParams ? '?' + queryParams : ''}`;
  const res = await fetch(url, { signal });
  if (res.ok) {
    return await res.json();
  } else {
    throw new Error('Failed to fetch card summary');
  }
}

// Fetch filtered cards with pagination and sorting
export async function fetchFilteredCards(page = 1, sortBy, sortOrder, colorFilter, typeFilter, previousColorFilter, selectedColors = [], exclusiveColors = false, pageSize = null, signal = null) {
  // Use smaller page size for initial load, larger for subsequent loads
  const actualPageSize = pageSize || (page === 1 ? 5 : 15);
  
  let queryParams = `page=${page}&page_size=${actualPageSize}&sort_by=${sortBy}&sort_order=${sortOrder}`;
  
  // Use new multi-color filtering if colors are selected
  if (selectedColors && selectedColors.length > 0) {
    selectedColors.forEach(color => {
      queryParams += `&colors=${encodeURIComponent(color)}`;
    });
    if (exclusiveColors) {
      queryParams += `&exclusive_colors=true`;
    }
  } else if (colorFilter) {
    // Fallback to old single color filter for backward compatibility
    if (colorFilter === 'Many' && previousColorFilter && previousColorFilter !== 'Many') {
      queryParams += `&color=${encodeURIComponent(previousColorFilter)}&many=true`;
    } else {
      queryParams += `&color=${encodeURIComponent(colorFilter)}`;
    }
  }
  
  if (typeFilter) {
    queryParams += `&type=${encodeURIComponent(typeFilter)}`;
  }

  // Add timeout to prevent hanging requests
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

  try {
    const res = await fetch(`/api/cards?${queryParams}`, { signal });

    clearTimeout(timeoutId);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    return await res.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out - the database query is taking too long. Please try again.');
    }
    throw error;
  }
}