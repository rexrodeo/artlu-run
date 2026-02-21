/**
 * ARTLU.RUN — Client-side JavaScript
 * ====================================
 * Handles: mini elevation charts, race filtering/search,
 * race request form, form validation, smooth scroll.
 */

document.addEventListener('DOMContentLoaded', function () {

    // =================================================================
    // MINI ELEVATION PROFILES (on race cards)
    // =================================================================
    document.querySelectorAll('.mini-elevation').forEach(function (el) {
        var raw = el.dataset.profile;
        if (!raw) return;
        try {
            var data = JSON.parse(raw);
        } catch (e) { return; }
        if (!data.length) return;

        var canvas = document.createElement('canvas');
        el.appendChild(canvas);
        var ctx = canvas.getContext('2d');
        var dpr = window.devicePixelRatio || 1;
        var w = el.offsetWidth;
        var h = el.offsetHeight || 40;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        ctx.scale(dpr, dpr);

        var min = Math.min.apply(null, data);
        var max = Math.max.apply(null, data);
        var range = max - min || 1;

        // Fill
        var grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, 'rgba(231,76,60,0.25)');
        grad.addColorStop(1, 'rgba(231,76,60,0.02)');
        ctx.beginPath();
        ctx.moveTo(0, h);
        for (var i = 0; i < data.length; i++) {
            var x = (i / (data.length - 1)) * w;
            var y = h - ((data[i] - min) / range) * (h * 0.85);
            ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        // Line
        ctx.beginPath();
        for (var i = 0; i < data.length; i++) {
            var x = (i / (data.length - 1)) * w;
            var y = h - ((data[i] - min) / range) * (h * 0.85);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.strokeStyle = '#e74c3c';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    });

    // =================================================================
    // RACE BROWSER — Search & Filter
    // =================================================================
    var searchInput = document.getElementById('race-search');
    var raceGrid = document.getElementById('race-grid');
    var filterPills = document.querySelectorAll('.pill[data-filter]');

    var currentFilter = 'all';

    function filterRaces() {
        if (!raceGrid) return;
        var query = (searchInput ? searchInput.value : '').toLowerCase();
        var cards = raceGrid.querySelectorAll('.race-card');

        cards.forEach(function (card) {
            var name = (card.dataset.name || '').toLowerCase();
            var distance = parseFloat(card.dataset.distance) || 0;
            var country = (card.dataset.country || '').toLowerCase();
            var matchesSearch = !query || name.indexOf(query) !== -1;

            var matchesFilter = true;
            if (currentFilter === '100') matchesFilter = distance >= 100;
            else if (currentFilter === '50') matchesFilter = distance >= 40 && distance < 100;
            else if (currentFilter === 'usa') matchesFilter = country === 'usa';
            else if (currentFilter === 'international') matchesFilter = country !== 'usa';

            card.style.display = (matchesSearch && matchesFilter) ? '' : 'none';
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterRaces);
    }

    filterPills.forEach(function (pill) {
        pill.addEventListener('click', function () {
            filterPills.forEach(function (p) { p.classList.remove('pill-active'); });
            pill.classList.add('pill-active');
            currentFilter = pill.dataset.filter;
            filterRaces();
        });
    });

    // =================================================================
    // RACE REQUEST FORM (AJAX)
    // =================================================================
    var requestForm = document.getElementById('race-request-form');
    if (requestForm) {
        requestForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var formData = new FormData(requestForm);
            var msgEl = document.getElementById('request-message');

            fetch('/request-race', {
                method: 'POST',
                body: formData
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    msgEl.textContent = data.message;
                    msgEl.className = 'form-message success';
                    requestForm.reset();
                } else {
                    msgEl.textContent = data.error || 'Something went wrong.';
                    msgEl.className = 'form-message error';
                }
            })
            .catch(function () {
                msgEl.textContent = 'Network error. Please try again.';
                msgEl.className = 'form-message error';
            });
        });
    }

    // =================================================================
    // SMOOTH SCROLL for anchor links
    // =================================================================
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            var target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // =================================================================
    // AUTO-UPPERCASE access code inputs
    // =================================================================
    var codeInput = document.getElementById('access_code');
    if (codeInput) {
        codeInput.addEventListener('input', function () {
            this.value = this.value.toUpperCase();
        });
    }

    // =================================================================
    // AUTO-DISMISS flash messages
    // =================================================================
    document.querySelectorAll('.flash').forEach(function (flash) {
        setTimeout(function () {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            flash.style.transition = 'all 0.3s';
            setTimeout(function () { flash.remove(); }, 300);
        }, 5000);
    });

    // =================================================================
    // PREMIUM CONTENT UNLOCK (race page)
    // =================================================================
    var raceSlug = document.body.dataset.raceSlug;
    if (raceSlug) {
        // Check if user is logged in and has premium access
        fetch('/api/my-premium/' + raceSlug)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.unlocked) {
                    revealPremiumContent(data.data);
                }
            })
            .catch(function (err) {
                // Silently fail; premium content stays locked
            });
    }

    function revealPremiumContent(premiumData) {
        var teasers = document.querySelectorAll('.premium-teaser');
        teasers.forEach(function (teaser) {
            teaser.classList.add('premium-unlocked');
            var overlay = teaser.querySelector('.premium-overlay');
            if (overlay) overlay.style.display = 'none';
            var blur = teaser.querySelector('.premium-blur');
            if (blur) blur.style.filter = 'none';
        });
    }

});
