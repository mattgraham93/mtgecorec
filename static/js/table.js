// Table management functions for MTG card visualizations
import { colorNorm } from './charts.js';

// Render filtered cards table
export function renderFilteredCardsTable(cards) {
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
export function renderPagination(totalFilteredCards, currentPage, pageSize, onPageChange) {
  const pageCount = Math.max(1, Math.ceil(totalFilteredCards / pageSize));
  const pagination = document.getElementById('filtered-pagination');
  if (!pagination) return;

  pagination.innerHTML = '';

  if (totalFilteredCards <= pageSize) {
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
    if (currentPage > 1) onPageChange(currentPage - 1);
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
        onPageChange(val);
      } else {
        input.value = currentPage;
      }
    }
  };
  input.onblur = () => {
    let val = parseInt(input.value);
    if (!isNaN(val) && val >= 1 && val <= pageCount && val !== currentPage) {
      onPageChange(val);
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
    if (currentPage < pageCount) onPageChange(currentPage + 1);
  };
  liNext.appendChild(aNext);
  pagination.appendChild(liNext);
}

// Setup table sorting
export function setupTableSorting(onSortChange) {
  const table = document.getElementById('filtered-cards-table');
  if (!table) return;

  const headers = table.querySelectorAll('th.sortable');
  headers.forEach(header => {
    header.addEventListener('click', function() {
      const sortBy = this.dataset.sort;
      onSortChange(sortBy);
    });
  });
}

// Update sort indicators
export function updateSortIndicators(currentSortBy, currentSortOrder) {
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

// Card modal function
export function showCardModal(name, imageUrl, typeLine, set, rarity, price) {
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
}

// Make showCardModal global
window.showCardModal = showCardModal;