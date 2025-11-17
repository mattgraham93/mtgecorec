// Narrative visualizations for MTG Economy page

document.addEventListener('DOMContentLoaded', function() {
  // Wait a bit for layout to settle before rendering charts
  setTimeout(() => {
    renderCharts();
  }, 100);

  // Handle window resize
  window.addEventListener('resize', debounce(() => {
    renderCharts();
  }, 250));
});

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function renderCharts() {
  // Fetch data from API - start with summary, then try smaller card sample
  fetch('/api/cards/summary')
    .then(res => res.json())
    .then(summary => {
      // Render visualizations that can work with summary data
      renderRarityTypeChart(summary);
      renderSetTimelineChart(summary);

      // Try to get a smaller sample of cards for price analysis
      return fetch('/api/cards?page_size=100&sort_by=name&sort_order=asc')
        .then(res => {
          if (!res.ok) throw new Error('Cards API failed');
          return res.json();
        })
        .then(cardsData => {
          const cards = cardsData.cards || [];
          renderPriceDistribution(cards);
          renderColorPriceChart(cards);
        })
        .catch(err => {
          console.warn('Could not fetch card details for price analysis:', err);
          // Show messages for price-based charts
          renderPriceDistribution([]);
          renderColorPriceChart([]);
        });
    })
    .catch(err => {
      console.error('Failed to load summary data:', err);
      // Show error messages for all charts
      document.querySelectorAll('.chart-container').forEach(container => {
        container.innerHTML = '<div class="alert alert-danger">Failed to load data</div>';
      });
    });
}

function renderPriceDistribution(cards) {
  const container = d3.select('#price-distribution-chart');
  container.html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div></div>');

  if (!cards || cards.length === 0) {
    container.html('<div class="alert alert-info">Price data requires individual card details. Sample data fetch failed due to rate limiting.</div>');
    return;
  }

  // Filter out cards without prices and prepare data
  const pricedCards = cards.filter(card => card.price && card.price > 0);
  const prices = pricedCards.map(card => card.price);

  if (prices.length === 0) {
    container.html('<div class="alert alert-warning">No price data available in current sample</div>');
    return;
  }

  // Create histogram bins
  const bins = d3.bin().thresholds(20)(prices);
  const maxCount = d3.max(bins, d => d.length);

  // Get container dimensions for responsive sizing
  const containerRect = container.node().getBoundingClientRect();
  const containerWidth = containerRect.width; // No padding to subtract
  const containerHeight = Math.max(400, containerRect.height); // Minimum 400px height

  const margin = {top: 10, right: 20, bottom: 40, left: 40};
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  // Clear loading spinner and create chart
  container.html('');

  const svg = container.append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear()
    .domain([0, d3.max(prices)])
    .range([0, width]);

  const y = d3.scaleLinear()
    .domain([0, maxCount])
    .range([height, 0]);

  // Add bars
  svg.selectAll('rect')
    .data(bins)
    .enter()
    .append('rect')
    .attr('x', d => x(d.x0))
    .attr('y', d => y(d.length))
    .attr('width', d => Math.max(0, x(d.x1) - x(d.x0) - 1))
    .attr('height', d => height - y(d.length))
    .attr('fill', '#B983FF')
    .attr('opacity', 0.8);

  // Add axes
  svg.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x).ticks(10))
    .selectAll('text')
    .attr('fill', '#F3F0FF');

  svg.append('g')
    .call(d3.axisLeft(y))
    .selectAll('text')
    .attr('fill', '#F3F0FF');

  // Labels
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', height + 30)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Price ($)');

  svg.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', -30)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Number of Cards');
}

function renderColorPriceChart(cards) {
  const container = d3.select('#color-price-chart');
  container.html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div></div>');

  if (!cards || cards.length === 0) {
    container.html('<div class="alert alert-info">Price analysis requires individual card details. Sample data fetch failed due to rate limiting.</div>');
    return;
  }

  // Group by color and calculate average price
  const colorData = {};
  cards.forEach(card => {
    if (!card.price || card.price <= 0) return;
    let color = 'Colorless';
    if (card.colors && card.colors.length > 0) {
      if (card.colors.length === 1) {
        const colorMap = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'};
        color = colorMap[card.colors[0]] || 'Other';
      } else {
        color = 'Multicolor';
      }
    }
    if (!colorData[color]) colorData[color] = {total: 0, count: 0};
    colorData[color].total += card.price;
    colorData[color].count += 1;
  });

  const data = Object.entries(colorData).map(([color, {total, count}]) => ({
    color,
    avgPrice: total / count
  })).sort((a, b) => b.avgPrice - a.avgPrice);

  if (data.length === 0) {
    container.html('<div class="alert alert-warning">No price data available in current sample</div>');
    return;
  }

  // Get container dimensions for responsive sizing
  const containerRect = container.node().getBoundingClientRect();
  const containerWidth = containerRect.width; // No padding to subtract
  const containerHeight = Math.max(400, containerRect.height); // Minimum 400px height

  const margin = {top: 10, right: 20, bottom: 50, left: 40};
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  // Clear loading spinner and create chart
  container.html('');

  const svg = container.append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  const x = d3.scaleBand()
    .domain(data.map(d => d.color))
    .range([0, width])
    .padding(0.1);

  const y = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.avgPrice)])
    .range([height, 0]);

  // Add bars
  svg.selectAll('rect')
    .data(data)
    .enter()
    .append('rect')
    .attr('x', d => x(d.color))
    .attr('y', d => y(d.avgPrice))
    .attr('width', x.bandwidth())
    .attr('height', d => height - y(d.avgPrice))
    .attr('fill', '#B983FF')
    .attr('opacity', 0.8);

  // Add axes
  svg.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .attr('fill', '#F3F0FF')
    .attr('transform', 'rotate(-45)')
    .attr('text-anchor', 'end');

  svg.append('g')
    .call(d3.axisLeft(y))
    .selectAll('text')
    .attr('fill', '#F3F0FF');

  // Labels
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', height + 40)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Color');

  svg.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', -30)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Average Price ($)');
}

function renderRarityTypeChart(summary) {
  const container = d3.select('#rarity-type-chart');
  container.html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div></div>');

  if (!summary || !summary.type_counts || !summary.combined_aggregations) {
    container.html('<div class="alert alert-warning">No data available</div>');
    return;
  }

  // Get the types that appear in the donut chart (matching visualizations.js logic)
  const typeCounts = summary.type_counts;
  let entries = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]);
  const priorityTypes = ['Legendary Creature', 'Planeswalker'];
  let topEntries = [];
  let remainingEntries = [...entries];

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

  // These are the types that appear in the donut chart
  const donutTypes = topEntries.map(([type]) => type);

  // Filter combined aggregations to only include these types
  const data = summary.combined_aggregations
    .filter(item => donutTypes.includes(item.type))
    .map(item => ({
      color: item.color,
      type: item.type,
      count: item.count
    }));

  if (data.length === 0) {
    container.html('<div class="alert alert-warning">No combined data available</div>');
    return;
  }

  // Get unique colors, ordered to match visualizations.js
  const colorOrder = ['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless', 'Many', 'Other'];
  const colors = [...new Set(data.map(d => d.color))].sort((a, b) => {
    const aIndex = colorOrder.indexOf(a);
    const bIndex = colorOrder.indexOf(b);
    return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
  });

  // Types in the same order as they appear in the donut chart
  const types = donutTypes;

  // Create matrix
  const matrix = {};
  colors.forEach(c => {
    matrix[c] = {};
    types.forEach(t => matrix[c][t] = 0);
  });

  data.forEach(item => {
    if (matrix[item.color] && matrix[item.color][item.type] !== undefined) {
      matrix[item.color][item.type] = item.count;
    }
  });

  // Convert to array format for D3
  const plotData = [];
  colors.forEach(c => {
    types.forEach(t => {
      plotData.push({color: c, type: t, count: matrix[c][t]});
    });
  });

  // Get container dimensions for responsive sizing
  const containerRect = container.node().getBoundingClientRect();
  const containerWidth = containerRect.width; // No padding to subtract
  const containerHeight = Math.max(500, containerRect.height); // Minimum 500px height for heatmap

  const margin = {top: 20, right: 20, bottom: 60, left: 80};
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  // Clear loading spinner and create chart
  container.html('');

  const svg = container.append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  const x = d3.scaleBand()
    .domain(types)
    .range([0, width])
    .padding(0.05);

  const y = d3.scaleBand()
    .domain(colors)
    .range([0, height])
    .padding(0.05);

  const color = d3.scaleSequential(d3.interpolateBlues)
    .domain([0, d3.max(plotData, d => d.count)]);

  // Add cells
  svg.selectAll('rect')
    .data(plotData)
    .enter()
    .append('rect')
    .attr('x', d => x(d.type))
    .attr('y', d => y(d.color))
    .attr('width', x.bandwidth())
    .attr('height', y.bandwidth())
    .attr('fill', d => d.count > 0 ? color(d.count) : '#2a2a2a')
    .attr('stroke', '#fff')
    .attr('stroke-width', 1)
    .attr('opacity', 0.9);

  // Add text labels for counts (only for cells with data)
  svg.selectAll('text')
    .data(plotData.filter(d => d.count > 0))
    .enter()
    .append('text')
    .attr('x', d => x(d.type) + x.bandwidth() / 2)
    .attr('y', d => y(d.color) + y.bandwidth() / 2)
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('fill', d => d.count > d3.max(plotData, d => d.count) / 2 ? '#fff' : '#000')
    .attr('font-size', '11px')
    .attr('font-weight', '500')
    .text(d => d.count);

  // Add axes
  svg.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .attr('fill', '#F3F0FF')
    .attr('transform', 'rotate(-45)')
    .attr('text-anchor', 'end')
    .attr('font-size', '11px');

  svg.append('g')
    .call(d3.axisLeft(y))
    .selectAll('text')
    .attr('fill', '#F3F0FF')
    .attr('font-size', '11px');

  // Add title
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', -10)
    .attr('text-anchor', 'middle')
    .attr('fill', '#B983FF')
    .attr('font-weight', 'bold')
    .attr('font-size', '16px')
    .text('Color vs Type Distribution (Top Types)');

  // Add axis labels
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', height + 50)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .attr('font-size', '12px')
    .text('Card Type (Top 9 from Donut Chart)');

  svg.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', -70)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .attr('font-size', '12px')
    .text('Card Color');
}

function renderSetTimelineChart(summary) {
  const container = d3.select('#set-timeline-chart');
  container.html('<div class="text-center"><div class="spinner-border text-primary" role="status"></div></div>');

  if (!summary || !summary.sets || summary.sets.length === 0) {
    container.html('<div class="alert alert-warning">No set data available</div>');
    return;
  }

  // The API already filters for sets with >30 cards, so just sort by unique card count ascending
  const setsData = summary.sets.sort((a, b) => a.unique_cards_count - b.unique_cards_count);

  if (setsData.length === 0) {
    container.html('<div class="alert alert-warning">No sets found in the database</div>');
    return;
  }

  // Create statistics cards
  // Clear loading spinner and create stats container
  container.html('');

  const statsContainer = container.append('div')
    .attr('class', 'row mb-4');

  // Top set (most cards)
  const topSet = setsData[setsData.length - 1];
  statsContainer.append('div')
    .attr('class', 'col-md-6')
    .html(`
      <div class="card bg-dark border-secondary">
        <div class="card-body text-center">
          <h5 class="card-title text-primary">Largest Set</h5>
          <h3 class="text-light">${topSet.set}</h3>
          <p class="text-muted">${topSet.unique_cards_count.toLocaleString()} unique cards</p>
        </div>
      </div>
    `);

  // Smallest set (least cards, but >30)
  const smallestSet = setsData[0];
  statsContainer.append('div')
    .attr('class', 'col-md-6')
    .html(`
      <div class="card bg-dark border-secondary">
        <div class="card-body text-center">
          <h5 class="card-title text-primary">Smallest Set</h5>
          <h3 class="text-light">${smallestSet.set}</h3>
          <p class="text-muted">${smallestSet.unique_cards_count.toLocaleString()} unique cards</p>
        </div>
      </div>
    `);

  // Create the chart
  // Get container dimensions for responsive sizing (accounting for stats cards above)
  const containerRect = container.node().getBoundingClientRect();
  const containerWidth = containerRect.width; // No padding to subtract
  const availableHeight = Math.max(500, containerRect.height - 200); // Subtract stats cards height

  const margin = {top: 10, right: 20, bottom: 80, left: 60};
  const width = containerWidth - margin.left - margin.right;
  const height = availableHeight - margin.top - margin.bottom;

  const svg = container.append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  const x = d3.scaleBand()
    .domain(setsData.map(d => d.set))
    .range([0, width])
    .padding(0.1);

  const y = d3.scaleLinear()
    .domain([0, d3.max(setsData, d => d.unique_cards_count)])
    .range([height, 0]);

  // Add bars
  svg.selectAll('rect')
    .data(setsData)
    .enter()
    .append('rect')
    .attr('x', d => x(d.set))
    .attr('y', d => y(d.unique_cards_count))
    .attr('width', x.bandwidth())
    .attr('height', d => height - y(d.unique_cards_count))
    .attr('fill', '#B983FF')
    .attr('opacity', 0.8);

  // Add value labels on bars (only for smaller sets to avoid overlap)
  svg.selectAll('.label')
    .data(setsData.filter(d => d.unique_cards_count < 200)) // Only label smaller sets
    .enter()
    .append('text')
    .attr('x', d => x(d.set) + x.bandwidth() / 2)
    .attr('y', d => y(d.unique_cards_count) - 5)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .attr('font-size', '10px')
    .text(d => d.unique_cards_count);

  // Add axes
  svg.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .attr('fill', '#F3F0FF')
    .attr('transform', 'rotate(-45)')
    .attr('text-anchor', 'end')
    .attr('font-size', '10px');

  svg.append('g')
    .call(d3.axisLeft(y))
    .selectAll('text')
    .attr('fill', '#F3F0FF');

  // Labels
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', height + 70)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Magic: The Gathering Sets');

  svg.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', -50)
    .attr('text-anchor', 'middle')
    .attr('fill', '#F3F0FF')
    .text('Unique Cards per Set');

  // Add title
  svg.append('text')
    .attr('x', width / 2)
    .attr('y', -5)
    .attr('text-anchor', 'middle')
    .attr('fill', '#B983FF')
    .attr('font-weight', 'bold')
    .attr('font-size', '16px')
    .text('Power of Sets: Card Count Distribution');
}