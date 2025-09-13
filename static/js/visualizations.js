// D3.js visualizations for card color and type breakdown with filtering, dropdown, and loading indicator

document.addEventListener('DOMContentLoaded', function() {
  let allCards = [];
  let currentColorFilter = null;

  // Reset button and dropdown logic
  const resetBtn = document.getElementById('reset-filters-btn');
  const colorDropdown = document.getElementById('color-filter-dropdown');

  // Make dropdown actually filter the charts
  if (colorDropdown) {
    colorDropdown.addEventListener('change', function() {
      currentColorFilter = colorDropdown.value || null;
      if (typeof updateCharts === 'function') updateCharts();
    });
  }

  // Show loading spinner
  showLoading();

  fetch('/api/cards?page=1&page_size=10000')
    .then(res => res.json())
    .then(data => {
      allCards = data.cards || [];
      hideLoading();
      setupViz();
    })
    .catch(() => {
      hideLoading();
      d3.select('#d3-bar-chart').html('<div class="alert alert-danger">Failed to load card data.</div>');
    });

  function setupViz() {
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
    function getColorCounts(cards) {
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
    function updateCharts() {
      // Remove old SVGs and legends
      d3.select('#d3-bar-chart').selectAll('*').remove();
      d3.select('#d3-donut-chart').selectAll('*').remove();
      // Hide tooltip if present
      d3.selectAll('.d3-tooltip').style('opacity', 0);
      // Always show reset button, but disable if no filter
      if (resetBtn) {
        resetBtn.disabled = !currentColorFilter;
        resetBtn.classList.toggle('btn-secondary', !currentColorFilter);
        resetBtn.classList.toggle('btn-primary', !!currentColorFilter);
      }
      // Keep dropdown in sync
      if (colorDropdown) {
        colorDropdown.value = currentColorFilter || '';
      }
      // Filter cards and bar chart data if needed
      let filteredCards = allCards;
      let chartData;
      if (currentColorFilter) {
        // Show only the selected color and 'Many' in the bar chart
        filteredCards = allCards.filter(card => {
          const key = getColorKey(card);
          if (key === currentColorFilter) return true;
          if (key === 'Many' && Array.isArray(card.colors) && card.colors.map(c => colorNorm[String(c).toLowerCase()] || c).includes(currentColorFilter)) return true;
          return false;
        });
        // Bar chart: only selected color and 'Many'
        const colorCounts = getColorCounts(filteredCards);
        chartData = colorOrder
          .filter(color => color === currentColorFilter || color === 'Many')
          .map(color => ({
            color,
            count: colorCounts[color] || 0,
            fill: colorMap[color]
          }));
      } else {
        // No filter: show all
        const colorCounts = getColorCounts(allCards);
        chartData = colorOrder.map(color => ({
          color,
          count: colorCounts[color] || 0,
          fill: colorMap[color]
        }));
      }
      renderBarChart(chartData);
      renderDonutChart(filteredCards);
    }
    // Format numbers as XX.Xk for thousands
    function formatCount(n) {
      if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
      return n;
    }
    function renderBarChart(data) {
      // Responsive width: 58% of .viz-row or 100% on mobile
      // Use container width for responsive sizing
      const container = document.getElementById('d3-bar-chart');
      let width = container ? container.offsetWidth : 600;
      let height = 350;
      let isMobile = window.innerWidth < 900;
      if (isMobile) {
        width = Math.min(window.innerWidth * 0.98, 420);
        height = 320;
      }

      // Tooltip div
      const tooltip = d3.select('body').append('div')
        .attr('class', 'd3-tooltip')
        .style('position', 'absolute')
        .style('background', '#2D1B4A')
        .style('color', '#F3F0FF')
        .style('padding', '8px 14px')
        .style('border-radius', '8px')
        .style('box-shadow', '0 0 8px #9D4EDD')
        .style('pointer-events', 'none')
        .style('font-size', '1rem')
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
          .attr('stroke', '#fff')
          .attr('stroke-width', d => d.color === 'White' ? 3 : 1.5)
          .attr('opacity', 0.95)
          .style('cursor', 'pointer')
          .on('mouseover', function(event, d) {
            d3.select(this).attr('opacity', 1).attr('stroke', '#B983FF');
            tooltip.transition().duration(100).style('opacity', 1);
            tooltip.html(`<strong>${d.color}</strong><br>Count: ${formatCount(d.count)}`)
              .style('left', (event.pageX + 12) + 'px')
              .style('top', (event.pageY - 28) + 'px');
          })
          .on('mousemove', function(event) {
            tooltip.style('left', (event.pageX + 12) + 'px')
                   .style('top', (event.pageY - 28) + 'px');
          })
          .on('mouseout', function() {
            d3.select(this).attr('opacity', 0.95).attr('stroke', '#fff');
            tooltip.transition().duration(200).style('opacity', 0);
          })
          .on('click', function(event, d) {
            if (currentColorFilter === d.color) {
              currentColorFilter = null;
              tooltip.transition().duration(200).style('opacity', 0);
            } else {
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
        // Add filter label if active
        if (currentColorFilter) {
          svg.append('text')
            .attr('x', width - 20)
            .attr('y', margin.top - 10)
            .attr('text-anchor', 'end')
            .attr('font-size', '1rem')
            .attr('fill', '#F3F0FF')
            .text(`Filtered: ${currentColorFilter}`);
        }
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
          .attr('stroke', '#fff')
          .attr('stroke-width', d => d.color === 'White' ? 3 : 1.5)
          .attr('opacity', 0.95)
          .style('cursor', 'pointer')
          .on('mouseover', function(event, d) {
            d3.select(this).attr('opacity', 1).attr('stroke', '#B983FF');
            tooltip.transition().duration(100).style('opacity', 1);
            tooltip.html(`<strong>${d.color}</strong><br>Count: ${formatCount(d.count)}`)
              .style('left', (event.pageX + 12) + 'px')
              .style('top', (event.pageY - 28) + 'px');
          })
          .on('mousemove', function(event) {
            tooltip.style('left', (event.pageX + 12) + 'px')
                   .style('top', (event.pageY - 28) + 'px');
          })
          .on('mouseout', function() {
            d3.select(this).attr('opacity', 0.95).attr('stroke', '#fff');
            tooltip.transition().duration(200).style('opacity', 0);
          })
          .on('click', function(event, d) {
            if (currentColorFilter === d.color) {
              currentColorFilter = null;
              tooltip.transition().duration(200).style('opacity', 0);
            } else {
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
        // Add filter label if active
        if (currentColorFilter) {
          svg.append('text')
            .attr('x', width - 20)
            .attr('y', margin.top - 10)
            .attr('text-anchor', 'end')
            .attr('font-size', '1rem')
            .attr('fill', '#F3F0FF')
            .text(`Filtered: ${currentColorFilter}`);
        }
      }
    }
    function renderDonutChart(cards) {
      // Group by type
      const typeCounts = {};
      let total = 0;
      for (const card of cards) {
        let t = (card.type || '').split('—')[0].trim(); // handle "Creature — Human"
        if (!t) t = 'Other';
        typeCounts[t] = (typeCounts[t] || 0) + 1;
        total++;
      }
      // Sort by count desc, show top 8, rest as "Other"
      let entries = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
      if (entries.length > 8) {
        const top = entries.slice(0, 7);
        const otherCount = entries.slice(7).reduce((sum, e) => sum + e[1], 0);
        entries = [...top, ['Other', otherCount]];
      }
      const data = entries.map(([type, count]) => ({type, count}));
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
// Redraw charts on window resize for true responsiveness
window.addEventListener('resize', () => {
  // Only rerender if on visualizations page
  if (document.getElementById('d3-bar-chart') && document.getElementById('d3-donut-chart')) {
    d3.select('#d3-bar-chart').selectAll('*').remove();
    d3.select('#d3-donut-chart').selectAll('*').remove();
    // Re-run setupViz if available
    if (typeof setupViz === 'function') setupViz();
    // If not, reload page as fallback
  }
});
      const pie = d3.pie().value(d => d.count);
      const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
      // Remove any existing donut tooltips before creating a new one
      d3.selectAll('.d3-tooltip.donut').remove();
      const tooltip = d3.select('body').append('div')
        .attr('class', 'd3-tooltip donut')
        .style('position', 'absolute')
        .style('background', '#2D1B4A')
        .style('color', '#F3F0FF')
        .style('padding', '8px 14px')
        .style('border-radius', '8px')
        .style('box-shadow', '0 0 8px #9D4EDD')
        .style('pointer-events', 'none')
        .style('font-size', '1rem')
        .style('opacity', 0);
      svg.selectAll('path')
        .data(pie(data))
        .enter()
        .append('path')
        .attr('d', arc)
        .attr('fill', (d, i) => colors[i % colors.length])
        .attr('stroke', '#18122B')
        .attr('stroke-width', 2)
        .on('mouseover', function(event, d) {
          d3.select(this).attr('opacity', 1).attr('stroke', '#B983FF');
          tooltip.transition().duration(100).style('opacity', 1);
          tooltip.html(`<strong>${d.data.type}</strong><br>Count: ${formatCount(d.data.count)}`)
            .style('left', (event.pageX + 12) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mousemove', function(event) {
          tooltip.style('left', (event.pageX + 12) + 'px')
                 .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseout', function() {
          d3.select(this).attr('opacity', 0.95).attr('stroke', '#18122B');
          tooltip.transition().duration(200).style('opacity', 0);
          setTimeout(() => { tooltip.remove(); }, 220);
        });
      // Center label: total
      svg.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 10)
        .attr('font-size', '2.2rem')
        .attr('font-weight', 'bold')
        .attr('fill', '#B983FF')
        .text(formatCount(total));
      svg.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 38)
        .attr('font-size', '1.1rem')
        .attr('fill', '#F3F0FF')
        .text('Total Cards');
      // Legend
      const legend = d3.select('#d3-donut-chart').append('div')
        .attr('class', 'd3-legend')
        .style('display', 'flex')
        .style('flex-wrap', 'wrap')
        .style('justify-content', 'center')
        .style('gap', '12px')
        .style('margin-top', '10px');
      data.forEach((d, i) => {
        legend.append('span')
          .style('display', 'inline-flex')
          .style('align-items', 'center')
          .style('gap', '6px')
          .html(`<span style=\"display:inline-block;width:18px;height:18px;background:${colors[i % colors.length]};border-radius:50%;margin-right:4px;\"></span>${d.type}`);
      });
    }
    // Initial render
    updateCharts();
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
});
