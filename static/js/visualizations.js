// D3.js visualizations for card color and type breakdown with filtering, dropdown, and loading indicator

document.addEventListener('DOMContentLoaded', function() {
  let allCards = [];
  let currentColorFilter = null;
  let currentTypeFilter = null;
  let previousColorFilter = null;
  const PAGE_SIZE = 10; // Show 10 cards per page in table
  let currentPage = 1;
  let totalFilteredCards = 0;
  let drillDownData = null; // For drilling into "Other" types
  let currentSortBy = 'name'; // Default sort column
  let currentSortOrder = 'asc'; // 'asc' or 'desc'

  // Reset button and dropdown logic
  const resetBtn = document.getElementById('reset-filters-btn');
  const colorDropdown = document.getElementById('color-filter-dropdown');

  // Show loading spinner
  showLoading();

  // Fetch summary stats for all cards (not just the first page)
  fetch('/api/cards/summary')
    .then(res => res.json())
    .then(summary => {
      window.cardSummary = summary;
      hideLoading();
      setupViz();
    })
    .catch(() => {
      hideLoading();
      d3.select('#d3-bar-chart').html('<div class="alert alert-danger">Failed to load card summary.</div>');
    });

  function setupViz() {
    // Load saved filters and sorting from localStorage
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
    // Map abbreviations and normalize color names
    const colorNorm = {
      'w': 'White', 'white': 'White',
      'u': 'Blue',  'blue': 'Blue',
      'b': 'Black', 'black': 'Black',
      'r': 'Red',   'red': 'Red',
      'g': 'Green', 'green': 'Green'
    };
    function getColorKey(card) {
      let colorKey = 'Colorless';
      if (Array.isArray(card.colors)) {
        if (card.colors.length === 1) {
          const raw = String(card.colors[0] || '').toLowerCase();
          colorKey = colorNorm[raw] || 'Other';
        } else if (card.colors.length > 1) {
          colorKey = 'Many';
        }
      }
      return colorKey;
    }
    // Use backend summary for color counts if available (always prefer backend data)
    function getColorCounts(cards) {
      if (window.cardSummary && window.cardSummary.color_counts) {
        return window.cardSummary.color_counts;
      }
      // fallback to local calculation
      const colorCounts = {};
      for (const card of cards) {
        const colorKey = getColorKey(card);
        colorCounts[colorKey] = (colorCounts[colorKey] || 0) + 1;
      }
      return colorCounts;
    }
    const colorOrder = ['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless', 'Many', 'Other'];
    const colorMap = {
      'White': 'rgb(249, 250, 244)', // white
      'Blue': 'rgb(41, 104, 171)',   // blue
      'Black': 'rgb(24, 11, 0)',     // dark brown
      'Red': 'rgb(211, 32, 42)',     // red
      'Green': 'rgb(0, 115, 62)',    // green
      'Colorless': 'rgb(166, 159, 157)', // gray
      'Many': 'rgb(235, 159, 130)',  // peach
      'Other': 'rgb(196, 211, 202)'  // light green (fallback for other)
    };
    async function updateCharts() {
      // Show loading spinners
      d3.select('#d3-bar-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
      d3.select('#d3-donut-chart').html('<div class="d-flex justify-content-center align-items-center" style="height:320px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
      // Hide tooltip if present
      d3.selectAll('.d3-tooltip').style('opacity', 0);
      // Always show reset button, but disable if no filter
      const anyFilter = currentColorFilter || currentTypeFilter;
      if (resetBtn) {
        resetBtn.disabled = !anyFilter;
        resetBtn.classList.toggle('btn-secondary', !anyFilter);
        resetBtn.classList.toggle('btn-primary', !!anyFilter);
      }
      // Keep dropdown in sync
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
        const res = await fetch(`/api/cards/summary?${queryParams}`);
        if (res.ok) {
          const summary = await res.json();
          window.cardSummary = summary;
        } else {
          console.error('Failed to fetch summary');
        }
      } catch (err) {
        console.error('Error fetching summary:', err);
      }

      let filteredCards = allCards;
      if (currentColorFilter) {
        if (currentColorFilter === 'Many') {
          filteredCards = allCards.filter(card => {
            const key = getColorKey(card);
            return key === 'Many';
          });
        } else {
          filteredCards = allCards.filter(card => {
            const key = getColorKey(card);
            if (key === currentColorFilter) return true;
            if (key === 'Many' && Array.isArray(card.colors) && card.colors.map(c => colorNorm[String(c).toLowerCase()] || c).includes(currentColorFilter)) return true;
            return false;
          });
        }
      }
      if (currentTypeFilter) {
        filteredCards = filteredCards.filter(card => {
          let t = (card.type_line || '').split(' — ')[0].trim();
          if (!t) t = 'Other';
          return t === currentTypeFilter;
        });
      }
      // Update active filters display
      let filterText = '';
      if (currentColorFilter) filterText += `<span class="badge bg-primary me-2">${currentColorFilter}</span>`;
      if (currentTypeFilter) filterText += `<span class="badge bg-secondary">${currentTypeFilter}</span>`;
      d3.select('#active-filters').html(filterText || '<span class="text-muted">No active filters</span>');

      // Save filters to localStorage for cross-page filtering
      const filters = {
        color: currentColorFilter,
        type: currentTypeFilter,
        sortBy: currentSortBy,
        sortOrder: currentSortOrder
      };
      localStorage.setItem('mtgCardFilters', JSON.stringify(filters));

      // Bar chart: show color breakdown of filtered cards
      const colorCounts = getColorCounts(filteredCards);
      const chartData = colorOrder.map(color => ({
        color,
        count: colorCounts[color] || 0,
        fill: colorMap[color]
      }));
      renderBarChart(chartData);

      // Always render donut chart using backend summary
      renderDonutChart([]);

      // Update filtered cards table
      fetchFilteredCards(1); // Reset to first page when filters change
    }
    // Format numbers as XX.Xk for thousands
    function formatCount(n) {
      if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
      return n;
    }
    
    // Fetch and display filtered cards in table
    async function fetchFilteredCards(page = 1) {
      try {
        // Show loading state
        const tbody = document.querySelector('#filtered-cards-table tbody');
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center"><div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div></td></tr>';
        }
        
        // Build query string with current filters and pagination
        let queryParams = `page=${page}&page_size=${PAGE_SIZE}&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;
        if (currentColorFilter) {
          if (currentColorFilter === 'Many' && previousColorFilter && previousColorFilter !== 'Many') {
            queryParams += `&color=${encodeURIComponent(previousColorFilter)}&many=true`;
          } else {
            queryParams += `&color=${encodeURIComponent(currentColorFilter)}`;
          }
        }
        if (currentTypeFilter) {
          queryParams += `&type=${encodeURIComponent(currentTypeFilter)}`;
        }
        
        const res = await fetch(`/api/cards?${queryParams}`);
        
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const data = await res.json();
        
        // Update count badge and pagination variables
        totalFilteredCards = data.total;
        currentPage = data.page;
        const countBadge = document.getElementById('filtered-count');
        if (countBadge) {
          countBadge.textContent = totalFilteredCards.toLocaleString();
        }
        
        renderFilteredCardsTable(data.cards);
        renderPagination();
      } catch (err) {
        console.error('Failed to fetch filtered cards:', err);
        // Show error in table
        const tbody = document.querySelector('#filtered-cards-table tbody');
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load cards</td></tr>';
        }
      }
    }
    
    // Render filtered cards table
    function renderFilteredCardsTable(cards) {
      const tbody = document.querySelector('#filtered-cards-table tbody');
      if (!tbody) return;
      
      if (!cards || cards.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No cards match the current filters</td></tr>';
        return;
      }
      
      tbody.innerHTML = '';
      
      // Color mapping for display
      const colorNames = {
        'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'
      };
      
      for (let i = 0; i < cards.length; i++) {
        const card = cards[i];
        
        // Format colors
        let colorDisplay = 'Colorless';
        if (card.colors && card.colors.length > 0) {
          if (card.colors.length === 1) {
            colorDisplay = colorNames[card.colors[0]] || card.colors[0];
          } else {
            colorDisplay = 'Many';
          }
        }
        
        // Format type (take first part)
        const typeDisplay = card.type_line ? card.type_line.split(' — ')[0] : '';
        
        // Format price
        const priceDisplay = card.price !== undefined ? '$' + card.price.toLocaleString() : '';
        
        // Format image
        const imageDisplay = card.image_uris && card.image_uris.normal 
          ? `<img src="${card.image_uris.normal}" alt="${card.name}" style="max-width:50px;max-height:60px;border-radius:6px;border:2px solid rgba(185,131,255,0.2);box-shadow:0 2px 4px rgba(0,0,0,0.1);cursor:pointer;transition:all 0.2s ease;" onmouseover="this.style.transform='scale(1.05)';this.style.boxShadow='0 4px 8px rgba(185,131,255,0.3)';" onmouseout="this.style.transform='scale(1)';this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)';" onclick="showCardModal('${card.name}', '${card.image_uris.normal}', '${card.type_line || ''}', '${card.set || ''}', '${card.rarity || ''}', '${priceDisplay}')">`
          : '';
        
        const row = document.createElement('tr');
        row.style.cssText = `
          transition: all 0.2s ease;
          border-bottom: 1px solid rgba(255,255,255,0.1);
        `;
        row.onmouseover = function() {
          this.style.backgroundColor = 'rgba(185, 131, 255, 0.05)';
          this.style.transform = 'translateY(-1px)';
          this.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        };
        row.onmouseout = function() {
          this.style.backgroundColor = 'transparent';
          this.style.transform = 'translateY(0)';
          this.style.boxShadow = 'none';
        };
        
        row.innerHTML = `
          <td style="padding:12px 16px;font-weight:600;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;">${card.name || ''}</td>
          <td style="padding:12px 16px;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;">${typeDisplay}</td>
          <td style="padding:12px 16px;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;">${colorDisplay}</td>
          <td style="padding:12px 16px;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;">${card.rarity || ''}</td>
          <td style="padding:12px 16px;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;">${priceDisplay}</td>
          <td style="padding:12px 16px;text-align:center;">${imageDisplay}</td>
        `;
        tbody.appendChild(row);
      }
    }
    
    // Render pagination controls
    function renderPagination() {
      const pageCount = Math.max(1, Math.ceil(totalFilteredCards / PAGE_SIZE));
      const pagination = document.getElementById('filtered-pagination');
      if (!pagination) return;
      
      pagination.innerHTML = '';
      
      if (totalFilteredCards <= PAGE_SIZE) {
        // Don't show pagination if all cards fit on one page
        return;
      }

      // Left arrow
      const liPrev = document.createElement('li');
      liPrev.className = 'page-item' + (currentPage === 1 ? ' disabled' : '');
      const aPrev = document.createElement('a');
      aPrev.className = 'page-link';
      aPrev.href = '#';
      aPrev.innerHTML = '&laquo;';
      aPrev.onclick = (e) => {
        e.preventDefault();
        if (currentPage > 1) fetchFilteredCards(currentPage - 1);
      };
      liPrev.appendChild(aPrev);
      pagination.appendChild(liPrev);

      // Page input
      const liInput = document.createElement('li');
      liInput.className = 'page-item';
      const input = document.createElement('input');
      input.type = 'number';
      input.min = 1;
      input.max = pageCount;
      input.value = currentPage;
      input.style = 'width: 60px; text-align: center; display: inline-block;';
      input.className = 'form-control';
      input.onkeydown = (e) => {
        if (e.key === 'Enter') {
          let val = parseInt(input.value);
          if (!isNaN(val) && val >= 1 && val <= pageCount) {
            fetchFilteredCards(val);
          } else {
            input.value = currentPage;
          }
        }
      };
      input.onblur = () => {
        let val = parseInt(input.value);
        if (!isNaN(val) && val >= 1 && val <= pageCount && val !== currentPage) {
          fetchFilteredCards(val);
        } else {
          input.value = currentPage;
        }
      };
      liInput.appendChild(input);
      pagination.appendChild(liInput);

      // Total pages display
      const liTotal = document.createElement('li');
      liTotal.className = 'page-item disabled';
      const spanTotal = document.createElement('span');
      spanTotal.className = 'page-link';
      spanTotal.style = 'background: none; border: none; color: #333;';
      spanTotal.textContent = ` / ${pageCount}`;
      liTotal.appendChild(spanTotal);
      pagination.appendChild(liTotal);

      // Right arrow
      const liNext = document.createElement('li');
      liNext.className = 'page-item' + (currentPage === pageCount ? ' disabled' : '');
      const aNext = document.createElement('a');
      aNext.className = 'page-link';
      aNext.href = '#';
      aNext.innerHTML = '&raquo;';
      aNext.onclick = (e) => {
        e.preventDefault();
        if (currentPage < pageCount) fetchFilteredCards(currentPage + 1);
      };
      liNext.appendChild(aNext);
      pagination.appendChild(liNext);
    }
    function renderBarChart(data) {
      // Clear any existing content
      d3.select('#d3-bar-chart').html('');
      
      // Responsive width: 58% of .viz-row or 100% on mobile
      const container = document.getElementById('d3-bar-chart');
      let width = container ? container.offsetWidth : 600;
      let height = 350;
      let isMobile = window.innerWidth < 900;
      if (isMobile) {
        width = Math.min(window.innerWidth * 0.98, 420);
        height = 320;
      }

      // Tooltip div with modern styling
      const tooltip = d3.select('body').append('div')
        .attr('class', 'd3-tooltip')
        .style('position', 'absolute')
        .style('background', 'linear-gradient(135deg, #2D1B4A 0%, #1a0d2e 100%)')
        .style('color', '#F3F0FF')
        .style('padding', '12px 16px')
        .style('border-radius', '12px')
        .style('box-shadow', '0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px rgba(185,131,255,0.2)')
        .style('pointer-events', 'none')
        .style('font-size', '0.9rem')
        .style('font-weight', '500')
        .style('font-family', 'system-ui, -apple-system, sans-serif')
        .style('backdrop-filter', 'blur(10px)')
        .style('border', '1px solid rgba(185,131,255,0.3)')
        .style('opacity', 0);

      if (isMobile) {
        // Horizontal bar chart for mobile
        const margin = {top: 30, right: 30, bottom: 40, left: 100};
        const svg = d3.select('#d3-bar-chart')
          .append('svg')
          .attr('width', '100%')
          .attr('height', height)
          .attr('viewBox', `0 0 ${width} ${height}`)
          .attr('preserveAspectRatio', 'xMinYMin meet');

        const y = d3.scaleBand()
          .domain(data.map(d => d.color))
          .range([margin.top, height - margin.bottom])
          .padding(0.2);
        const x = d3.scaleLinear()
          .domain([0, d3.max(data, d => d.count) || 1])
          .nice()
          .range([margin.left, width - margin.right]);

        svg.append('g')
          .attr('transform', `translate(0,${height - margin.bottom})`)
          .call(d3.axisBottom(x).ticks(Math.max(3, Math.floor(width/80))))
          .selectAll('text')
          .attr('fill', '#F3F0FF')
          .attr('font-weight', 600);

        svg.append('g')
          .attr('transform', `translate(${margin.left},0)`)
          .call(d3.axisLeft(y))
          .selectAll('text')
          .attr('fill', '#F3F0FF')
          .attr('font-weight', 600);

        svg.selectAll('.bar')
          .data(data)
          .enter()
          .append('rect')
          .attr('class', 'bar')
          .attr('y', d => y(d.color))
          .attr('x', margin.left)
          .attr('height', y.bandwidth())
          .attr('width', d => x(d.count) - margin.left)
          .attr('fill', d => d.fill)
          .attr('stroke', '#ffffff')
          .attr('stroke-width', 2)
          .attr('rx', 4)
          .attr('opacity', 0.9)
          .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.1))')
          .style('cursor', 'pointer')
          .on('mouseover', function(event, d) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('opacity', 1)
              .attr('stroke', '#B983FF')
              .attr('stroke-width', 3)
              .style('filter', 'drop-shadow(0 3px 6px rgba(185, 131, 255, 0.2))');
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip.html(`<strong>${d.color}</strong><br>Count: ${formatCount(d.count)}`)
              .style('left', (event.pageX + 15) + 'px')
              .style('top', (event.pageY - 35) + 'px');
          })
          .on('mousemove', function(event) {
            tooltip.style('left', (event.pageX + 15) + 'px')
                   .style('top', (event.pageY - 35) + 'px');
          })
          .on('mouseout', function() {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('opacity', 0.9)
              .attr('stroke', '#ffffff')
              .attr('stroke-width', 2)
              .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.1))');
            tooltip.transition().duration(300).style('opacity', 0);
          })
          .on('click', function(event, d) {
            if (currentColorFilter === d.color) {
              currentColorFilter = null;
              previousColorFilter = null;
            } else {
              previousColorFilter = currentColorFilter;
              currentColorFilter = d.color;
            }
            if (colorDropdown) colorDropdown.value = currentColorFilter || '';
            updateCharts();
          });

        svg.append('text')
          .attr('x', width / 2)
          .attr('y', margin.top - 10)
          .attr('text-anchor', 'middle')
          .attr('font-size', '20px')
          .attr('font-weight', 'bold')
          .attr('fill', '#B983FF')
          .text('Card Count by Color');
        // X axis label
        svg.append('text')
          .attr('x', width / 2)
          .attr('y', height - 10)
          .attr('text-anchor', 'middle')
          .attr('font-size', '14px')
          .attr('fill', '#F3F0FF')
          .text('Count');
        // Y axis label
        svg.append('text')
          .attr('transform', `rotate(-90)`)
          .attr('y', 18)
          .attr('x', -height / 2)
          .attr('text-anchor', 'middle')
          .attr('font-size', '14px')
          .attr('fill', '#F3F0FF')
          .text('Color');
      } else {
        // Vertical bar chart for desktop
        const margin = {top: 30, right: 20, bottom: 50, left: 60};
        const svg = d3.select('#d3-bar-chart')
          .append('svg')
          .attr('width', '100%')
          .attr('height', height)
          .attr('viewBox', `0 0 ${width} ${height}`)
          .attr('preserveAspectRatio', 'xMinYMin meet');

        const x = d3.scaleBand()
          .domain(data.map(d => d.color))
          .range([margin.left, width - margin.right])
          .padding(0.2);
        const y = d3.scaleLinear()
          .domain([0, d3.max(data, d => d.count) || 1])
          .nice()
          .range([height - margin.bottom, margin.top]);

        svg.append('g')
          .attr('transform', `translate(0,${height - margin.bottom})`)
          .call(d3.axisBottom(x))
          .selectAll('text')
          .attr('fill', '#F3F0FF')
          .attr('font-weight', 600);

        svg.append('g')
          .attr('transform', `translate(${margin.left},0)`)
          .call(d3.axisLeft(y))
          .selectAll('text')
          .attr('fill', '#F3F0FF')
          .attr('font-weight', 600);

        svg.selectAll('.bar')
          .data(data)
          .enter()
          .append('rect')
          .attr('class', 'bar')
          .attr('x', d => x(d.color))
          .attr('y', d => y(d.count))
          .attr('width', x.bandwidth())
          .attr('height', d => y(0) - y(d.count))
          .attr('fill', d => d.fill)
          .attr('stroke', '#ffffff')
          .attr('stroke-width', 2)
          .attr('rx', 4)
          .attr('opacity', 0.9)
          .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.1))')
          .style('cursor', 'pointer')
          .on('mouseover', function(event, d) {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('opacity', 1)
              .attr('stroke', '#B983FF')
              .attr('stroke-width', 3)
              .style('filter', 'drop-shadow(0 3px 6px rgba(185, 131, 255, 0.2))');
            tooltip.transition().duration(200).style('opacity', 1);
            tooltip.html(`<strong>${d.color}</strong><br>Count: ${formatCount(d.count)}`)
              .style('left', (event.pageX + 15) + 'px')
              .style('top', (event.pageY - 35) + 'px');
          })
          .on('mousemove', function(event) {
            tooltip.style('left', (event.pageX + 15) + 'px')
                   .style('top', (event.pageY - 35) + 'px');
          })
          .on('mouseout', function() {
            d3.select(this)
              .transition()
              .duration(200)
              .attr('opacity', 0.9)
              .attr('stroke', '#ffffff')
              .attr('stroke-width', 2)
              .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.1))');
            tooltip.transition().duration(300).style('opacity', 0);
          })
          .on('click', function(event, d) {
            if (currentColorFilter === d.color) {
              currentColorFilter = null;
              previousColorFilter = null;
            } else {
              previousColorFilter = currentColorFilter;
              currentColorFilter = d.color;
            }
            if (colorDropdown) colorDropdown.value = currentColorFilter || '';
            updateCharts();
          });

        // Y axis label
        svg.append('text')
          .attr('transform', 'rotate(-90)')
          .attr('y', 15)
          .attr('x', -height / 2)
          .attr('text-anchor', 'middle')
          .attr('font-size', '14px')
          .attr('fill', '#F3F0FF')
          .text('Count');
        // X axis label
        svg.append('text')
          .attr('x', width / 2)
          .attr('y', height - 10)
          .attr('text-anchor', 'middle')
          .attr('font-size', '14px')
          .attr('fill', '#F3F0FF')
          .text('Color');
      }
    }
  function renderDonutChart(cards) {
      // Clear any existing content
      d3.select('#d3-donut-chart').html('');
      
      // Always use backend summary for type counts if available
      let typeCounts = {};
      let total = 0;
      if (window.cardSummary && window.cardSummary.type_counts) {
        typeCounts = window.cardSummary.type_counts;
        total = window.cardSummary.total || 0;
      } else {
        for (const card of cards) {
          let t = (card.type_line || '').split(' — ')[0].trim();
          if (!t) t = 'Other';
          typeCounts[t] = (typeCounts[t] || 0) + 1;
          total++;
        }
      }
      
      let data;
      let remainingEntries = [];
      
      if (drillDownData) {
        // Use drill-down data
        data = drillDownData;
      } else {
        // Prepare data with priority types always included
        let entries = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
        const priorityTypes = ['Legendary Creature', 'Planeswalker'];
        let topEntries = [];
        remainingEntries = [...entries];
        
        // First, add priority types if they exist
        for (let pt of priorityTypes) {
          let idx = remainingEntries.findIndex(e => e[0] === pt);
          if (idx !== -1) {
            topEntries.push(remainingEntries.splice(idx, 1)[0]);
          }
        }
        
        // Then add top remaining to fill to 8
        let numToAdd = 8 - topEntries.length;
        topEntries = topEntries.concat(remainingEntries.splice(0, numToAdd));
        
        // Sort topEntries by count desc
        topEntries.sort((a, b) => b[1] - a[1]);
        
        // Calculate other count and add Other if needed
        let otherCount = remainingEntries.reduce((sum, e) => sum + e[1], 0);
        if (otherCount > 0) {
          topEntries.push(['Other', otherCount]);
        }
        
        data = topEntries.map(([type, count]) => ({type, count}));
      }
      
      const colors = d3.schemeTableau10.concat(['#B983FF', '#9D4EDD', '#18122B']);
      // Use container width for responsive sizing
      const container = document.getElementById('d3-donut-chart');
      let width = container ? container.offsetWidth : 350;
      let height = 350;
      if (window.innerWidth < 900) {
        width = Math.min(window.innerWidth * 0.98, 320);
        height = 320;
      }
      const radius = Math.min(width, height) / 2 - 10;
      const svg = d3.select('#d3-donut-chart')
        .append('svg')
        .attr('width', '100%')
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .append('g')
        .attr('transform', `translate(${width / 2},${height / 2})`);

      const pie = d3.pie().value(d => d.count);
      const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
      // Remove any existing donut tooltips before creating a new one
      d3.selectAll('.d3-tooltip.donut').remove();
      const tooltip = d3.select('body').append('div')
        .attr('class', 'd3-tooltip donut')
        .style('position', 'absolute')
        .style('background', 'linear-gradient(135deg, #2D1B4A 0%, #1a0d2e 100%)')
        .style('color', '#F3F0FF')
        .style('padding', '12px 16px')
        .style('border-radius', '12px')
        .style('box-shadow', '0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px rgba(185,131,255,0.2)')
        .style('pointer-events', 'none')
        .style('font-size', '0.9rem')
        .style('font-weight', '500')
        .style('font-family', 'system-ui, -apple-system, sans-serif')
        .style('backdrop-filter', 'blur(10px)')
        .style('border', '1px solid rgba(185,131,255,0.3)')
        .style('opacity', 0);

      svg.selectAll('path')
        .data(pie(data))
        .enter()
        .append('path')
        .attr('d', arc)
        .attr('fill', (d, i) => colors[i % colors.length])
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 3)
        .attr('opacity', 0.9)
        .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))')
        .attr('cursor', 'pointer')
        .attr('tabindex', 0)
        .attr('role', 'button')
        .attr('aria-label', (d) => `${d.data.type}: ${formatCount(d.data.count)} cards`)
        .on('mouseover', function(event, d) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('opacity', 1)
            .attr('stroke', '#B983FF')
            .attr('stroke-width', 4)
            .style('filter', 'drop-shadow(0 4px 8px rgba(185, 131, 255, 0.3))');
          tooltip.transition().duration(200).style('opacity', 1);
          tooltip.html(`<strong>${d.data.type}</strong><br>Count: ${formatCount(d.data.count)}`)
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 35) + 'px');
        })
        .on('focus', function(event, d) {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('opacity', 1)
            .attr('stroke', '#B983FF')
            .attr('stroke-width', 4)
            .style('filter', 'drop-shadow(0 4px 8px rgba(185, 131, 255, 0.3))');
        })
        .on('blur', function() {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('opacity', 0.9)
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 3)
            .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))');
        })
        .on('mousemove', function(event) {
          tooltip.style('left', (event.pageX + 15) + 'px')
                 .style('top', (event.pageY - 35) + 'px');
        })
        .on('mouseout', function() {
          d3.select(this)
            .transition()
            .duration(200)
            .attr('opacity', 0.9)
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 3)
            .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))');
          tooltip.transition().duration(300).style('opacity', 0);
          setTimeout(() => { tooltip.remove(); }, 320);
        })
        .on('click', function(event, d) {
          if (d.data.type === 'Other' && !drillDownData) {
            // Drill down into Other types
            drillDownData = remainingEntries
              .filter(([type]) => type !== 'Other')
              .map(([type, count]) => ({type, count}));
            currentTypeFilter = null; // Clear type filter when drilling down
            updateCharts();
          } else {
            // Exit drill-down mode if active and apply filter
            if (drillDownData) {
              drillDownData = null;
            }
            if (currentTypeFilter === d.data.type) {
              currentTypeFilter = null;
            } else {
              currentTypeFilter = d.data.type;
            }
            updateCharts();
          }
        })
        .on('keydown', function(event, d) {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            if (d.data.type === 'Other' && !drillDownData) {
              drillDownData = remainingEntries
                .filter(([type]) => type !== 'Other')
                .map(([type, count]) => ({type, count}));
              updateCharts();
            } else {
              // Exit drill-down mode if active and apply filter
              if (drillDownData) {
                drillDownData = null;
              }
              if (currentTypeFilter === d.data.type) {
                currentTypeFilter = null;
              } else {
                currentTypeFilter = d.data.type;
              }
              updateCharts();
            }
          }
        });
      // Center label: total with modern styling
      const centerGroup = svg.append('g')
        .attr('class', 'center-label');
      
      centerGroup.append('circle')
        .attr('r', radius * 0.4)
        .attr('fill', 'rgba(185, 131, 255, 0.1)')
        .attr('stroke', 'rgba(185, 131, 255, 0.3)')
        .attr('stroke-width', 2);
      
      centerGroup.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', -5)
        .attr('font-size', '2.4rem')
        .attr('font-weight', '700')
        .attr('fill', '#B983FF')
        .style('font-family', 'system-ui, -apple-system, sans-serif')
        .text(formatCount(drillDownData ? drillDownData.reduce((sum, d) => sum + d.count, 0) : total));
      
      centerGroup.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 25)
        .attr('font-size', '1rem')
        .attr('font-weight', '500')
        .attr('fill', '#F3F0FF')
        .style('font-family', 'system-ui, -apple-system, sans-serif')
        .text(drillDownData ? 'Other Types' : 'Total Cards');
      // Legend: single column, clickable
      const legendContainer = d3.select('#d3-legend');
      legendContainer.selectAll('*').remove();
      
      if (drillDownData) {
        // Add back button with modern styling
        legendContainer.append('div')
          .attr('class', 'd3-legend-item back-button')
          .style('color', '#B983FF')
          .style('cursor', 'pointer')
          .style('font-weight', '600')
          .style('font-size', '0.95rem')
          .style('margin-bottom', '12px')
          .style('padding', '8px 12px')
          .style('background', 'rgba(185, 131, 255, 0.1)')
          .style('border-radius', '8px')
          .style('border', '1px solid rgba(185, 131, 255, 0.3)')
          .style('transition', 'all 0.2s ease')
          .on('mouseover', function() {
            d3.select(this)
              .style('background', 'rgba(185, 131, 255, 0.2)')
              .style('border-color', 'rgba(185, 131, 255, 0.5)');
          })
          .on('mouseout', function() {
            d3.select(this)
              .style('background', 'rgba(185, 131, 255, 0.1)')
              .style('border-color', 'rgba(185, 131, 255, 0.3)');
          })
          .on('click', function() {
            drillDownData = null;
            updateCharts();
          })
          .html('← Back to Overview');
      }
      
      data.forEach((d, i) => {
        const legendItem = legendContainer.append('div')
          .attr('class', 'd3-legend-item' + (currentTypeFilter === d.type ? ' active' : ''))
          .style('color', currentTypeFilter === d.type ? '#ffffff' : '#F3F0FF')
          .style('cursor', 'pointer')
          .style('font-size', '0.9rem')
          .style('font-weight', '500')
          .style('padding', '6px 8px')
          .style('margin-bottom', '4px')
          .style('border-radius', '6px')
          .style('transition', 'all 0.2s ease')
          .style('font-family', 'system-ui, -apple-system, sans-serif');
        
        if (currentTypeFilter === d.type) {
          legendItem.style('background', 'rgba(185, 131, 255, 0.2)')
                  .style('border', '1px solid rgba(185, 131, 255, 0.4)');
        } else {
          legendItem.on('mouseover', function() {
            d3.select(this).style('background', 'rgba(255, 255, 255, 0.05)');
          })
          .on('mouseout', function() {
            d3.select(this).style('background', 'transparent');
          });
        }
        
        legendItem.on('click', function() {
          if (d.type === 'Other' && !drillDownData) {
            // Drill down into Other types
            drillDownData = remainingEntries
              .filter(([type]) => type !== 'Other')
              .map(([type, count]) => ({type, count}));
            currentTypeFilter = null; // Clear type filter when drilling down
            updateCharts();
          } else {
            // Exit drill-down mode if active and apply filter
            if (drillDownData) {
              drillDownData = null;
            }
            if (currentTypeFilter === d.type) {
              currentTypeFilter = null;
            } else {
              currentTypeFilter = d.type;
            }
            updateCharts();
          }
        })
        .html(`<span style="display:inline-block;width:12px;height:12px;background:${colors[i % colors.length]};border-radius:50%;margin-right:8px;border:2px solid rgba(255,255,255,0.3);"></span>${d.type}`);
      });
    }
    // Initial render
    updateCharts();

    // Add sorting functionality to table headers
    function setupTableSorting() {
      const table = document.getElementById('filtered-cards-table');
      if (!table) return;
      
      const headers = table.querySelectorAll('th.sortable');
      headers.forEach(header => {
        header.addEventListener('click', function() {
          const sortBy = this.dataset.sort;
          if (currentSortBy === sortBy) {
            // Toggle sort order
            currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
          } else {
            // New sort column, default to ascending
            currentSortBy = sortBy;
            currentSortOrder = 'asc';
          }
          updateSortIndicators();
          fetchFilteredCards(1); // Reset to first page when sorting
        });
      });
    }
    
    function updateSortIndicators() {
      // Clear all indicators
      document.querySelectorAll('.sort-indicator').forEach(indicator => {
        indicator.className = 'sort-indicator';
      });
      
      // Set active indicator
      const activeIndicator = document.getElementById(`sort-${currentSortBy}`);
      if (activeIndicator) {
        activeIndicator.classList.add(currentSortOrder === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    }
    
    setupTableSorting();
    updateSortIndicators();

    // Make dropdown actually filter the charts
    if (colorDropdown) {
      colorDropdown.addEventListener('change', function() {
        currentColorFilter = colorDropdown.value || null;
        // Save filters to localStorage
        const filters = {
          color: currentColorFilter,
          type: currentTypeFilter,
          sortBy: currentSortBy,
          sortOrder: currentSortOrder
        };
        localStorage.setItem('mtgCardFilters', JSON.stringify(filters));
        updateCharts();
      });
    }

    // Fix reset button to always clear filter and restore all charts
    if (resetBtn) {
      resetBtn.addEventListener('click', function() {
        currentColorFilter = null;
        currentTypeFilter = null;
        previousColorFilter = null;
        drillDownData = null;
        currentSortBy = 'name';
        currentSortOrder = 'asc';
        currentPage = 1;
        if (colorDropdown) colorDropdown.value = '';
        updateSortIndicators();
        // Save cleared filters to localStorage
        const filters = {
          color: null,
          type: null,
          sortBy: 'name',
          sortOrder: 'asc'
        };
        localStorage.setItem('mtgCardFilters', JSON.stringify(filters));
        if (typeof updateCharts === 'function') updateCharts();
      });
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

  // Card modal function
  window.showCardModal = function(name, imageUrl, typeLine, set, rarity, price) {
    // Create modal HTML
    const modalHtml = `
      <div class="modal fade" id="cardModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content bg-dark text-light">
            <div class="modal-header">
              <h5 class="modal-title">${name}</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body text-center">
              <img src="${imageUrl}" alt="${name}" class="img-fluid mb-3" style="max-height: 400px;">
              <div class="row">
                <div class="col-md-6">
                  <p><strong>Type:</strong> ${typeLine}</p>
                  <p><strong>Set:</strong> ${set}</p>
                </div>
                <div class="col-md-6">
                  <p><strong>Rarity:</strong> ${rarity}</p>
                  <p><strong>Price:</strong> ${price}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Remove existing modal if present
    const existingModal = document.getElementById('cardModal');
    if (existingModal) {
      existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('cardModal'));
    modal.show();
  };
});
