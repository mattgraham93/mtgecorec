// Chart rendering functions for MTG card visualizations
import { allCards, setCurrentTypeFilter } from './state.js';

// Format numbers as XX.Xk for thousands
export function formatCount(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n;
}

// Color mappings and normalization
export const colorNorm = {
  'w': 'White', 'white': 'White',
  'u': 'Blue',  'blue': 'Blue',
  'b': 'Black', 'black': 'Black',
  'r': 'Red',   'red': 'Red',
  'g': 'Green', 'green': 'Green'
};

export const colorOrder = ['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless', 'Many', 'Other'];

export const colorMap = {
  'White': 'rgb(249, 250, 244)', // white
  'Blue': 'rgb(41, 104, 171)',   // blue
  'Black': 'rgb(24, 11, 0)',     // dark brown
  'Red': 'rgb(211, 32, 42)',     // red
  'Green': 'rgb(0, 115, 62)',    // green
  'Colorless': 'rgb(166, 159, 157)', // gray
  'Many': 'rgb(235, 159, 130)',  // peach
  'Other': 'rgb(196, 211, 202)'  // light green (fallback for other)
};

export function getColorKey(card) {
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

// Use backend summary for color counts if available
export function getColorCounts(cards) {
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

// Render bar chart
export function renderBarChart(data, onColorClick) {
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
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('opacity', 1)
          .attr('stroke', '#B983FF')
          .attr('stroke-width', 3);
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
          .attr('stroke-width', 2);
        tooltip.transition().duration(300).style('opacity', 0);
      })
      .on('click', function(event, d) {
        onColorClick(d.color);
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
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('opacity', 1)
          .attr('stroke', '#B983FF')
          .attr('stroke-width', 3);
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
          .attr('stroke-width', 2);
        tooltip.transition().duration(300).style('opacity', 0);
      })
      .on('click', function(event, d) {
        onColorClick(d.color);
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

// Render donut chart
export function renderDonutChart(data, drillDownData, onTypeClick, onDrillDown, onBackToOverview) {
  // Clear any existing content
  d3.select('#d3-donut-chart').html('');

  // Always use backend summary for type counts if available
  let typeCounts = {};
  let total = 0;
  if (window.cardSummary && window.cardSummary.type_counts) {
    typeCounts = window.cardSummary.type_counts;
    total = window.cardSummary.total || 0;
  }

  let chartData;
  let remainingEntries = [];

  if (drillDownData) {
    // Use drill-down data
    chartData = drillDownData;
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

    chartData = topEntries.map(([type, count]) => ({type, count}));
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
  
  // Create persistent tooltip (like bar chart)
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
    .data(pie(chartData))
    .enter()
    .append('path')
    .attr('d', arc)
    .attr('fill', (d, i) => colors[i % colors.length])
    .attr('stroke', '#ffffff')
    .attr('stroke-width', 3)
    .attr('opacity', 0.9)
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
        .attr('stroke-width', 4);
      
      // Enhanced tooltip with combined data if available
      let tooltipContent = `<strong>${d.data.type}</strong><br>Count: ${formatCount(d.data.count)}`;
      
      if (!drillDownData && window.cardSummary && window.cardSummary.combined_aggregations) {
        // Show top color combinations for this type
        const typeAggregations = window.cardSummary.combined_aggregations
          .filter(item => item.type === d.data.type)
          .sort((a, b) => b.count - a.count)
          .slice(0, 3);
        
        if (typeAggregations.length > 0) {
          tooltipContent += '<br><br><small>Top colors:</small>';
          typeAggregations.forEach(agg => {
            tooltipContent += `<br>${agg.color}: ${formatCount(agg.count)}`;
          });
        }
      }
      
      tooltip.transition().duration(200).style('opacity', 1);
      tooltip.html(tooltipContent)
        .style('left', (event.pageX + 15) + 'px')
        .style('top', (event.pageY - 35) + 'px');
    })
    .on('focus', function(event, d) {
      d3.select(this)
        .transition()
        .duration(200)
        .attr('opacity', 1)
        .attr('stroke', '#B983FF')
        .attr('stroke-width', 4);
    })
    .on('blur', function() {
      d3.select(this)
        .transition()
        .duration(200)
        .attr('opacity', 0.9)
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 3);
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
        .attr('stroke-width', 3);
      tooltip.transition().duration(300).style('opacity', 0);
    })
    .on('click', function(event, d) {
      if (d.data.type === 'Other' && !drillDownData) {
        // Drill down into Other types using combined aggregations if available
        if (window.cardSummary && window.cardSummary.combined_aggregations) {
          const otherAggregations = window.cardSummary.combined_aggregations
            .filter(item => !['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land'].includes(item.type))
            .reduce((acc, item) => {
              const existing = acc.find(a => a.type === item.type);
              if (existing) {
                existing.count += item.count;
              } else {
                acc.push({type: item.type, count: item.count});
              }
              return acc;
            }, [])
            .sort((a, b) => b.count - a.count);
          
          onDrillDown(otherAggregations);
        } else {
          // Fallback to old method
          onDrillDown(remainingEntries);
        }
      } else {
        // Exit drill-down mode if active and apply filter
        if (drillDownData) {
          onBackToOverview();
        }
        onTypeClick(d.data.type, drillDownData);
      }
    })
    .on('keydown', function(event, d) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (d.data.type === 'Other' && !drillDownData) {
          if (window.cardSummary && window.cardSummary.combined_aggregations) {
            const otherAggregations = window.cardSummary.combined_aggregations
              .filter(item => !['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land'].includes(item.type))
              .reduce((acc, item) => {
                const existing = acc.find(a => a.type === item.type);
                if (existing) {
                  existing.count += item.count;
                } else {
                  acc.push({type: item.type, count: item.count});
                }
                return acc;
              }, [])
              .sort((a, b) => b.count - a.count);
            
            onDrillDown(otherAggregations);
          } else {
            onDrillDown(remainingEntries);
          }
        } else {
          // Exit drill-down mode if active and apply filter
          if (drillDownData) {
            onBackToOverview();
          }
          onTypeClick(d.data.type, drillDownData);
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
        onBackToOverview();
      })
      .html('← Back to Overview');
  }

  chartData.forEach((d, i) => {
    const legendItem = legendContainer.append('div')
      .attr('class', 'd3-legend-item')
      .style('color', '#F3F0FF')
      .style('cursor', 'pointer')
      .style('font-size', '0.9rem')
      .style('font-weight', '500')
      .style('padding', '6px 8px')
      .style('margin-bottom', '4px')
      .style('border-radius', '6px')
      .style('transition', 'all 0.2s ease')
      .style('font-family', 'system-ui, -apple-system, sans-serif');

    legendItem.on('mouseover', function() {
      d3.select(this).style('background', 'rgba(255, 255, 255, 0.05)');
    })
    .on('mouseout', function() {
      d3.select(this).style('background', 'transparent');
    })
    .on('click', function() {
      if (d.type === 'Other' && !drillDownData) {
        if (window.cardSummary && window.cardSummary.combined_aggregations) {
          const otherAggregations = window.cardSummary.combined_aggregations
            .filter(item => !['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land'].includes(item.type))
            .reduce((acc, item) => {
              const existing = acc.find(a => a.type === item.type);
              if (existing) {
                existing.count += item.count;
              } else {
                acc.push({type: item.type, count: item.count});
              }
              return acc;
            }, [])
            .sort((a, b) => b.count - a.count);
          
          onDrillDown(otherAggregations);
        } else {
          onDrillDown(remainingEntries);
        }
      } else {
        onTypeClick(d.type, drillDownData);
      }
    })
    .html(`<span style="display:inline-block;width:12px;height:12px;background:${colors[i % colors.length]};border-radius:50%;margin-right:8px;border:2px solid rgba(255,255,255,0.3);"></span>${d.type}`);
  });
}