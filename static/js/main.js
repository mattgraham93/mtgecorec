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
  selectedColors,
  exclusiveColors,
  setCurrentPage,
  setTotalFilteredCards,
  setCurrentSortBy,
  setCurrentSortOrder,
  setCurrentColorFilter,
  setCurrentTypeFilter,
  setPreviousColorFilter,
  setDrillDownData,
  setSelectedColors,
  setExclusiveColors,
  loadStateFromStorage,
  saveStateToStorage,
  resetFilters
} from './state.js';

import { fetchCardSummary, fetchFilteredCards } from './api.js';

import { renderBarChart, renderDonutChart, getColorCounts, colorOrder, colorMap } from './charts.js';

import { renderFilteredCardsTable, renderPagination, setupTableSorting, updateSortIndicators } from './table.js';

// Debounce and request management
let updateChartsTimeout = null;
let currentSummaryController = null;
let currentCardsController = null;
let tableLoaded = false; // Track if table has been loaded

// Debounced update charts function
function debouncedUpdateCharts(immediate = false) {
  // Cancel any pending update
  if (updateChartsTimeout) {
    clearTimeout(updateChartsTimeout);
  }
  
  // Cancel any pending API requests
  if (currentSummaryController) {
    currentSummaryController.abort();
  }
  if (currentCardsController) {
    currentCardsController.abort();
  }
  
  if (immediate) {
    // Execute immediately
    updateCharts();
  } else {
    // Debounce for 300ms
    updateChartsTimeout = setTimeout(() => {
      updateCharts();
    }, 300);
  }
}

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
async function updateCharts(providedSummary = null) {
  // Show loading spinners
  d3.select('#d3-bar-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
  d3.select('#d3-donut-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
  // Hide tooltip if present
  d3.selectAll('.d3-tooltip').style('opacity', 0);

  // Update reset button
  const resetBtn = document.getElementById('reset-filters-btn');
  const anyFilter = (currentColorFilter || currentTypeFilter) || (selectedColors && selectedColors.length > 0);
  if (resetBtn) {
    resetBtn.disabled = !anyFilter;
    resetBtn.classList.toggle('btn-secondary', !anyFilter);
    resetBtn.classList.toggle('btn-primary', !!anyFilter);
  }

  // Fetch filtered summary
  let queryParams = '';

  // Use new multi-color filtering if colors are selected
  if (selectedColors && selectedColors.length > 0) {
    selectedColors.forEach(color => {
      queryParams += `colors=${encodeURIComponent(color)}&`;
    });
    if (exclusiveColors) {
      queryParams += `exclusive_colors=true&`;
    }
  } else if (currentColorFilter) {
    // Fallback to old single color filter for backward compatibility
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

  let summary;
  if (providedSummary && !queryParams) {
    // Use provided summary if no filters are applied
    summary = providedSummary;
  } else {
    try {
      // Cancel any previous summary request
      if (currentSummaryController) {
        currentSummaryController.abort();
      }
      currentSummaryController = new AbortController();
      
      summary = await fetchCardSummary(queryParams, currentSummaryController.signal);
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Error fetching summary:', err);
      }
      return; // Don't continue if summary failed
    } finally {
      currentSummaryController = null;
    }
  }

  window.cardSummary = summary;

  // Update active filters display
  let filterText = '';
  if (selectedColors && selectedColors.length > 0) {
    const modeText = exclusiveColors ? ' (exactly)' : '';
    selectedColors.forEach(color => {
      filterText += `<span class="badge bg-primary me-2">${color}${modeText}</span>`;
    });
  } else if (currentColorFilter) {
    filterText += `<span class="badge bg-primary me-2">${currentColorFilter}</span>`;
  }
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

  // Update table if it's loaded or if we have filters applied
  if (window.tableLoaded || (selectedColors && selectedColors.length > 0) || currentColorFilter || currentTypeFilter) {
    await fetchAndRenderTable(1); // Reset to first page
  }
}

// Handle color click from bar chart
function handleColorClick(color) {
  if (currentColorFilter === color) {
    setCurrentColorFilter(null);
    setPreviousColorFilter(null);
    setSelectedColors([]);
  } else {
    setPreviousColorFilter(currentColorFilter);
    setCurrentColorFilter(color);
    setSelectedColors([color]);
  }
  debouncedUpdateCharts();
}

// Handle type click from donut chart
function handleTypeClick(type, isDrillDown) {
  if (isDrillDown) {
    setDrillDownData(null);
  }
  if (currentTypeFilter === type) {
    setCurrentTypeFilter(null);
  } else {
    setCurrentTypeFilter(type);
  }
  debouncedUpdateCharts();
}

// Handle drill down
function handleDrillDown(remainingEntries) {
  setDrillDownData(remainingEntries
    .filter(([type]) => type !== 'Other')
    .map(([type, count]) => ({type, count})));
  setCurrentTypeFilter(null); // Clear type filter when drilling down
  debouncedUpdateCharts();
}

// Handle back to overview
function handleBackToOverview() {
  setDrillDownData(null);
  debouncedUpdateCharts();
}

// Fetch and render table
async function fetchAndRenderTable(page = 1) {
  try {
    // Cancel any previous cards request
    if (currentCardsController) {
      currentCardsController.abort();
    }
    currentCardsController = new AbortController();
    
    // Only show generic loading if we don't already have a count-specific message
    const tbody = document.querySelector('#filtered-cards-table tbody');
    const currentContent = tbody ? tbody.innerHTML : '';
    const hasCountMessage = currentContent.includes('Loading') && currentContent.includes('of');
    
    if (tbody && !hasCountMessage) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-4">
            <div class="d-flex align-items-center justify-content-center">
              <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                <span class="visually-hidden">Loading...</span>
              </div>
              <span class="text-muted">Loading cards...</span>
            </div>
          </td>
        </tr>
      `;
    }

    const data = await fetchFilteredCards(page, currentSortBy, currentSortOrder, currentColorFilter, currentTypeFilter, previousColorFilter, selectedColors, exclusiveColors, page === 1 ? 5 : 15, currentCardsController.signal);

    // Update count badge and pagination variables
    setTotalFilteredCards(data.total);
    setCurrentPage(data.page);
    const countBadge = document.getElementById('filtered-count');
    if (countBadge) {
      countBadge.textContent = totalFilteredCards.toLocaleString();
    }

    renderFilteredCardsTable(data.cards);
    renderPagination(totalFilteredCards, currentPage, page === 1 ? 5 : 15, handlePageChange);
  } catch (err) {
    if (err.name === 'AbortError') {
      // Request was cancelled, ignore
      return;
    }
    console.error('Failed to fetch filtered cards:', err);
    // Show error in table
    const tbody = document.querySelector('#filtered-cards-table tbody');
    if (tbody) {
      const errorMessage = err.message.includes('timed out') 
        ? 'Loading cards... (this may take a while for large datasets - up to 60 seconds)'
        : 'Failed to load cards. Please try refreshing the page.';
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-warning">${errorMessage}</td></tr>`;
    }
  } finally {
    currentCardsController = null;
  }
}

// Handle page change
function handlePageChange(page) {
  fetchAndRenderTable(page);
}

// Handle sort change
function handleSortChange(sortBy) {
  if (currentSortBy === sortBy) {
    setCurrentSortOrder(currentSortOrder === 'asc' ? 'desc' : 'asc');
  } else {
    setCurrentSortBy(sortBy);
    setCurrentSortOrder('asc');
  }
  updateSortIndicators(currentSortBy, currentSortOrder);
  fetchAndRenderTable(1); // Reset to first page when sorting
}

// Setup lazy loading for table data
function setupLazyTableLoading(initialSummary = null) {
  let tableLoaded = false;

  // Function to load table data
  const loadTableData = async () => {
    if (!tableLoaded) {
      tableLoaded = true;
      window.tableLoaded = true; // Global flag for updateCharts
      
      // First, show the total count quickly
      try {
        let summary = initialSummary;
        if (!summary) {
          summary = await fetchCardSummary();
        }
        window.cardSummary = summary;
        const totalCards = summary.total || 0;
        const countBadge = document.getElementById('filtered-count');
        if (countBadge) {
          countBadge.textContent = totalCards.toLocaleString();
        }
        
        // Show loading message with count
        const tbody = document.querySelector('#filtered-cards-table tbody');
        if (tbody && totalCards > 0) {
          const loadingCount = Math.min(5, totalCards);
          tbody.innerHTML = `
            <tr>
              <td colspan="7" class="text-center py-4">
                <div class="d-flex align-items-center justify-content-center">
                  <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                  </div>
                  <span class="text-muted">Loading ${loadingCount} of ${totalCards.toLocaleString()} cards...</span>
                </div>
              </td>
            </tr>
          `;
        }
      } catch (err) {
        console.error('Error fetching summary for count:', err);
      }
      
      // Then load the actual table data
      fetchAndRenderTable(1);
    }
  };

  // Load table immediately on page load for better UX
  loadTableData();
}

// Initialize the application
document.addEventListener('DOMContentLoaded', async function() {
  // Load saved state
  loadStateFromStorage();

  // Show initial loading
  showLoading();

  try {
    // Fetch initial summary once
    const initialSummary = await fetchCardSummary();
    window.cardSummary = initialSummary;
    hideLoading();

    // Initial render with provided summary
    await updateCharts(initialSummary);

    // Setup table sorting (but don't load table data yet)
    setupTableSorting(handleSortChange);
    updateSortIndicators(currentSortBy, currentSortOrder);

    // Setup lazy loading for table data with initial summary
    setupLazyTableLoading(initialSummary);

    // Setup event handlers
    const colorCheckboxes = document.querySelectorAll('.color-checkbox');
    const exclusiveToggle = document.getElementById('exclusive-colors-toggle');
    
    // Set initial state for exclusive toggle
    if (exclusiveToggle) {
      exclusiveToggle.checked = exclusiveColors;
    }
    
    // Set initial state for color checkboxes
    if (selectedColors && selectedColors.length > 0) {
      colorCheckboxes.forEach(checkbox => {
        if (selectedColors.includes(checkbox.value)) {
          checkbox.checked = true;
        }
      });
    }
    
    // Handle color checkbox changes
    colorCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function() {
        const checkedColors = Array.from(colorCheckboxes)
          .filter(cb => cb.checked)
          .map(cb => cb.value);
        
        if (checkedColors.length === 0) {
          // No colors selected - clear all filters
          setSelectedColors([]);
          setCurrentColorFilter(null);
          setPreviousColorFilter(null);
        } else {
          // Multiple colors selected
          setSelectedColors(checkedColors);
          setCurrentColorFilter(null);
          setPreviousColorFilter(null);
        }
        
        saveStateToStorage();
        debouncedUpdateCharts();
      });
    });
    
    // Handle exclusive colors toggle
    if (exclusiveToggle) {
      exclusiveToggle.addEventListener('change', function() {
        setExclusiveColors(exclusiveToggle.checked);
        saveStateToStorage();
        debouncedUpdateCharts();
      });
    }

    // Legacy single color dropdown (keep for backward compatibility)
    const colorDropdown = document.getElementById('color-filter-dropdown');
    if (colorDropdown) {
      colorDropdown.addEventListener('change', function() {
        setCurrentColorFilter(colorDropdown.value || null);
        // Clear multi-select when using legacy dropdown
        if (colorDropdown.value) {
          setSelectedColors([]);
          setExclusiveColors(false);
        }
        saveStateToStorage();
        debouncedUpdateCharts();
      });
    }

    const resetBtn = document.getElementById('reset-filters-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', function() {
        resetFilters();
        // Clear all color checkboxes
        const colorCheckboxes = document.querySelectorAll('.color-checkbox');
        colorCheckboxes.forEach(checkbox => {
          checkbox.checked = false;
        });
        const exclusiveToggle = document.getElementById('exclusive-colors-toggle');
        if (exclusiveToggle) exclusiveToggle.checked = false;
        updateSortIndicators(currentSortBy, currentSortOrder);
        debouncedUpdateCharts(true); // Immediate update for reset
      });
    }
  } catch (error) {
    hideLoading();
    console.error('Failed to initialize:', error);
    d3.select('#d3-bar-chart').html('<div class="alert alert-danger">Failed to load card summary.</div>');
  }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (currentSummaryController) {
    currentSummaryController.abort();
  }
  if (currentCardsController) {
    currentCardsController.abort();
  }
  if (updateChartsTimeout) {
    clearTimeout(updateChartsTimeout);
  }
});