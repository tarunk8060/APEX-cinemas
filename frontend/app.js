// -------------------------------------------------------------
// WEB APP STATE MANAGEMENT
// -------------------------------------------------------------
const state = {
    currentUser: null, // { id: string, username: string, role: 'user' | 'admin' }
    activeView: 'catalog',
    movies: [],
    selectedMovie: null,
    selectedSeats: [],
    bookedSeats: {}, // seat_no -> user_id
    selectedShowtimeId: null,
    showtimes: [],
    cancelShowtimeId: null,
    cancelMoviePrice: 0,
    userBookedSeatsForCancel: [],
    seatsSelectedForCancel: [],
};

const BASE_URL = (() => {
    // If served directly by FastAPI (port 8000) or deployed on Render → use relative URLs
    // If opened via Live Server (port 5500), file://, or any other port → point to FastAPI backend
    const port = window.location.port;
    const protocol = window.location.protocol;
    if (protocol === 'file:' || (port && port !== '8000')) {
        return 'http://127.0.0.1:8000';
    }
    return ''; // Same-origin (FastAPI is the server)
})();


// -------------------------------------------------------------
// UTILITY HELPERS
// -------------------------------------------------------------
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast-notification');
    toast.textContent = message;
    toast.className = `toast-notification show ${type}`;

    setTimeout(() => {
        toast.className = 'toast-notification';
    }, 3500);
}

// -------------------------------------------------------------
// UNIVERSAL MODAL ENGINE
// -------------------------------------------------------------
let _modalAction = null;

/**
 * showModal({ type, icon, title, subtitle, details, confirmLabel, confirmIcon, onConfirm })
 * type: 'success' | 'danger' | 'warning' | 'info'
 * details: array of { label, value, highlight? }
 */
function showModal({ type = 'info', icon = 'fa-circle-question', title = 'Are you sure?',
    subtitle = '', details = [], confirmLabel = 'Confirm',
    confirmIcon = 'fa-check', onConfirm }) {

    _modalAction = onConfirm;

    // Set icon badge
    const badge = document.getElementById('modal-icon-badge');
    badge.className = `modal-icon-badge type-${type}`;
    document.getElementById('modal-icon').className = `fa-solid ${icon}`;

    // Set text
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-subtitle').textContent = subtitle;

    // Build detail rows
    const box = document.getElementById('modal-detail-box');
    box.innerHTML = details.map(d => `
        <div class="modal-detail-row">
            <span class="detail-label">${d.label}</span>
            <span class="detail-value${d.highlight ? ' highlight' : ''}">${d.value}</span>
        </div>`).join('');

    // Style confirm button
    const confirmBtn = document.getElementById('modal-confirm-btn');
    confirmBtn.className = `btn modal-btn type-${type}`;
    document.getElementById('modal-confirm-icon').className = `fa-solid ${confirmIcon}`;
    document.getElementById('modal-confirm-label').textContent = confirmLabel;

    // Show overlay
    document.getElementById('confirm-modal-overlay').classList.remove('hidden');
}

function closeConfirmModal() {
    _modalAction = null;
    document.getElementById('confirm-modal-overlay').classList.add('hidden');
}

function runModalAction() {
    const action = _modalAction;
    closeConfirmModal();
    if (typeof action === 'function') action();
}

function handleModalOverlayClick(e) {
    // Close if clicking the backdrop (not the card itself)
    if (e.target === document.getElementById('confirm-modal-overlay')) {
        closeConfirmModal();
    }
}

async function apiRequest(endpoint, options = {}) {
    const defaultHeaders = {
        'Content-Type': 'application/json',
    };

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers
        }
    };

    try {
        const response = await fetch(`${BASE_URL}${endpoint}`, config);

        // Always try to parse JSON regardless of content-type
        let data = null;
        const text = await response.text();
        if (text) {
            try {
                data = JSON.parse(text);
            } catch (parseErr) {
                console.warn('JSON parse failed for response from', endpoint, parseErr);
            }
        }

        if (!response.ok) {
            let errMsg = `Server error ${response.status}`;
            if (data && data.detail) {
                // FastAPI returns detail as a string (4xx errors) or array (422 validation)
                if (typeof data.detail === 'string') {
                    errMsg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    // 422 validation error — extract field + message from each item
                    errMsg = data.detail
                        .map(e => {
                            const field = e.loc ? e.loc[e.loc.length - 1] : 'field';
                            return `${field}: ${e.msg}`;
                        })
                        .join(', ');
                }
            }
            throw new Error(errMsg);
        }
        return data;
    } catch (error) {
        if (error.name === 'TypeError') {
            console.error('Network error — server may be down:', error);
            throw new Error('Cannot connect to server. Please make sure the backend is running.');
        }
        console.error(`API Error on ${endpoint}:`, error);
        throw error;
    }
}

// Theme Switcher
function changeTheme(themeName) {
    if (themeName === 'light') {
        document.body.className = 'light-theme';
    } else {
        document.body.className = 'dark-theme';
    }
}

// -------------------------------------------------------------
// AUTHENTICATION INTERFACES
// -------------------------------------------------------------
function switchAuthTab(portal) {
    const tabUser = document.getElementById('tab-btn-user');
    const tabAdmin = document.getElementById('tab-btn-admin');
    const portalUser = document.getElementById('portal-user');
    const portalAdmin = document.getElementById('portal-admin');

    if (portal === 'user') {
        tabUser.classList.add('active');
        tabAdmin.classList.remove('active');
        portalUser.classList.add('active');
        portalAdmin.classList.remove('active');
    } else {
        tabAdmin.classList.add('active');
        tabUser.classList.remove('active');
        portalAdmin.classList.add('active');
        portalUser.classList.remove('active');
    }
}

function toggleUserAuthMode(mode) {
    const signinFrame = document.getElementById('user-signin-frame');
    const registerFrame = document.getElementById('user-register-frame');

    if (mode === 'login') {
        signinFrame.classList.add('active');
        registerFrame.classList.remove('active');
    } else {
        registerFrame.classList.add('active');
        signinFrame.classList.remove('active');
    }
}

// SIGN IN & SIGN UP ACTIONS
async function handleUserSignIn(e) {
    e.preventDefault();
    const nameInput = document.getElementById('user-login-name').value.trim();
    const passInput = document.getElementById('user-login-pass').value.trim();

    try {
        const result = await apiRequest('/users/login', {
            method: 'POST',
            body: JSON.stringify({ username: nameInput, password: passInput })
        });

        state.currentUser = {
            id: result.id,
            username: result.username,
            role: 'user'
        };
        localStorage.setItem('currentUser', JSON.stringify(state.currentUser));

        onLoginSuccess();
        showToast(result.message || `Welcome back, ${result.username}!`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleUserSignUp(e) {
    e.preventDefault();
    const nameInput = document.getElementById('user-reg-name').value.trim();
    const passInput = document.getElementById('user-reg-pass').value.trim();

    try {
        const result = await apiRequest('/users/register', {
            method: 'POST',
            body: JSON.stringify({ username: nameInput, password: passInput })
        });

        // Auto sign-in
        state.currentUser = {
            id: result.id,
            username: result.username,
            role: 'user'
        };
        localStorage.setItem('currentUser', JSON.stringify(state.currentUser));

        onLoginSuccess();
        showToast(`Account created successfully! Welcome, ${result.username}!`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleAdminSignIn(e) {
    e.preventDefault();
    const nameInput = document.getElementById('admin-login-name').value.trim();
    const passInput = document.getElementById('admin-login-pass').value.trim();

    try {
        const result = await apiRequest('/admins/login', {
            method: 'POST',
            body: JSON.stringify({ username: nameInput, password: passInput })
        });

        state.currentUser = {
            id: 'admin_sys',
            username: result.username,
            role: 'admin'
        };
        localStorage.setItem('currentUser', JSON.stringify(state.currentUser));

        onLoginSuccess();
        showToast(result.message || 'Logged in as Admin!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function onLoginSuccess() {
    // Hide login screen
    document.getElementById('auth-overlay').classList.add('hidden');

    // Show main app layout FIRST so views can render into a visible container
    document.getElementById('app-layout').classList.remove('hidden');

    // Configure session UI cards
    document.getElementById('session-username').textContent = state.currentUser.username;
    document.getElementById('session-role').textContent = `Role: ${state.currentUser.role.toUpperCase()}`;

    // Hide/show admin panel buttons based on role
    const adminNav = document.getElementById('nav-btn-admin');
    if (state.currentUser.role === 'admin') {
        adminNav.classList.remove('hidden-admin');
    } else {
        adminNav.classList.add('hidden-admin');
    }

    // Restore active view or navigate to default
    const savedView = localStorage.getItem('activeView');
    if (savedView) {
        if (savedView === 'admin' && state.currentUser.role !== 'admin') {
            showView('catalog');
        } else if (savedView === 'booking' || savedView === 'cancel-booking') {
            // Safe fallback if refreshed on booking subview (since selectedMovie is in-memory)
            showView('catalog');
        } else {
            showView(savedView);
        }
    } else {
        if (state.currentUser.role === 'admin') {
            showView('admin');
        } else {
            showView('catalog');
        }
    }
}

function handleLogout() {
    showModal({
        type: 'warning',
        icon: 'fa-right-from-bracket',
        title: 'Log Out?',
        subtitle: 'You will be returned to the login screen.',
        confirmLabel: 'Log Out',
        confirmIcon: 'fa-right-from-bracket',
        onConfirm: () => {
            state.currentUser = null;
            localStorage.removeItem('currentUser');
            localStorage.removeItem('activeView');

            document.getElementById('app-layout').classList.add('hidden');
            document.getElementById('auth-overlay').classList.remove('hidden');

            document.getElementById('user-login-name').value = '';
            document.getElementById('user-login-pass').value = '';
            document.getElementById('user-reg-name').value = '';
            document.getElementById('user-reg-pass').value = '';
            document.getElementById('admin-login-name').value = '';
            document.getElementById('admin-login-pass').value = '';

            toggleUserAuthMode('login');
            switchAuthTab('user');
            showToast('Logged out successfully.', 'info');
        }
    });
}

// -------------------------------------------------------------
// SINGLE PAGE VIEW CONTROLLER
// -------------------------------------------------------------
function showView(viewName) {
    // Role guard — users cannot access admin view
    if (viewName === 'admin' && (!state.currentUser || state.currentUser.role !== 'admin')) {
        showToast('Access denied: Admin only.', 'error');
        showView('catalog');
        return;
    }

    state.activeView = viewName;
    localStorage.setItem('activeView', viewName);

    // Toggle active classes in HTML
    document.querySelectorAll('.app-view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`view-${viewName}`).classList.add('active');

    // Highlight sidebar active item
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });

    if (viewName === 'catalog') {
        document.getElementById('nav-btn-movies').classList.add('active');
        loadCatalog();
    } else if (viewName === 'bookings') {
        document.getElementById('nav-btn-bookings').classList.add('active');
        loadBookings();
    } else if (viewName === 'admin') {
        document.getElementById('nav-btn-admin').classList.add('active');
        loadAdminPanel();
    }
}

// -------------------------------------------------------------
// VIEW 1: MOVIES CATALOG VIEW RENDERING
// -------------------------------------------------------------
async function loadCatalog() {
    const grid = document.getElementById('movies-grid');
    grid.innerHTML = '<p class="subtitle text-center">Loading movies catalog...</p>';

    try {
        const movies = await apiRequest('/movies');
        state.movies = movies;

        // Sort movies by favorite genre based on previous bookings
        if (state.currentUser && state.currentUser.role === 'user') {
            try {
                const bookings = await apiRequest(`/bookings?user_id=${state.currentUser.id}`);
                if (bookings.length > 0) {
                    const genreCounts = {};
                    bookings.forEach(b => {
                        const m = movies.find(movie => movie.id === b.movie_id);
                        if (m && m.genre) {
                            const genres = m.genre.split(' ');
                            genres.forEach(g => {
                                genreCounts[g] = (genreCounts[g] || 0) + 1;
                            });
                        }
                    });

                    const sortedGenres = Object.keys(genreCounts).sort((a, b) => genreCounts[b] - genreCounts[a]);

                    if (sortedGenres.length > 0) {
                        const topGenres = sortedGenres.slice(0, 2); // Use top 2 genres

                        movies.sort((a, b) => {
                            const aScore = (a.genre || '').split(' ').filter(g => topGenres.includes(g)).length;
                            const bScore = (b.genre || '').split(' ').filter(g => topGenres.includes(g)).length;
                            return bScore - aScore;
                        });
                    }
                }
            } catch (err) {
                console.warn('Could not fetch bookings to sort catalog', err);
            }
        }

        if (movies.length === 0) {
            grid.innerHTML = `
                <div class="text-center w-full" style="grid-column: 1 / -1; padding: 60px 0;">
                    <p class="subtitle" style="font-size: 16px; margin-bottom: 20px;">No movies are currently showing.</p>
                    ${state.currentUser && state.currentUser.role === 'admin' ? '<button class="btn btn-primary" onclick="showView(\'admin\')">Go Add Movies</button>' : ''}
                </div>
            `;
            return;
        }

        grid.innerHTML = '';
        movies.forEach(movie => {
            const card = document.createElement('div');
            card.className = 'movie-card glass-card';

            // Build poster image HTML
            const posterHTML = movie.image_url
                ? `<div class="movie-poster-wrap">
                       <img src="${escapeHTML(movie.image_url)}" alt="${escapeHTML(movie.name)} poster" class="movie-poster" onerror="this.parentElement.style.display='none'">
                   </div>`
                : `<div class="movie-poster-placeholder">
                       <i class="fa-solid fa-film fa-3x"></i>
                   </div>`;

            const ratingVal = movie.age_rating || 'U';
            let badgeColorClass = 'badge-u';
            if (ratingVal === 'A' || ratingVal === '18+') badgeColorClass = 'badge-a';
            else if (ratingVal === 'UA' || ratingVal === 'PG') badgeColorClass = 'badge-ua';

            card.innerHTML = `
                <div class="card-top-accent"></div>
                ${posterHTML}
                <div class="movie-card-body">
                    <h3 class="movie-title">${escapeHTML(movie.name)}</h3>
                    <div class="movie-details-list">
                        <div class="detail-item">
                            <span class="label">🏷️ Genre:</span>
                            <span class="value">${escapeHTML(movie.genre || 'N/A')}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">🗣️ Language:</span>
                            <span class="value">${escapeHTML(movie.language)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">🖥️ Screen:</span>
                            <span class="value">${escapeHTML(movie.screen_no)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">🎟️ Ticket Price:</span>
                            <span class="value price-tag">₹${movie.price}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">🪑 Total Capacity:</span>
                            <span class="value">${movie.seats_available} Seats</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">  Rating:</span>
                            <span class="value badge-rating ${badgeColorClass}">${escapeHTML(ratingVal)}</span>
                        </div>
                    </div>
                    <button class="btn btn-primary btn-block" onclick="startBooking('${movie.id}')">
                        Book Tickets
                    </button>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (err) {
        showToast('Error loading movies: ' + err.message, 'error');
        grid.innerHTML = '<p class="subtitle text-center highlight">Failed to load movie catalog. Database issue.</p>';
    }
}

// -------------------------------------------------------------
// VIEW 2: INTERACTIVE SEAT BOOKING
// -------------------------------------------------------------
async function startBooking(movieId) {
    try {
        const movie = await apiRequest(`/movies/${movieId}`);
        
        // Age Restriction Check
        const rating = movie.age_rating || 'U';
        if (rating === 'A' || rating === '18+') {
            state.pendingBookingMovieId = movieId;
            document.getElementById('age-warning-modal-overlay').classList.remove('hidden');
            return;
        }
        
        await proceedWithBooking(movie);
    } catch (err) {
        showToast('Error initializing booking details: ' + err.message, 'error');
    }
}

async function proceedWithBooking(movie) {
    try {
        state.selectedMovie = movie;
        state.selectedSeats = [];
        state.selectedShowtimeId = null;
        state.showtimes = [];

        // Show Booking Page
        showView('booking');

        // Load Receipt Details
        document.getElementById('booking-movie-title').textContent = `Select Seats for ${movie.name}`;
        document.getElementById('summary-movie-name').textContent = movie.name;
        document.getElementById('summary-movie-lang').textContent = movie.language;
        document.getElementById('summary-movie-screen').textContent = movie.screen_no;
        document.getElementById('summary-movie-price').textContent = `₹${movie.price}`;
        document.getElementById('summary-movie-date').textContent = 'N/A';
        document.getElementById('summary-movie-time').textContent = 'N/A';

        updateReceiptDisplay();

        // Load Showtimes Map from API
        const showtimes = await apiRequest(`/movies/${movie.id}/showtimes`);
        state.showtimes = showtimes;
        renderShowtimes(showtimes);

        // Display placeholder in the seat selector until showtime is selected
        document.getElementById('seat-layout-grid').innerHTML = `
            <div class="text-center w-full" style="grid-column: 1 / -1; padding: 40px 0;">
                <p class="subtitle showtime-empty-msg"><i class="fa-solid fa-circle-info"></i> Please select a showtime above to view available seats.</p>
            </div>
        `;

        renderRecommendations(movie.recommendations || []);
    } catch (err) {
        showToast('Error loading showtimes: ' + err.message, 'error');
    }
}

function confirmAgeWarning() {
    document.getElementById('age-warning-modal-overlay').classList.add('hidden');
    if (state.pendingBookingMovieId) {
        const movieId = state.pendingBookingMovieId;
        state.pendingBookingMovieId = null;
        apiRequest(`/movies/${movieId}`).then(movie => {
            proceedWithBooking(movie);
        }).catch(err => {
            showToast('Error: ' + err.message, 'error');
        });
    }
}

function closeAgeWarningModal() {
    document.getElementById('age-warning-modal-overlay').classList.add('hidden');
    state.pendingBookingMovieId = null;
    showView('catalog');
}

function handleAgeWarningOverlayClick(event) {
    if (event.target.id === 'age-warning-modal-overlay') {
        closeAgeWarningModal();
    }
}

function renderShowtimes(showtimes) {
    const container = document.getElementById('showtimes-list');
    container.innerHTML = '';

    if (showtimes.length === 0) {
        container.innerHTML = '<p class="showtime-empty-msg"><i class="fa-solid fa-triangle-exclamation"></i> No showtimes scheduled for this movie.</p>';
        return;
    }

    showtimes.forEach(st => {
        const pill = document.createElement('div');
        pill.className = 'showtime-pill';
        pill.dataset.id = st.id;

        // Format the date if it's YYYY-MM-DD
        let displayDate = st.show_date;
        try {
            const dateObj = new Date(st.show_date);
            if (!isNaN(dateObj.getTime())) {
                displayDate = dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric', weekday: 'short' });
            }
        } catch (e) {}

        pill.innerHTML = `
            <span class="showtime-date">${displayDate}</span>
            <span class="showtime-time">${st.show_time}</span>
        `;
        pill.onclick = () => selectShowtime(st.id);
        container.appendChild(pill);
    });
}

async function selectShowtime(showtimeId) {
    try {
        state.selectedShowtimeId = showtimeId;
        state.selectedSeats = [];
        updateReceiptDisplay();

        // Highlight active pill
        document.querySelectorAll('.showtime-pill').forEach(pill => {
            if (parseInt(pill.dataset.id) === showtimeId) {
                pill.classList.add('active');
            } else {
                pill.classList.remove('active');
            }
        });

        // Update summary Date and Time
        const selectedSt = state.showtimes.find(st => st.id === showtimeId);
        if (selectedSt) {
            document.getElementById('summary-movie-date').textContent = selectedSt.show_date;
            document.getElementById('summary-movie-time').textContent = selectedSt.show_time;
        }

        // Load Seat Map for the showtime
        const gridContainer = document.getElementById('seat-layout-grid');
        gridContainer.innerHTML = '<p class="subtitle text-center">Loading seat map...</p>';

        const seatData = await apiRequest(`/showtimes/${showtimeId}/seats`);
        state.bookedSeats = seatData.seats; // seat_no -> boolean (true: booked, false: available)

        // Fetch bookings to know who booked what (for color-coding)
        const allBookings = await apiRequest('/bookings');
        const userSeatMappings = {};
        allBookings.forEach(booking => {
            if (booking.showtime_id === showtimeId) {
                userSeatMappings[booking.seat_no] = booking.user_id || 'Anonymous';
            }
        });

        const seatStatesMap = {};
        for (const seatNo in state.bookedSeats) {
            const isBooked = state.bookedSeats[seatNo];
            seatStatesMap[seatNo] = isBooked ? (userSeatMappings[seatNo] || 'Anonymous') : null;
        }

        renderSeatGrid(state.selectedMovie.seats_available, seatStatesMap);
    } catch (err) {
        showToast('Error loading seats: ' + err.message, 'error');
    }
}

function renderSeatGrid(totalSeats, seatStatesMap) {
    const gridContainer = document.getElementById('seat-layout-grid');
    gridContainer.innerHTML = '';

    const displaySeats = Math.min(totalSeats, 150);
    const rowLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

    if (totalSeats > 120) {
        // Special 24-column layout: 5 - 2 aisle - 10 - 2 aisle - 5
        // Row A: 24 continuous seats
        // Rows B, C...: 20 seats with aisles in columns 6, 7 and 18, 19
        let rowsCount = 1;
        if (displaySeats > 24) {
            rowsCount += Math.ceil((displaySeats - 24) / 20);
        }

        for (let r = 0; r < rowsCount; r++) {
            const letter = rowLetters[r];
            const rowDiv = document.createElement('div');
            rowDiv.className = 'seat-row';

            // Row letter on left
            const label = document.createElement('span');
            label.className = 'row-label';
            label.textContent = letter;
            rowDiv.appendChild(label);

            if (r === 0) {
                // Row A: 24 continuous seats
                const seatsInRowA = Math.min(24, displaySeats);
                for (let seatNum = 1; seatNum <= seatsInRowA; seatNum++) {
                    const seatNo = `A${seatNum}`;
                    const seatBtn = document.createElement('button');
                    seatBtn.className = 'seat';
                    seatBtn.textContent = seatNum;

                    const bookedById = seatStatesMap[seatNo];
                    const isBooked = bookedById !== null && bookedById !== undefined;
                    const isBookedByMe = isBooked && (bookedById === state.currentUser.id);

                    if (isBooked) {
                        if (isBookedByMe) {
                            seatBtn.classList.add('your-booking');
                            seatBtn.title = 'Your seat';
                        } else {
                            seatBtn.classList.add('booked');
                            seatBtn.title = 'Reserved';
                        }
                    } else {
                        seatBtn.title = `Seat ${seatNo}`;
                        seatBtn.onclick = () => selectSeat(seatNo, seatBtn);
                    }
                    rowDiv.appendChild(seatBtn);
                }
            } else {
                // Rows B, C...: 20 seats with aisles in columns 6, 7 and 18, 19
                let seatNum = 1;
                const rowLimit = (r === rowsCount - 1) ? (displaySeats - 24 - (r - 1) * 20) : 20;

                for (let col = 1; col <= 24; col++) {
                    if (col === 6 || col === 7 || col === 18 || col === 19) {
                        const spacer = document.createElement('div');
                        spacer.className = 'seat-aisle-spacer';
                        rowDiv.appendChild(spacer);
                    } else {
                        if (seatNum <= rowLimit) {
                            const seatNo = `${letter}${seatNum}`;
                            const seatBtn = document.createElement('button');
                            seatBtn.className = 'seat';
                            seatBtn.textContent = seatNum;

                            const bookedById = seatStatesMap[seatNo];
                            const isBooked = bookedById !== null && bookedById !== undefined;
                            const isBookedByMe = isBooked && (bookedById === state.currentUser.id);

                            if (isBooked) {
                                if (isBookedByMe) {
                                    seatBtn.classList.add('your-booking');
                                    seatBtn.title = 'Your seat';
                                } else {
                                    seatBtn.classList.add('booked');
                                    seatBtn.title = 'Reserved';
                                }
                            } else {
                                seatBtn.title = `Seat ${seatNo}`;
                                seatBtn.onclick = () => selectSeat(seatNo, seatBtn);
                            }
                            rowDiv.appendChild(seatBtn);
                            seatNum++;
                        } else {
                            const emptySpacer = document.createElement('div');
                            emptySpacer.style.width = '32px';
                            emptySpacer.style.height = '32px';
                            rowDiv.appendChild(emptySpacer);
                        }
                    }
                }
            }
            gridContainer.appendChild(rowDiv);
        }
    } else {
        // Standard 10-column layout with middle aisle (c === 5)
        const cols = 10;
        const rowsCount = Math.ceil(displaySeats / cols);

        for (let r = 0; r < rowsCount; r++) {
            const letter = rowLetters[r];
            const rowDiv = document.createElement('div');
            rowDiv.className = 'seat-row';

            // Row letter on left
            const label = document.createElement('span');
            label.className = 'row-label';
            label.textContent = letter;
            rowDiv.appendChild(label);

            for (let c = 0; c < cols; c++) {
                const seatNum = c + 1;
                const seatNo = `${letter}${seatNum}`;

                if (c === 5) {
                    const spacer = document.createElement('div');
                    spacer.className = 'seat-aisle-spacer';
                    rowDiv.appendChild(spacer);
                }

                const seatBtn = document.createElement('button');
                seatBtn.className = 'seat';
                seatBtn.textContent = seatNum;

                const bookedById = seatStatesMap[seatNo];
                const isBooked = bookedById !== null && bookedById !== undefined;
                const isBookedByMe = isBooked && (bookedById === state.currentUser.id);

                if (isBooked) {
                    if (isBookedByMe) {
                        seatBtn.classList.add('your-booking');
                        seatBtn.title = 'Your seat';
                    } else {
                        seatBtn.classList.add('booked');
                        seatBtn.title = 'Reserved';
                    }
                } else {
                    seatBtn.title = `Seat ${seatNo}`;
                    seatBtn.onclick = () => selectSeat(seatNo, seatBtn);
                }

                rowDiv.appendChild(seatBtn);
            }
            gridContainer.appendChild(rowDiv);
        }
    }
}

function selectSeat(seatNo, element) {
    const idx = state.selectedSeats.indexOf(seatNo);
    if (idx > -1) {
        state.selectedSeats.splice(idx, 1);
        element.classList.remove('selected');
    } else {
        state.selectedSeats.push(seatNo);
        element.classList.add('selected');
    }

    // Sort seats alphabetically
    state.selectedSeats.sort((a, b) => {
        const aRow = a[0], bRow = b[0];
        const aNum = parseInt(a.slice(1)), bNum = parseInt(b.slice(1));
        if (aRow !== bRow) return aRow.localeCompare(bRow);
        return aNum - bNum;
    });

    updateReceiptDisplay();
}

function updateReceiptDisplay() {
    const seatsText = state.selectedSeats.length > 0 ? state.selectedSeats.join(', ') : 'None';
    document.getElementById('summary-selected-seats').textContent = `Selected Seats: ${seatsText}`;
    document.getElementById('summary-ticket-count').textContent = `Total Tickets: ${state.selectedSeats.length}`;

    const totalPrice = state.selectedSeats.length * (state.selectedMovie ? state.selectedMovie.price : 0);
    document.getElementById('summary-total-price').textContent = `₹${totalPrice}`;

    // Enable/disable confirm button
    const confirmBtn = document.getElementById('confirm-booking-btn');
    confirmBtn.disabled = (state.selectedSeats.length === 0 || !state.selectedShowtimeId);
}

function handleConfirmBooking() {
    if (state.selectedSeats.length === 0 || !state.selectedShowtimeId) return;

    const movie = state.selectedMovie;
    const selectedSt = state.showtimes.find(st => st.id === state.selectedShowtimeId);
    const dateStr = selectedSt ? selectedSt.show_date : 'N/A';
    const timeStr = selectedSt ? selectedSt.show_time : 'N/A';
    const seatsStr = state.selectedSeats.join(', ');
    const price = state.selectedSeats.length * movie.price;

    showModal({
        type: 'success',
        icon: 'fa-ticket',
        title: 'Confirm Reservation',
        subtitle: 'Review your booking details below.',
        details: [
            { label: 'Movie', value: movie.name },
            { label: 'Language', value: movie.language },
            { label: 'Screen', value: movie.screen_no },
            { label: 'Date', value: dateStr },
            { label: 'Time', value: timeStr },
            { label: 'Seats', value: seatsStr },
            { label: 'Total Price', value: `\u20B9${price}`, highlight: true }
        ],
        confirmLabel: 'Book Now',
        confirmIcon: 'fa-check-circle',
        onConfirm: async () => {
            try {
                await apiRequest(`/showtimes/${state.selectedShowtimeId}/book`, {
                    method: 'POST',
                    body: JSON.stringify({
                        user_name: state.currentUser.username,
                        user_id: state.currentUser.id,
                        seats: state.selectedSeats
                    })
                });
                showToast('Seats reserved successfully! Enjoy your show.', 'success');
                showView('bookings');
            } catch (err) {
                showToast('Booking failed: ' + err.message, 'error');
                if (selectedSt) {
                    selectShowtime(state.selectedShowtimeId);
                } else {
                    startBooking(movie.id);
                }
            }
        }
    });
}

function renderRecommendations(recs) {
    const list = document.getElementById('booking-recommendations');
    list.innerHTML = '';

    if (recs.length === 0) {
        list.innerHTML = '<p class="subtitle text-center" style="font-size:11px;">No similar movies found.</p>';
        return;
    }

    recs.forEach(rec => {
        // Find if movie exists in system to allow instant booking link
        const systemMovie = state.movies.find(m => m.name.toLowerCase() === rec.title.toLowerCase());

        // Skip movies that are not currently in the system
        if (!systemMovie) return;

        const card = document.createElement('div');
        card.className = 'rec-card';

        card.innerHTML = `
            <div class="rec-info">
                <h5>${escapeHTML(rec.title)}</h5>
                <p>${escapeHTML(rec.genres)}</p>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="startBooking('${systemMovie.id}')">Book Now</button>
        `;
        list.appendChild(card);
    });

    // Check again in case all recommendations were filtered out
    if (list.children.length === 0) {
        list.innerHTML = '<p class="subtitle text-center" style="font-size:11px;">No similar movies found.</p>';
    }
}

// -------------------------------------------------------------
// VIEW 3: MY BOOKINGS LIST VIEW
// -------------------------------------------------------------
async function loadBookings() {
    const listContainer = document.getElementById('bookings-list-container');
    listContainer.innerHTML = '<p class="subtitle text-center">Fetching reservations list...</p>';

    try {
        const result = await apiRequest(`/bookings?user_id=${state.currentUser.id}`);

        if (result.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center w-full" style="padding: 60px 0;">
                    <p class="subtitle" style="font-size:16px; margin-bottom:20px;">You have no active cinema bookings yet.</p>
                    <button class="btn btn-primary" onclick="showView('catalog')">View Movies & Book Tickets</button>
                </div>
            `;
            return;
        }

        listContainer.innerHTML = '';

        const activeBookings = result.filter(b => !b.is_expired);
        const pastBookings = result.filter(b => b.is_expired);

        // Group Active Bookings by showtime_id
        const groupedActive = {};
        activeBookings.forEach(booking => {
            const key = booking.showtime_id;
            if (!groupedActive[key]) {
                groupedActive[key] = {
                    showtime_id: booking.showtime_id,
                    movie_id: booking.movie_id,
                    movie_name: booking.movie_name,
                    show_date: booking.show_date,
                    show_time: booking.show_time,
                    seats: [],
                };
            }
            groupedActive[key].seats.push(booking.seat_no);
        });

        // Group Past/Expired Bookings by showtime_id
        const groupedPast = {};
        pastBookings.forEach(booking => {
            const key = booking.showtime_id;
            if (!groupedPast[key]) {
                groupedPast[key] = {
                    showtime_id: booking.showtime_id,
                    movie_id: booking.movie_id,
                    movie_name: booking.movie_name,
                    show_date: booking.show_date,
                    show_time: booking.show_time,
                    seats: [],
                };
            }
            groupedPast[key].seats.push(booking.seat_no);
        });

        // 1. Render Active Bookings
        const activeList = Object.values(groupedActive);
        if (activeList.length > 0) {
            const activeHeader = document.createElement('div');
            activeHeader.className = 'booking-group-title active-title';
            activeHeader.innerHTML = '<i class="fa-solid fa-ticket"></i> Active Reservations';
            listContainer.appendChild(activeHeader);

            activeList.forEach(booking => {
                const movie = state.movies.find(m => m.id === booking.movie_id) || { name: booking.movie_name, language: 'N/A', screen_no: 'N/A', price: booking.price || 0 };
                const card = document.createElement('div');
                card.className = 'booking-row-card glass-card';
                
                // Sort seats alphabetically
                booking.seats.sort((a, b) => {
                    const aRow = a[0], bRow = b[0];
                    const aNum = parseInt(a.slice(1)), bNum = parseInt(b.slice(1));
                    if (aRow !== bRow) return aRow.localeCompare(bRow);
                    return aNum - bNum;
                });
                
                const seatsStr = booking.seats.join(', ');
                const totalCost = booking.seats.length * movie.price;

                const qrData = `Apex Cinemas Ticket: ${movie.name} | Seats: ${seatsStr} | Date: ${booking.show_date} | Time: ${booking.show_time} | Screen: ${movie.screen_no}`;

                card.innerHTML = `
                    <div class="booking-indicator-bar"></div>
                    <div class="booking-info-block">
                        <h4 class="booking-movie-header">${escapeHTML(movie.name)} (${escapeHTML(movie.language || 'N/A')})</h4>
                        <p class="booking-meta-details">
                            <i class="fa-solid fa-desktop"></i> Screen: ${escapeHTML(movie.screen_no)}  |  
                            <i class="fa-solid fa-calendar-days"></i> ${escapeHTML(booking.show_date)}  |  
                            <i class="fa-solid fa-clock"></i> ${escapeHTML(booking.show_time)}  |  
                            <i class="fa-solid fa-chair"></i> Seats: ${escapeHTML(seatsStr)}  |  
                            <i class="fa-solid fa-indian-rupee-sign"></i> Total: ₹${totalCost}
                        </p>
                    </div>
                    <div class="booking-qr-code">
                        <img src="https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=${encodeURIComponent(qrData)}" alt="Ticket QR Code" class="qr-code-img">
                    </div>
                    <div class="booking-actions">
                        <button class="btn btn-danger btn-sm" onclick="startCancellation(${booking.showtime_id}, ['${booking.seats.join("','")}'])">
                            <i class="fa-solid fa-circle-xmark"></i> Cancel Booking
                        </button>
                    </div>
                `;
                listContainer.appendChild(card);
            });
        }

        // 2. Render Past/Expired Bookings
        const pastList = Object.values(groupedPast);
        if (pastList.length > 0) {
            const pastHeader = document.createElement('div');
            pastHeader.className = 'booking-group-title past-title';
            pastHeader.innerHTML = '<i class="fa-solid fa-clock-rotate-left"></i> Previous Bookings (Expired after 24 hrs)';
            listContainer.appendChild(pastHeader);

            pastList.forEach(booking => {
                const movie = state.movies.find(m => m.id === booking.movie_id) || { name: booking.movie_name, language: 'N/A', screen_no: 'N/A', price: booking.price || 0 };
                const card = document.createElement('div');
                card.className = 'booking-row-card glass-card expired';
                
                // Sort seats alphabetically
                booking.seats.sort((a, b) => {
                    const aRow = a[0], bRow = b[0];
                    const aNum = parseInt(a.slice(1)), bNum = parseInt(b.slice(1));
                    if (aRow !== bRow) return aRow.localeCompare(bRow);
                    return aNum - bNum;
                });
                
                const seatsStr = booking.seats.join(', ');
                const totalCost = booking.seats.length * movie.price;

                card.innerHTML = `
                    <div class="booking-indicator-bar"></div>
                    <div class="booking-info-block">
                        <h4 class="booking-movie-header">${escapeHTML(movie.name)} (${escapeHTML(movie.language || 'N/A')})</h4>
                        <p class="booking-meta-details">
                            <i class="fa-solid fa-desktop"></i> Screen: ${escapeHTML(movie.screen_no)}  |  
                            <i class="fa-solid fa-calendar-days"></i> ${escapeHTML(booking.show_date)}  |  
                            <i class="fa-solid fa-clock"></i> ${escapeHTML(booking.show_time)}  |  
                            <i class="fa-solid fa-chair"></i> Seats: ${escapeHTML(seatsStr)}  |  
                            <i class="fa-solid fa-indian-rupee-sign"></i> Total: ₹${totalCost}
                        </p>
                    </div>
                    <div class="booking-actions">
                        <span class="badge-expired"><i class="fa-solid fa-clock"></i> Expired</span>
                    </div>
                `;
                listContainer.appendChild(card);
            });
        }

    } catch (err) {
        showToast('Error loading bookings: ' + err.message, 'error');
        listContainer.innerHTML = '<p class="subtitle text-center highlight">Failed to fetch bookings. Database connectivity error.</p>';
    }
}

// -------------------------------------------------------------
// INTERACTIVE SEAT CANCELLATION FLOW
// -------------------------------------------------------------
async function startCancellation(showtimeId, seats) {
    try {
        state.cancelShowtimeId = showtimeId;
        state.userBookedSeatsForCancel = [...seats];
        state.seatsSelectedForCancel = [];

        // Load showtime and movie information
        const seatData = await apiRequest(`/showtimes/${showtimeId}/seats`);
        const movie = state.movies.find(m => m.id === seatData.movie_id) || { name: seatData.movie_name || 'Odyssey Feature', price: seatData.price || 150 };
        state.cancelMoviePrice = movie.price;

        // Open Cancellation View
        showView('cancel-booking');

        // Load Receipt Details
        document.getElementById('cancel-booking-title').textContent = `Cancel Tickets for ${movie.name}`;
        document.getElementById('cancel-summary-movie-name').textContent = movie.name;
        document.getElementById('cancel-summary-movie-date').textContent = seatData.show_date;
        document.getElementById('cancel-summary-movie-time').textContent = seatData.show_time;

        updateCancellationDisplay();

        // Build Seat States Map:
        // user_booked -> current user's seat
        // others_booked -> other user's seat
        // null -> free seat
        const seatStatesMap = {};
        for (const seatNo in seatData.seats) {
            const isBooked = seatData.seats[seatNo];
            if (isBooked) {
                if (seats.includes(seatNo)) {
                    seatStatesMap[seatNo] = 'user_booked';
                } else {
                    seatStatesMap[seatNo] = 'others_booked';
                }
            } else {
                seatStatesMap[seatNo] = null;
            }
        }

        renderCancelSeatGrid(movie.seats_available, seatStatesMap);
    } catch (err) {
        showToast('Error loading cancellation seating map: ' + err.message, 'error');
    }
}

function renderCancelSeatGrid(totalSeats, seatStatesMap) {
    const gridContainer = document.getElementById('cancel-seat-layout-grid');
    gridContainer.innerHTML = '';

    const displaySeats = Math.min(totalSeats, 150);
    const rowLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

    if (totalSeats > 120) {
        // Special 24-column layout: 5 - 2 aisle - 10 - 2 aisle - 5
        let rowsCount = 1;
        if (displaySeats > 24) {
            rowsCount += Math.ceil((displaySeats - 24) / 20);
        }

        for (let r = 0; r < rowsCount; r++) {
            const letter = rowLetters[r];
            const rowDiv = document.createElement('div');
            rowDiv.className = 'seat-row';

            // Row letter on left
            const label = document.createElement('span');
            label.className = 'row-label';
            label.textContent = letter;
            rowDiv.appendChild(label);

            if (r === 0) {
                // Row A: 24 continuous seats
                const seatsInRowA = Math.min(24, displaySeats);
                for (let seatNum = 1; seatNum <= seatsInRowA; seatNum++) {
                    const seatNo = `A${seatNum}`;
                    const seatBtn = document.createElement('button');
                    seatBtn.className = 'seat';
                    seatBtn.textContent = seatNum;

                    const stateVal = seatStatesMap[seatNo];
                    if (stateVal === 'user_booked') {
                        seatBtn.classList.add('your-booking');
                        seatBtn.title = `Your Seat ${seatNo} - Click to cancel`;
                        seatBtn.onclick = () => selectSeatForCancellation(seatNo, seatBtn);
                    } else if (stateVal === 'others_booked') {
                        seatBtn.classList.add('booked');
                        seatBtn.style.opacity = '0.35';
                        seatBtn.style.pointerEvents = 'none';
                        seatBtn.title = 'Reserved';
                    } else {
                        seatBtn.style.opacity = '0.2';
                        seatBtn.style.pointerEvents = 'none';
                        seatBtn.title = 'Available';
                    }
                    rowDiv.appendChild(seatBtn);
                }
            } else {
                // Rows B, C...: 20 seats with aisles in columns 6, 7 and 18, 19
                let seatNum = 1;
                const rowLimit = (r === rowsCount - 1) ? (displaySeats - 24 - (r - 1) * 20) : 20;

                for (let col = 1; col <= 24; col++) {
                    if (col === 6 || col === 7 || col === 18 || col === 19) {
                        const spacer = document.createElement('div');
                        spacer.className = 'seat-aisle-spacer';
                        rowDiv.appendChild(spacer);
                    } else {
                        if (seatNum <= rowLimit) {
                            const seatNo = `${letter}${seatNum}`;
                            const seatBtn = document.createElement('button');
                            seatBtn.className = 'seat';
                            seatBtn.textContent = seatNum;

                            const stateVal = seatStatesMap[seatNo];
                            if (stateVal === 'user_booked') {
                                seatBtn.classList.add('your-booking');
                                seatBtn.title = `Your Seat ${seatNo} - Click to cancel`;
                                seatBtn.onclick = () => selectSeatForCancellation(seatNo, seatBtn);
                            } else if (stateVal === 'others_booked') {
                                seatBtn.classList.add('booked');
                                seatBtn.style.opacity = '0.35';
                                seatBtn.style.pointerEvents = 'none';
                                seatBtn.title = 'Reserved';
                            } else {
                                seatBtn.style.opacity = '0.2';
                                seatBtn.style.pointerEvents = 'none';
                                seatBtn.title = 'Available';
                            }
                            rowDiv.appendChild(seatBtn);
                            seatNum++;
                        } else {
                            const emptySpacer = document.createElement('div');
                            emptySpacer.style.width = '32px';
                            emptySpacer.style.height = '32px';
                            rowDiv.appendChild(emptySpacer);
                        }
                    }
                }
            }
            gridContainer.appendChild(rowDiv);
        }
    } else {
        // Standard 10-column layout
        const cols = 10;
        const rowsCount = Math.ceil(displaySeats / cols);

        for (let r = 0; r < rowsCount; r++) {
            const letter = rowLetters[r];
            const rowDiv = document.createElement('div');
            rowDiv.className = 'seat-row';

            // Row letter on left
            const label = document.createElement('span');
            label.className = 'row-label';
            label.textContent = letter;
            rowDiv.appendChild(label);

            for (let c = 0; c < cols; c++) {
                const seatNum = c + 1;
                const seatNo = `${letter}${seatNum}`;

                if (c === 5) {
                    const spacer = document.createElement('div');
                    spacer.className = 'seat-aisle-spacer';
                    rowDiv.appendChild(spacer);
                }

                const seatBtn = document.createElement('button');
                seatBtn.className = 'seat';
                seatBtn.textContent = seatNum;

                const stateVal = seatStatesMap[seatNo];
                if (stateVal === 'user_booked') {
                    seatBtn.classList.add('your-booking');
                    seatBtn.title = `Your Seat ${seatNo} - Click to cancel`;
                    seatBtn.onclick = () => selectSeatForCancellation(seatNo, seatBtn);
                } else if (stateVal === 'others_booked') {
                    seatBtn.classList.add('booked');
                    seatBtn.style.opacity = '0.35';
                    seatBtn.style.pointerEvents = 'none';
                    seatBtn.title = 'Reserved';
                } else {
                    seatBtn.style.opacity = '0.2';
                    seatBtn.style.pointerEvents = 'none';
                    seatBtn.title = 'Available';
                }

                rowDiv.appendChild(seatBtn);
            }
            gridContainer.appendChild(rowDiv);
        }
    }
}

function selectSeatForCancellation(seatNo, element) {
    const idx = state.seatsSelectedForCancel.indexOf(seatNo);
    if (idx > -1) {
        state.seatsSelectedForCancel.splice(idx, 1);
        element.classList.remove('selected');
        element.classList.add('your-booking');
    } else {
        state.seatsSelectedForCancel.push(seatNo);
        element.classList.remove('your-booking');
        element.classList.add('selected');
    }

    // Sort seats alphabetically
    state.seatsSelectedForCancel.sort((a, b) => {
        const aRow = a[0], bRow = b[0];
        const aNum = parseInt(a.slice(1)), bNum = parseInt(b.slice(1));
        if (aRow !== bRow) return aRow.localeCompare(bRow);
        return aNum - bNum;
    });

    updateCancellationDisplay();
}

function updateCancellationDisplay() {
    const seatsText = state.seatsSelectedForCancel.length > 0 ? state.seatsSelectedForCancel.join(', ') : 'None';
    document.getElementById('cancel-summary-seats').textContent = `Selected to Cancel: ${seatsText}`;
    document.getElementById('cancel-summary-ticket-count').textContent = `Total to Cancel: ${state.seatsSelectedForCancel.length}`;

    const refundPerTicket = Math.max(0, state.cancelMoviePrice - 40);
    const totalRefund = state.seatsSelectedForCancel.length * refundPerTicket;
    document.getElementById('cancel-summary-refund').textContent = `₹${totalRefund}`;

    // Enable/disable cancellation button
    const confirmBtn = document.getElementById('confirm-cancellation-btn');
    confirmBtn.disabled = state.seatsSelectedForCancel.length === 0;
}

function handleConfirmCancellation() {
    if (state.seatsSelectedForCancel.length === 0 || !state.cancelShowtimeId) return;

    const seatsStr = state.seatsSelectedForCancel.join(', ');
    const refundPerTicket = Math.max(0, state.cancelMoviePrice - 40);
    const totalRefund = state.seatsSelectedForCancel.length * refundPerTicket;

    showModal({
        type: 'danger',
        icon: 'fa-trash-can',
        title: 'Cancel Reservations?',
        subtitle: 'The selected seats will be cancelled and deleted.',
        details: [
            { label: 'Seats to Cancel', value: seatsStr },
            { label: 'Total Refund', value: `\u20B9${totalRefund} (after ₹40/ticket fee)`, highlight: true }
        ],
        confirmLabel: 'Confirm Cancellation',
        confirmIcon: 'fa-trash-can',
        onConfirm: async () => {
            try {
                // Cancel each selected seat in parallel
                const promises = state.seatsSelectedForCancel.map(seat =>
                    apiRequest(`/showtimes/${state.cancelShowtimeId}/cancel`, {
                        method: 'POST',
                        body: JSON.stringify({ seat_no: seat })
                    })
                );
                const results = await Promise.all(promises);

                let totalRefundVal = 0;
                let totalDeductionVal = 0;
                results.forEach(res => {
                    if (res && res.refund_amount !== undefined) {
                        totalRefundVal += res.refund_amount;
                    }
                    if (res && res.deduction !== undefined) {
                        totalDeductionVal += res.deduction;
                    }
                });

                showToast(`Cancelled successfully! Total refund of ₹${totalRefundVal} processed after ₹${totalDeductionVal} deduction.`, 'success');
                showView('bookings');
            } catch (err) {
                showToast('Cancellation failed: ' + err.message, 'error');
                startCancellation(state.cancelShowtimeId, state.userBookedSeatsForCancel);
            }
        }
    });
}

// -------------------------------------------------------------
// VIEW 4: ADMIN OPERATIONS VIEW
// -------------------------------------------------------------
async function loadAdminPanel() {
    const list = document.getElementById('admin-movies-list');
    list.innerHTML = '<p class="subtitle text-center">Loading database listings...</p>';

    try {
        const movies = await apiRequest('/movies');
        state.movies = movies;

        if (movies.length === 0) {
            list.innerHTML = '<p class="subtitle text-center" style="padding: 40px 0;">No active movies in DB.</p>';
            return;
        }

        list.innerHTML = '';
        movies.forEach(movie => {
            const row = document.createElement('div');
            row.className = 'admin-movie-row';
            row.innerHTML = `
                <div class="admin-movie-info">
                    <h4>${escapeHTML(movie.name)}</h4>
                    <p>ID: ${movie.id} | Genre: ${escapeHTML(movie.genre || 'N/A')} | Price: ₹${movie.price} | Screen: ${escapeHTML(movie.screen_no)}</p>
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteMovie('${movie.id}')">
                    <i class="fa-solid fa-trash-can"></i> Delete
                </button>
            `;
            list.appendChild(row);
        });
    } catch (err) {
        showToast('Error loading movies in admin panel: ' + err.message, 'error');
    }
}

async function handleNewMovieSubmit(e) {
    e.preventDefault();

    const idInput = document.getElementById('admin-movie-id').value.trim().toUpperCase();
    const titleInput = document.getElementById('admin-movie-title').value.trim();
    const genreInput = document.getElementById('admin-movie-genre').value.trim();
    const langInput = document.getElementById('admin-movie-lang').value.trim();
    const priceInput = parseInt(document.getElementById('admin-movie-price').value);
    const seatsInput = parseInt(document.getElementById('admin-movie-seats').value);
    const screenInput = document.getElementById('admin-movie-screen').value.trim();
    const imageInput = document.getElementById('admin-movie-image').value.trim() || null;
    const ratingInput = document.getElementById('admin-movie-rating').value || 'U';
    const timingsInput = document.getElementById('admin-movie-timings').value.trim() || null;

    try {
        await apiRequest('/movies', {
            method: 'POST',
            body: JSON.stringify({
                id: idInput,
                name: titleInput,
                genre: genreInput,
                language: langInput,
                price: priceInput,
                seats_available: seatsInput,
                screen_no: screenInput,
                image_url: imageInput,
                age_rating: ratingInput,
                show_timings: timingsInput
            })
        });

        showToast(`Successfully added movie '${titleInput}' to theater!`, 'success');

        // Reset Form Inputs
        document.getElementById('admin-movie-id').value = '';
        document.getElementById('admin-movie-title').value = '';
        document.getElementById('admin-movie-genre').value = '';
        document.getElementById('admin-movie-lang').value = '';
        document.getElementById('admin-movie-price').value = '';
        document.getElementById('admin-movie-seats').value = '';
        document.getElementById('admin-movie-screen').value = '';
        document.getElementById('admin-movie-image').value = '';
        document.getElementById('admin-movie-rating').value = '';
        document.getElementById('admin-movie-timings').value = '';

        loadAdminPanel();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function deleteMovie(movieId) {
    const movie = state.movies.find(m => m.id === movieId);
    const movieName = movie ? movie.name : 'this movie';

    showModal({
        type: 'danger',
        icon: 'fa-trash-can',
        title: 'Delete Movie?',
        subtitle: 'This will permanently remove the movie and ALL its bookings.',
        details: [
            { label: 'Movie', value: movieName },
            { label: 'ID', value: movieId }
        ],
        confirmLabel: 'Delete',
        confirmIcon: 'fa-trash-can',
        onConfirm: async () => {
            try {
                const result = await apiRequest(`/movies/${movieId}`, { method: 'DELETE' });
                showToast(result.message || `Movie ${movieName} deleted successfully.`, 'success');
                loadAdminPanel();
            } catch (err) {
                showToast('Deletion failed: ' + err.message, 'error');
            }
        }
    });
}

// -------------------------------------------------------------
// SYSTEM INITS & UTILS
// -------------------------------------------------------------
function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Global page load trigger
// NOTE: Do NOT call loadCatalog() here — the user must log in first.
// The catalog is loaded by onLoginSuccess() -> showView('catalog').
window.onload = () => {
    // Clear user session so it asks for login every time the link is opened
    localStorage.removeItem('currentUser');
    localStorage.removeItem('activeView');

    // Initialize Carousel
    showSlides(slideIndex);
    // Auto-advance carousel every 5 seconds
    setInterval(() => { changeSlide(1); }, 5000);
};

// -------------------------------------------------------------
// CAROUSEL LOGIC
// -------------------------------------------------------------
let slideIndex = 1;

function changeSlide(n) {
    showSlides(slideIndex += n);
}

function currentSlide(n) {
    showSlides(slideIndex = n);
}

function showSlides(n) {
    let i;
    const slides = document.getElementsByClassName("carousel-slide");
    const dots = document.getElementsByClassName("carousel-dot");

    if (!slides.length) return; // if not present

    if (n > slides.length) { slideIndex = 1 }
    if (n < 1) { slideIndex = slides.length }
    for (i = 0; i < slides.length; i++) {
        slides[i].classList.remove("active");
    }
    for (i = 0; i < dots.length; i++) {
        dots[i].classList.remove("active");
    }
    slides[slideIndex - 1].classList.add("active");
    if (dots.length >= slideIndex) {
        dots[slideIndex - 1].classList.add("active");
    }
}
