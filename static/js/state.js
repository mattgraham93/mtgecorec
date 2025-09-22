// State management for MTG card visualizations
export let allCards = [];
export let currentColorFilter = null;
export let currentTypeFilter = null;
export let previousColorFilter = null;
export const PAGE_SIZE = 10; // Show 10 cards per page in table
export let currentPage = 1;
export let totalFilteredCards = 0;
export let drillDownData = null; // For drilling into "Other" types
export let currentSortBy = 'name'; // Default sort column
export let currentSortOrder = 'asc'; // 'asc' or 'desc'

// Setter functions for state variables
export function setCurrentPage(page) {
  currentPage = page;
}

export function setTotalFilteredCards(total) {
  totalFilteredCards = total;
}

export function setCurrentSortBy(sortBy) {
  currentSortBy = sortBy;
}

export function setCurrentSortOrder(sortOrder) {
  currentSortOrder = sortOrder;
}

export function setCurrentColorFilter(filter) {
  currentColorFilter = filter;
}

export function setCurrentTypeFilter(filter) {
  currentTypeFilter = filter;
}

export function setPreviousColorFilter(filter) {
  previousColorFilter = filter;
}

export function setDrillDownData(data) {
  drillDownData = data;
}

// Load state from localStorage
export function loadStateFromStorage() {
  const savedFilters = localStorage.getItem('mtgCardFilters');
  if (savedFilters) {
    try {
      const filters = JSON.parse(savedFilters);
      currentColorFilter = filters.color || null;
      currentTypeFilter = filters.type || null;
      currentSortBy = filters.sortBy || 'name';
      currentSortOrder = filters.sortOrder || 'asc';
    } catch (e) {
      console.error('Error loading saved filters:', e);
    }
  }
}

// Save current state to localStorage
export function saveStateToStorage() {
  const filters = {
    color: currentColorFilter,
    type: currentTypeFilter,
    sortBy: currentSortBy,
    sortOrder: currentSortOrder
  };
  localStorage.setItem('mtgCardFilters', JSON.stringify(filters));
}

// Reset all filters and state
export function resetFilters() {
  currentColorFilter = null;
  currentTypeFilter = null;
  previousColorFilter = null;
  drillDownData = null;
  currentSortBy = 'name';
  currentSortOrder = 'asc';
  currentPage = 1;
  saveStateToStorage();
}