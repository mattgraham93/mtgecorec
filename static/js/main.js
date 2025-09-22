// Main module for MTG card visualizations - coordinates all functionality
import {
  allCards,
  currentColorFilter,
  currentTypeFilter,
  previousColorFilter,
  PAGE_SIZE,
  currentPage,
  totalFilteredCards,
  drillDownData,
  currentSortBy,
  currentSortOrder,
  loadStateFromStorage,
  saveStateToStorage,
  resetFilters
} from './state.js';

import { fetchCardSummary, fetchFilteredCards } from './api.js';

import { renderBarChart, renderDonutChart, getColorCounts, colorOrder, colorMap } from './charts.js';

import { renderFilteredCardsTable, renderPagination, setupTableSorting, updateSortIndicators } from './table.js';

// Loading spinner logic
function showLoading() {
  d3.select('#d3-bar-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:220px;"><div class="spinner-border text-primary" style="width:3rem;height:3rem;" role="status"><span class="visually-hidden">Loading...</span></div></div>');
  d3.select('#d3-donut-chart').html('');
}

function hideLoading() {
  d3.select('#d3-bar-chart').html('');
  d3.select('#d3-donut-chart').html('');
}

// Update charts and table
async function updateCharts() {
  // Show loading spinners
  d3.select('#d3-bar-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
  d3.select('#d3-donut-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
  // Hide tooltip if present
  d3.selectAll('.d3-tooltip').style('opacity', 0);

  // Update reset button
  const resetBtn = document.getElementById('reset-filters-btn');
  const anyFilter = currentColorFilter || currentTypeFilter;
  if (resetBtn) {
    resetBtn.disabled = !anyFilter;
    resetBtn.classList.toggle('btn-secondary', !anyFilter);
    resetBtn.classList.toggle('btn-primary', !!anyFilter);
  }

  // Update dropdown
  const colorDropdown = document.getElementById('color-filter-dropdown');
  if (colorDropdown) {
    colorDropdown.value = currentColorFilter || '';
  }

  // Fetch filtered summary
  let queryParams = '';
  if (currentColorFilter) {
    if (currentColorFilter === 'Many' && previousColorFilter && previousColorFilter !== 'Many') {
      queryParams += `color=${encodeURIComponent(previousColorFilter)}&many=true&`;
    } else {
      queryParams += `color=${encodeURIComponent(currentColorFilter)}&`;
    }
  }
  if (currentTypeFilter) {
    queryParams += `type=${encodeURIComponent(currentTypeFilter)}&`;
  }
  if (queryParams) queryParams = queryParams.slice(0, -1); // remove trailing &

  try {
    const summary = await fetchCardSummary(queryParams);
    window.cardSummary = summary;
  } catch (err) {
    console.error('Error fetching summary:', err);
  }

  // Update active filters display
  let filterText = '';
  if (currentColorFilter) filterText += `<span class="badge bg-primary me-2">${currentColorFilter}</span>`;
  if (currentTypeFilter) filterText += `<span class="badge bg-secondary">${currentTypeFilter}</span>`;
  d3.select('#active-filters').html(filterText || '<span class="text-muted">No active filters</span>');

  // Save state
  saveStateToStorage();

  // Bar chart
  const colorCounts = getColorCounts(allCards);
  const chartData = colorOrder.map(color => ({
    color,
    count: colorCounts[color] || 0,
    fill: colorMap[color]
  }));
  renderBarChart(chartData, handleColorClick);

  // Donut chart
  renderDonutChart([], drillDownData, handleTypeClick, handleDrillDown, handleBackToOverview);

  // Update table
  await fetchAndRenderTable(1); // Reset to first page
}

// Handle color click from bar chart
function handleColorClick(color) {
  if (currentColorFilter === color) {
    currentColorFilter = null;
    previousColorFilter = null;
  } else {
    previousColorFilter = currentColorFilter;
    currentColorFilter = color;
  }
  const colorDropdown = document.getElementById('color-filter-dropdown');
  if (colorDropdown) colorDropdown.value = currentColorFilter || '';
  updateCharts();
}

// Handle type click from donut chart
function handleTypeClick(type, isDrillDown) {
  if (isDrillDown) {
    drillDownData = null;
  }
  if (currentTypeFilter === type) {
    currentTypeFilter = null;
  } else {
    currentTypeFilter = type;
  }
  updateCharts();
}

// Handle drill down
function handleDrillDown(remainingEntries) {
  drillDownData = remainingEntries
    .filter(([type]) => type !== 'Other')
    .map(([type, count]) => ({type, count}));
  currentTypeFilter = null; // Clear type filter when drilling down
  updateCharts();
}

// Handle back to overview
function handleBackToOverview() {
  drillDownData = null;
  updateCharts();
}

// Fetch and render table
async function fetchAndRenderTable(page = 1) {
  try {
    // Show loading state
    const tbody = document.querySelector('#filtered-cards-table tbody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center"><div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div></td></tr>';
    }

    const data = await fetchFilteredCards(page, currentSortBy, currentSortOrder, currentColorFilter, currentTypeFilter, previousColorFilter);

    // Update count badge and pagination variables
    totalFilteredCards = data.total;
    currentPage = data.page;
    const countBadge = document.getElementById('filtered-count');
    if (countBadge) {
      countBadge.textContent = totalFilteredCards.toLocaleString();
    }

    renderFilteredCardsTable(data.cards);
    renderPagination(totalFilteredCards, currentPage, PAGE_SIZE, handlePageChange);
  } catch (err) {
    console.error('Failed to fetch filtered cards:', err);
    // Show error in table
    const tbody = document.querySelector('#filtered-cards-table tbody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load cards</td></tr>';
    }
  }
}

// Handle page change
function handlePageChange(page) {
  fetchAndRenderTable(page);
}

// Handle sort change
function handleSortChange(sortBy) {
  if (currentSortBy === sortBy) {
    currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
  } else {
    currentSortBy = sortBy;
    currentSortOrder = 'asc';
  }
  updateSortIndicators(currentSortBy, currentSortOrder);
  fetchAndRenderTable(1); // Reset to first page when sorting
}

// Initialize the application
document.addEventListener('DOMContentLoaded', async function() {
  // Load saved state
  loadStateFromStorage();

  // Show initial loading
  showLoading();

  try {
    // Fetch initial summary
    const summary = await fetchCardSummary();
    window.cardSummary = summary;
    hideLoading();

    // Initial render
    await updateCharts();

    // Setup table sorting
    setupTableSorting(handleSortChange);
    updateSortIndicators(currentSortBy, currentSortOrder);

    // Setup event handlers
    const colorDropdown = document.getElementById('color-filter-dropdown');
    if (colorDropdown) {
      colorDropdown.addEventListener('change', function() {
        currentColorFilter = colorDropdown.value || null;
        saveStateToStorage();
        updateCharts();
      });
    }

    const resetBtn = document.getElementById('reset-filters-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', function() {
        resetFilters();
        const colorDropdown = document.getElementById('color-filter-dropdown');
        if (colorDropdown) colorDropdown.value = '';
        updateSortIndicators(currentSortBy, currentSortOrder);
        updateCharts();
      });
    }
  } catch (error) {
    hideLoading();
    console.error('Failed to initialize:', error);
    d3.select('#d3-bar-chart').html('<div class="alert alert-danger">Failed to load card summary.</div>');
  }
});