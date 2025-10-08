// Table management functions for MTG card visualizations
import { colorNorm } from './charts.js';

// Global variable to store current cards data for modal access
let currentTableCards = [];

// Render filtered cards table
export function renderFilteredCardsTable(cards) {
  // Store cards data globally for modal access
  currentTableCards = cards || [];
  const tbody = document.querySelector('#filtered-cards-table tbody');
  if (!tbody) return;

  if (!cards || cards.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No cards match the current filters</td></tr>';
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

    // Format set count
    const setCountDisplay = card.set_count || 1;

    // Lazy load image with placeholder
    const imageDisplay = card.image_uris && card.image_uris.normal
      ? `<div class="card-image-container" style="width:50px;height:60px;display:flex;align-items:center;justify-content:center;background:rgba(185,131,255,0.1);border-radius:6px;border:2px solid rgba(185,131,255,0.2);">
           <div class="image-placeholder" style="width:20px;height:20px;border:2px solid #B983FF;border-top:2px solid transparent;border-radius:50%;animation:spin 1s linear infinite;"></div>
         </div>
         <img src="${card.image_uris.normal}" alt="${card.name}" style="display:none;max-width:50px;max-height:60px;border-radius:6px;border:2px solid rgba(185,131,255,0.2);box-shadow:0 2px 4px rgba(0,0,0,0.1);cursor:pointer;transition:all 0.2s ease;" onload="this.style.display='block';this.previousElementSibling.style.display='none';" onerror="this.style.display='none';this.previousElementSibling.innerHTML='❌';" onmouseover="this.style.transform='scale(1.05)';this.style.boxShadow='0 4px 8px rgba(185,131,255,0.3)';" onmouseout="this.style.transform='scale(1)';this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)';" data-card-index="${i}" onclick="showCardModalFromTable(this)">`
      : '<div class="text-muted" style="width:50px;text-align:center;">—</div>';

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
      <td style="padding:12px 16px;color:#F3F0FF;font-family:system-ui,-apple-system,sans-serif;text-align:center;">${setCountDisplay}</td>
      <td style="padding:12px 16px;text-align:center;">${imageDisplay}</td>
    `;
    tbody.appendChild(row);
  }
}

// Render pagination controls
export function renderPagination(totalFilteredCards, currentPage, pageSize, onPageChange) {
  const pageCount = Math.max(1, Math.ceil(totalFilteredCards / pageSize));
  const pagination = document.getElementById('filtered-pagination');
  const paginationContainer = document.querySelector('nav.mt-2');
  if (!pagination) return;

  pagination.innerHTML = '';

  if (totalFilteredCards <= pageSize) {
    // Hide pagination if all cards fit on one page
    if (paginationContainer) paginationContainer.classList.add('d-none');
    return;
  }

  // Show pagination container
  if (paginationContainer) paginationContainer.classList.remove('d-none');

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
export function showCardModal(name, setsJson, typeLine) {
  const sets = JSON.parse(setsJson);
  
  // Create modal HTML with all printings
  let printingsHtml = '';
  sets.forEach((printing, index) => {
    const priceDisplay = printing.price !== undefined ? '$' + printing.price.toLocaleString() : 'N/A';
    const imageUrl = printing.image_uris?.normal || printing.image_uris?.large || '';
    const largeImageUrl = printing.image_uris?.large || printing.image_uris?.normal || '';
    
    printingsHtml += `
      <div class="card-printing mb-3 p-3 border rounded" style="background: rgba(255,255,255,0.05);">
        <div class="row">
          <div class="col-md-4">
            ${imageUrl ? `<img src="${imageUrl}" alt="${name}" class="img-fluid rounded card-printing-image" style="max-height: 200px; cursor: pointer;" data-large-image="${largeImageUrl}" data-printing-index="${index}">` : '<div class="text-muted">No image available</div>'}
          </div>
          <div class="col-md-8">
            <h6 class="text-primary">${name}</h6>
            <p class="mb-1"><strong>Set:</strong> ${printing.set || 'Unknown'}</p>
            <p class="mb-1"><strong>Rarity:</strong> ${printing.rarity || 'Unknown'}</p>
            <p class="mb-1"><strong>Price:</strong> ${priceDisplay}</p>
            <p class="mb-1"><strong>Artist:</strong> ${printing.artist || 'Unknown'}</p>
          </div>
        </div>
      </div>
    `;
  });

  const modalHtml = `
    <div class="modal fade" id="cardModal" tabindex="-1" style="z-index: 1055;">
      <div class="modal-dialog modal-xl">
        <div class="modal-content bg-dark text-light">
          <div class="modal-header">
            <h5 class="modal-title">${name} - All Printings (${sets.length} sets)</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <strong>Type:</strong> ${typeLine}
            </div>
            <div class="printings-container" style="max-height: 60vh; overflow-y: auto;">
              ${printingsHtml}
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

  // Get modal element and create Bootstrap modal instance
  const modalElement = document.getElementById('cardModal');
  const modal = new bootstrap.Modal(modalElement);

  // Add click handlers when modal is shown
  modalElement.addEventListener('shown.bs.modal', function() {
    document.querySelectorAll('.card-printing-image').forEach(img => {
      img.addEventListener('click', function() {
        const largeImageUrl = this.getAttribute('data-large-image');
        const printingIndex = parseInt(this.getAttribute('data-printing-index'));
        showLargeImageModal(name, largeImageUrl, sets[printingIndex]);
      });
    });
  });

  // Show modal
  modal.show();
}

// New function to show modal from table using stored data
export function showCardModalFromTable(imgElement) {
  const cardIndex = parseInt(imgElement.getAttribute('data-card-index'));
  if (isNaN(cardIndex) || !currentTableCards[cardIndex]) {
    console.error('Invalid card index or card data not found');
    return;
  }
  
  const card = currentTableCards[cardIndex];
  showCardModal(card.name, JSON.stringify(card.sets), card.type_line);
}

// New function to show large image modal
export function showLargeImageModal(cardName, imageUrl, printing) {
  const priceDisplay = printing.price !== undefined ? '$' + printing.price.toLocaleString() : 'N/A';
  
  const largeModalHtml = `
    <div class="modal fade" id="largeImageModal" tabindex="-1" style="z-index: 1065;">
      <div class="modal-dialog modal-lg">
        <div class="modal-content bg-dark text-light">
          <div class="modal-header">
            <h5 class="modal-title">${cardName} - ${printing.set || 'Unknown'}</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body text-center">
            ${imageUrl ? `<img src="${imageUrl}" alt="${cardName}" class="img-fluid" style="max-height: 70vh;">` : '<div class="text-muted">No image available</div>'}
            <div class="mt-3">
              <p class="mb-1"><strong>Set:</strong> ${printing.set || 'Unknown'}</p>
              <p class="mb-1"><strong>Rarity:</strong> ${printing.rarity || 'Unknown'}</p>
              <p class="mb-1"><strong>Price:</strong> ${priceDisplay}</p>
              <p class="mb-1"><strong>Artist:</strong> ${printing.artist || 'Unknown'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Remove existing large modal if present
  const existingLargeModal = document.getElementById('largeImageModal');
  if (existingLargeModal) {
    existingLargeModal.remove();
  }

  // Add large modal to body
  document.body.insertAdjacentHTML('beforeend', largeModalHtml);

  // Show large modal
  const largeModal = new bootstrap.Modal(document.getElementById('largeImageModal'));
  largeModal.show();
}

// Make functions global
window.showCardModal = showCardModal;
window.showCardModalFromTable = showCardModalFromTable;
window.showLargeImageModal = showLargeImageModal;