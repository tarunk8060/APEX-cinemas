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
        } else if (savedView === 'booking') {
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
    if (confirm('Are you sure you want to log out?')) {
        state.currentUser = null;
        localStorage.removeItem('currentUser');
        localStorage.removeItem('activeView');

        // Hide Main App & Reset Navs
        document.getElementById('app-layout').classList.add('hidden');
        document.getElementById('auth-overlay').classList.remove('hidden');

        // Reset login inputs
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
        state.selectedMovie = movie;
        state.selectedSeats = [];

        // Show Booking Page
        showView('booking');

        // Load Receipt Details
        document.getElementById('booking-movie-title').textContent = `Select Seats for ${movie.name}`;
        document.getElementById('summary-movie-name').textContent = movie.name;
        document.getElementById('summary-movie-lang').textContent = movie.language;
        document.getElementById('summary-movie-screen').textContent = movie.screen_no;
        document.getElementById('summary-movie-price').textContent = `₹${movie.price}`;

        updateReceiptDisplay();

        // Load Seats Map from API
        const seatData = await apiRequest(`/movies/${movieId}/seats`);
        state.bookedSeats = seatData.seats; // seat_no -> boolean (true: booked, false: available)

        // In order to distinguish who booked, fetch user_id mappings from all bookings
        const allBookings = await apiRequest('/bookings');
        const userSeatMappings = {}; // seat_no -> user_id
        allBookings.forEach(booking => {
            if (booking.movie_id === movieId) {
                userSeatMappings[booking.seat_no] = booking.user_id || 'Anonymous';
            }
        });

        // Map seat states: null for available, user_id for booked
        const seatStatesMap = {};
        for (const seatNo in state.bookedSeats) {
            const isBooked = state.bookedSeats[seatNo];
            seatStatesMap[seatNo] = isBooked ? (userSeatMappings[seatNo] || 'Anonymous') : null;
        }

        renderSeatGrid(movie.seats_available, seatStatesMap);
        renderRecommendations(movie.recommendations || []);
    } catch (err) {
        showToast('Error initializing seat selector: ' + err.message, 'error');
    }
}

function renderSeatGrid(totalSeats, seatStatesMap) {
    const gridContainer = document.getElementById('seat-layout-grid');
    gridContainer.innerHTML = '';

    // Rendering parameters
    const displaySeats = Math.min(totalSeats, 150);
    const cols = 10;
    const rowsCount = Math.ceil(displaySeats / cols);
    const rowLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

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

            // Handle Middle aisle space
            if (c === 5) {
                const spacer = document.createElement('div');
                spacer.className = 'seat-aisle-spacer';
                rowDiv.appendChild(spacer);
            }

            const seatBtn = document.createElement('button');
            seatBtn.className = 'seat';
            seatBtn.textContent = seatNum;

            // Check status
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

    const totalPrice = state.selectedSeats.length * state.selectedMovie.price;
    document.getElementById('summary-total-price').textContent = `₹${totalPrice}`;

    // Enable/disable confirm button
    const confirmBtn = document.getElementById('confirm-booking-btn');
    confirmBtn.disabled = state.selectedSeats.length === 0;
}

async function handleConfirmBooking() {
    if (state.selectedSeats.length === 0) return;

    const movie = state.selectedMovie;
    const seatsStr = state.selectedSeats.join(', ');
    const price = state.selectedSeats.length * movie.price;

    if (confirm(`Confirm Reservation?\n\nMovie: ${movie.name}\nSeats: ${seatsStr}\nTotal Price: ₹${price}`)) {
        try {
            await apiRequest(`/movies/${movie.id}/book`, {
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
            // Reload page to avoid conflict
            startBooking(movie.id);
        }
    }
}

function renderRecommendations(recs) {
    const list = document.getElementById('booking-recommendations');
    list.innerHTML = '';

    if (recs.length === 0) {
        list.innerHTML = '<p class="subtitle text-center" style="font-size:11px;">No similar movies found.</p>';
        return;
    }

    recs.forEach(rec => {
        const card = document.createElement('div');
        card.className = 'rec-card';

        // Find if movie exists in system to allow instant booking link
        const systemMovie = state.movies.find(m => m.name.toLowerCase() === rec.title.toLowerCase());

        card.innerHTML = `
            <div class="rec-info">
                <h5>${escapeHTML(rec.title)}</h5>
                <p>${escapeHTML(rec.genres)}</p>
            </div>
            ${systemMovie ? `<button class="btn btn-secondary btn-sm" onclick="startBooking('${systemMovie.id}')">Book Now</button>` : ''}
        `;
        list.appendChild(card);
    });
}

// -------------------------------------------------------------
// VIEW 3: MY BOOKINGS LIST VIEW
// -------------------------------------------------------------
async function loadBookings() {
    const listContainer = document.getElementById('bookings-list-container');
    listContainer.innerHTML = '<p class="subtitle text-center">Fetching reservations list...</p>';

    try {
        // Query filter by user id
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
        result.forEach(booking => {
            // Find movie detail in local state if available to extract metadata
            const movie = state.movies.find(m => m.id === booking.movie_id) || { name: 'Odyssey Feature', language: 'N/A', screen_no: 'N/A', price: 0 };

            const card = document.createElement('div');
            card.className = 'booking-row-card glass-card';
            card.innerHTML = `
                <div class="booking-indicator-bar"></div>
                <div class="booking-info-block">
                    <h4 class="booking-movie-header">${escapeHTML(movie.name)} (${escapeHTML(movie.language)})</h4>
                    <p class="booking-meta-details">
                        <i class="fa-solid fa-desktop"></i> Screen: ${escapeHTML(movie.screen_no)}  |  
                        <i class="fa-solid fa-chair"></i> Seat: ${escapeHTML(booking.seat_no)}  |  
                        <i class="fa-solid fa-indian-rupee-sign"></i> Price: ₹${movie.price}
                    </p>
                </div>
                <div class="booking-actions">
                    <button class="btn btn-danger btn-sm" onclick="cancelBooking('${booking.movie_id}', '${booking.seat_no}', ${movie.price})">
                        <i class="fa-solid fa-circle-xmark"></i> Cancel Booking
                    </button>
                </div>
            `;
            listContainer.appendChild(card);
        });
    } catch (err) {
        showToast('Error loading bookings: ' + err.message, 'error');
        listContainer.innerHTML = '<p class="subtitle text-center highlight">Failed to fetch bookings. Database connectivity error.</p>';
    }
}

async function cancelBooking(movieId, seatNo, refundAmt) {
    if (confirm(`Cancel Booking?\n\nAre you sure you want to cancel seat ${seatNo}?\nThis will issue a refund of ₹${refundAmt}.`)) {
        try {
            await apiRequest(`/movies/${movieId}/cancel`, {
                method: 'POST',
                body: JSON.stringify({ seat_no: seatNo })
            });

            showToast('Reservation cancelled. Refund has been initiated.', 'success');
            loadBookings();
        } catch (err) {
            showToast('Cancellation failed: ' + err.message, 'error');
        }
    }
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
                image_url: imageInput
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

        loadAdminPanel();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteMovie(movieId) {
    const movie = state.movies.find(m => m.id === movieId);
    const movieName = movie ? movie.name : 'this movie';

    if (confirm(`Delete Movie '${movieName}'?\n\nWARNING: This will permanently remove the movie and cancel all booked seats for it!`)) {
        try {
            const result = await apiRequest(`/movies/${movieId}`, {
                method: 'DELETE'
            });

            showToast(result.message || `Movie ${movieName} deleted successfully.`, 'success');
            loadAdminPanel();
        } catch (err) {
            showToast('Deletion failed: ' + err.message, 'error');
        }
    }
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
    // Restore user session if available
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
        try {
            state.currentUser = JSON.parse(savedUser);
            onLoginSuccess();
        } catch (e) {
            console.error('Failed to parse saved user session:', e);
            localStorage.removeItem('currentUser');
            localStorage.removeItem('activeView');
        }
    }
};
