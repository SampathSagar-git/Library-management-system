/**
 * Smart Library Management & Booking System - Master Client Script
 */

document.addEventListener('DOMContentLoaded', () => {
  initAlertAutoDismiss();
  initDeskBookingEngine();
  initAdminAnalyticsCharts();
  initBookModal();
});

// Auto-dismiss alert banners after 6 seconds
function initAlertAutoDismiss() {
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 6000);
  });
}

// ================= Dedicated Desk Booking Interactive Engine =================
function initDeskBookingEngine() {
  const bookingForm = document.getElementById('deskBookingForm');
  const dateInput = document.getElementById('bookingDateInput');
  const timeInput = document.getElementById('bookingTimeInput');
  const durationInput = document.getElementById('bookingDurationInput');
  const deskSeats = document.querySelectorAll('.desk-seat');
  const selectedDeskInput = document.getElementById('selectedDeskNumber');
  const selectedZoneInput = document.getElementById('selectedZone');
  const deskSelectionNotice = document.getElementById('deskSelectionNotice');
  const submitBtn = document.getElementById('btnSubmitDeskBooking');

  if (!deskSeats.length || !dateInput) return;

  function fetchLiveDeskAvailability() {
    const bDate = dateInput.value;
    const bTime = timeInput ? timeInput.value : '09:00';
    const bDuration = durationInput ? durationInput.value : 2;

    if (!bDate) return;

    fetch(`/api/desks/availability?date=${encodeURIComponent(bDate)}&start_time=${encodeURIComponent(bTime)}&duration=${encodeURIComponent(bDuration)}`)
      .then(res => res.json())
      .then(data => {
        const desksMap = data.desks || {};

        deskSeats.forEach(seat => {
          const deskNum = seat.getAttribute('data-desk-number');
          const deskData = desksMap[deskNum];

          // Reset classes
          seat.classList.remove('available', 'occupied', 'selected');

          if (deskData) {
            if (deskData.status === 'occupied') {
              seat.classList.add('occupied');
              const statusBadge = seat.querySelector('.desk-status-text');
              if (statusBadge) statusBadge.innerText = 'Occupied';
              seat.title = `Booked during: ${deskData.occupied_times.join(', ')}`;
            } else {
              seat.classList.add('available');
              const statusBadge = seat.querySelector('.desk-status-text');
              if (statusBadge) statusBadge.innerText = 'Available';
              seat.title = 'Available for reservation';
            }
          }
        });

        // Re-apply selection if currently selected desk is still available
        if (selectedDeskInput && selectedDeskInput.value) {
          const currentSelected = document.querySelector(`.desk-seat[data-desk-number="${selectedDeskInput.value}"]`);
          if (currentSelected && currentSelected.classList.contains('available')) {
            currentSelected.classList.remove('available');
            currentSelected.classList.add('selected');
          } else {
            resetDeskSelection();
          }
        }
      })
      .catch(err => console.error('Desk availability check failed:', err));
  }

  function resetDeskSelection() {
    if (selectedDeskInput) selectedDeskInput.value = '';
    if (selectedZoneInput) selectedZoneInput.value = '';
    if (submitBtn) submitBtn.disabled = true;
    if (deskSelectionNotice) {
      deskSelectionNotice.innerHTML = `
        <div class="alert alert-light border text-muted py-2 mb-0">
          <i class="fa-solid fa-hand-pointer me-1 text-primary"></i> Click any green desk on the floor map to select it.
        </div>
      `;
    }
  }

  // Handle seat clicks
  deskSeats.forEach(seat => {
    seat.addEventListener('click', () => {
      if (seat.classList.contains('occupied')) {
        alert('This desk is currently occupied for your selected date and time. Please choose another desk or time window.');
        return;
      }

      // Unselect previous
      deskSeats.forEach(s => {
        if (s.classList.contains('selected')) {
          s.classList.remove('selected');
          s.classList.add('available');
        }
      });

      // Select clicked desk
      seat.classList.remove('available');
      seat.classList.add('selected');

      const deskNum = seat.getAttribute('data-desk-number');
      const deskZone = seat.getAttribute('data-desk-zone');

      if (selectedDeskInput) selectedDeskInput.value = deskNum;
      if (selectedZoneInput) selectedZoneInput.value = deskZone;
      if (submitBtn) submitBtn.disabled = false;

      if (deskSelectionNotice) {
        deskSelectionNotice.innerHTML = `
          <div class="alert alert-primary py-2 mb-0 d-flex align-items-center justify-content-between">
            <div>
              <strong>Selected: Desk ${deskNum}</strong>
              <div class="small text-muted">${deskZone}</div>
            </div>
            <span class="badge bg-primary px-3 py-2"><i class="fa-solid fa-check me-1"></i> Ready to Book</span>
          </div>
        `;
      }
    });
  });

  // Listen to filter changes
  if (dateInput) dateInput.addEventListener('change', fetchLiveDeskAvailability);
  if (timeInput) timeInput.addEventListener('change', fetchLiveDeskAvailability);
  if (durationInput) durationInput.addEventListener('change', fetchLiveDeskAvailability);

  // Initial fetch
  fetchLiveDeskAvailability();
}

// ================= Chart.js Admin Analytics =================
function initAdminAnalyticsCharts() {
  const trendsCtx = document.getElementById('chartLoanTrends');
  const catCtx = document.getElementById('chartCategories');
  const deskCtx = document.getElementById('chartDeskOccupancy');

  if (!trendsCtx && !catCtx && !deskCtx) return;

  fetch('/admin/api/analytics')
    .then(res => res.json())
    .then(data => {
      // 1. Borrowing & Returns Trends Line Chart
      if (trendsCtx && data.trends) {
        new Chart(trendsCtx, {
          type: 'line',
          data: {
            labels: data.trends.labels,
            datasets: [
              {
                label: 'Books Borrowed',
                data: data.trends.loans,
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.12)',
                fill: true,
                tension: 0.35,
                borderWidth: 2.5,
                pointRadius: 4,
                pointHoverRadius: 6
              },
              {
                label: 'Books Returned',
                data: data.trends.returns,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.12)',
                fill: true,
                tension: 0.35,
                borderWidth: 2.5,
                pointRadius: 4,
                pointHoverRadius: 6
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'top' },
              tooltip: { padding: 10, cornerRadius: 8 }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } },
              x: { grid: { display: false } }
            }
          }
        });
      }

      // 2. Category Distribution Doughnut Chart
      if (catCtx && data.categories) {
        new Chart(catCtx, {
          type: 'doughnut',
          data: {
            labels: data.categories.labels,
            datasets: [{
              data: data.categories.counts,
              backgroundColor: [
                '#2563eb', '#7c3aed', '#0284c7', '#059669', 
                '#d97706', '#db2777', '#4f46e5'
              ],
              borderWidth: 2,
              borderColor: '#ffffff'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12 } }
            },
            cutout: '68%'
          }
        });
      }

      // 3. Desk Occupancy by Zone Bar Chart
      if (deskCtx && data.desks) {
        new Chart(deskCtx, {
          type: 'bar',
          data: {
            labels: data.desks.labels.map(l => l.replace(' & ', '\n')),
            datasets: [{
              label: 'Reserved Desks Today',
              data: data.desks.counts,
              backgroundColor: 'rgba(124, 58, 237, 0.85)',
              borderRadius: 8
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } },
              x: { grid: { display: false } }
            }
          }
        });
      }
    })
    .catch(err => console.error('Failed to load admin analytics:', err));
}

// ================= Book Detail Preview Modal =================
function initBookModal() {
  const bookModal = document.getElementById('bookDetailModal');
  if (!bookModal) return;

  bookModal.addEventListener('show.bs.modal', function (event) {
    const button = event.relatedTarget;
    if (!button) return;

    const bookId = button.getAttribute('data-book-id');
    if (!bookId) return;

    fetch(`/api/books/${bookId}`)
      .then(res => res.json())
      .then(book => {
        document.getElementById('modalBookTitle').innerText = book.title || 'Book Details';
        document.getElementById('modalBookAuthor').innerText = book.author || '';
        document.getElementById('modalBookCategory').innerText = book.category || 'General';
        document.getElementById('modalBookISBN').innerText = book.isbn || '';
        document.getElementById('modalBookPublisher').innerText = book.publisher || 'Academic Press';
        document.getElementById('modalBookYear').innerText = book.publication_year || '2024';
        document.getElementById('modalBookLocation').innerText = book.location || 'Floor 1';
        document.getElementById('modalBookDesc').innerText = book.description || 'No description available.';
        document.getElementById('modalBookCover').src = book.cover_image || 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=600&q=80';

        const availBadge = document.getElementById('modalBookAvailBadge');
        if (availBadge) {
          if (book.is_available) {
            availBadge.className = 'badge bg-success';
            availBadge.innerText = `${book.available_copies} of ${book.quantity} Copies Available`;
          } else {
            availBadge.className = 'badge bg-danger';
            availBadge.innerText = 'All Copies Checked Out (Reservation Available)';
          }
        }

        // Action form buttons
        const borrowForm = document.getElementById('modalBorrowForm');
        const reserveForm = document.getElementById('modalReserveForm');
        if (borrowForm) borrowForm.action = `/loans/request/${book._id}`;
        if (reserveForm) reserveForm.action = `/reservations/book/${book._id}`;
      })
      .catch(err => console.error('Failed to fetch book detail:', err));
  });
}
