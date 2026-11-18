/*
 * Page « Temps réel » du back-office : interroge /temps-reel/stats/ et /temps-reel/evenements/ toutes les 5 s.
 * Tout le contenu venant des visiteurs (chemins, noms d'action) est inséré avec textContent : jamais en HTML.
 */
(function () {
    var root = document.querySelector('[data-live]');
    if (!root) { return; }
    var site = root.dataset.site;
    var urlStats = root.dataset.urlStats + '?site=' + encodeURIComponent(site);
    var urlEvents = root.dataset.urlEvents;
    var POLL_MS = 5000;
    var lastId = 0;
    var failures = 0;
    var timer = null;
    var inFlight = false;
    var firstEvents = true;

    function q(sel) { return root.querySelector(sel); }
    function qa(sel) { return root.querySelectorAll(sel); }
    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) { node.className = cls; }
        if (text !== undefined) { node.textContent = text; }
        return node;
    }
    function fmt(n) { return typeof n === 'number' ? n.toLocaleString('fr-FR') : '—'; }
    function plural(n, word) { return fmt(n) + ' ' + word + (n > 1 ? 's' : ''); }
    function setKpi(name, value) { qa('[data-kpi="' + name + '"]').forEach(function (n) { n.textContent = value; }); }

    function setStatus(ok, text) {
        q('[data-live-status]').textContent = text;
        var dot = q('[data-live-dot]');
        dot.classList.toggle('bg-[#1a7f37]', ok);
        dot.classList.toggle('live-dot', ok);
        dot.classList.toggle('bg-outline', !ok);
        q('[data-live-unavailable]').classList.toggle('hidden', ok || failures < 2);
    }

    // --- Graphique : barres fines, base alignée, extrémité arrondie, infobulle au survol ------------------
    function renderChart(points) {
        var chart = q('[data-chart]');
        var tooltip = q('[data-tooltip]');
        var max = Math.max.apply(null, points.map(function (p) { return p.count; }).concat([1]));
        var niceMax = max <= 4 ? 4 : Math.ceil(max / 4) * 4;
        q('[data-axis="max"]').textContent = fmt(niceMax);
        q('[data-axis="mid"]').textContent = fmt(niceMax / 2);
        q('[data-chart-start]').textContent = points.length ? points[0].minute : '';
        q('[data-chart-end]').textContent = points.length ? points[points.length - 1].minute : '';
        chart.textContent = '';
        points.forEach(function (point) {
            var col = el('div', 'bar-col relative flex-1 h-full flex items-end cursor-default');
            col.tabIndex = 0;
            var bar = el('div', 'bar w-full bg-primary rounded-t-[4px]');
            bar.style.height = point.count ? Math.max(point.count / niceMax * 100, 2) + '%' : '0';
            col.appendChild(bar);
            function show() {
                tooltip.textContent = point.minute + ' · ' + plural(point.count, 'page') + ' vue' + (point.count > 1 ? 's' : '');
                tooltip.classList.remove('hidden');
                var box = chart.getBoundingClientRect();
                var c = col.getBoundingClientRect();
                tooltip.style.left = (c.left - box.left + c.width / 2) + 'px';
                tooltip.style.top = (box.height - 20 - bar.offsetHeight - 6) + 'px';
            }
            function hide() { tooltip.classList.add('hidden'); }
            col.addEventListener('mouseenter', show);
            col.addEventListener('mouseleave', hide);
            col.addEventListener('focus', show);
            col.addEventListener('blur', hide);
            chart.appendChild(col);
        });
        var body = q('[data-chart-table]');
        body.textContent = '';
        points.slice().reverse().forEach(function (point) {
            var row = el('tr');
            row.appendChild(el('td', 'py-1 pr-4 text-on-surface-variant', point.minute));
            row.appendChild(el('td', 'py-1 font-medium', fmt(point.count)));
            body.appendChild(row);
        });
    }

    // --- Listes à barres horizontales (une seule teinte ; le libellé porte l'identité) --------------------
    function renderBars(name, rows, labelOf, mono) {
        var list = q('[data-list="' + name + '"]');
        list.textContent = '';
        if (!rows.length) {
            list.appendChild(el('li', 'text-sm text-on-surface-variant', "Aucune donnée aujourd'hui."));
            return;
        }
        var max = Math.max.apply(null, rows.map(function (r) { return r.count; }));
        rows.forEach(function (row) {
            var item = el('li', 'flex flex-col gap-1');
            var head = el('div', 'flex items-baseline justify-between gap-3 text-sm');
            head.appendChild(el('span', 'truncate' + (mono ? ' font-mono text-[13px]' : ''), labelOf(row)));
            head.appendChild(el('span', 'font-semibold tabular-nums', fmt(row.count)));
            var track = el('div', 'h-1.5 rounded-full bg-surface-container');
            var fill = el('div', 'h-full rounded-full bg-primary');
            fill.style.width = Math.max(row.count / max * 100, 3) + '%';
            track.appendChild(fill);
            item.appendChild(head);
            item.appendChild(track);
            list.appendChild(item);
        });
    }

    function renderStats(data) {
        setKpi('online', fmt(data.online));
        setKpi('pageviews_today', fmt(data.pageviews_today));
        setKpi('visitors_today', fmt(data.visitors_today));
        setKpi('actions_today', fmt(data.actions_today));
        var h = data.health;
        var rate5 = h.total ? '(' + h.rate_5xx + ' %)' : '';
        setKpi('errors_5xx', fmt(h.errors_5xx));
        setKpi('errors_5xx_b', fmt(h.errors_5xx));
        setKpi('rate_5xx', rate5);
        setKpi('rate_5xx_b', rate5);
        setKpi('errors_4xx', fmt(h.errors_4xx));
        setKpi('rate_4xx', h.total ? '(' + h.rate_4xx + ' %)' : '');
        setKpi('requests', fmt(h.total));
        setKpi('avg_ms', fmt(h.avg_ms));
        setKpi('p95_ms', fmt(h.p95_ms));
        // État : icône + texte, jamais la couleur seule.
        var bad = h.errors_5xx > 0;
        q('[data-health-icon]').textContent = bad ? 'warning' : 'check_circle';
        q('[data-health-icon-wrap]').className = 'w-10 h-10 rounded-xl flex items-center justify-center ' + (bad ? 'bg-error-container' : 'bg-primary/10');
        q('[data-health-icon]').className = 'material-symbols-outlined text-[22px] ' + (bad ? 'text-error' : 'text-primary');
        renderChart(data.chart);
        renderBars('actions', data.actions, function (r) { return r.label; });
        renderBars('top_pages', data.top_pages, function (r) { return r.path || '/'; }, true);
        renderBars('devices', data.devices, function (r) { return r.name; });
        renderBars('countries', data.countries, function (r) { return r.name; });
        q('[data-countries-card]').classList.toggle('hidden', !data.countries.length);
    }

    // --- Flux d'événements -----------------------------------------------------------------------------------
    var KIND = {
        action: { icon: 'bolt', cls: 'text-secondary', bg: 'bg-secondary-container/20' },
        pageview: { icon: 'visibility', cls: 'text-primary', bg: 'bg-primary/10' },
        error4xx: { icon: 'report', cls: 'text-on-surface-variant', bg: 'bg-surface-container' },
        error5xx: { icon: 'error', cls: 'text-error', bg: 'bg-error-container' }
    };

    function renderEvents(events, initial) {
        var feed = q('[data-feed]');
        if (!events.length) { return; }
        q('[data-feed-empty]').classList.add('hidden');
        // `events` arrive du plus récent au plus ancien : on insère du plus ancien au plus récent, en tête de liste.
        events.slice().reverse().forEach(function (event) {
            if (event.id <= lastId) { return; }   // déjà affiché (deux réponses qui se croisent)
            lastId = event.id;
            var kind = KIND[event.kind] || KIND.pageview;
            var item = el('li', 'flex items-start gap-3 py-2.5' + (initial ? '' : ' feed-new'));
            var icon = el('span', 'w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ' + kind.bg);
            icon.appendChild(el('span', 'material-symbols-outlined text-[18px] ' + kind.cls, kind.icon));
            var text = el('div', 'min-w-0 flex-1');
            text.appendChild(el('p', 'text-sm font-medium truncate', event.label));
            text.appendChild(el('p', 'text-xs text-on-surface-variant truncate', [event.path, event.detail, event.device].filter(Boolean).join(' · ')));
            item.appendChild(icon);
            item.appendChild(text);
            item.appendChild(el('span', 'text-xs text-on-surface-variant tabular-nums shrink-0', event.time));
            feed.insertBefore(item, feed.firstChild);
        });
        while (feed.children.length > 60) { feed.removeChild(feed.lastChild); }
    }

    function getJson(url) {
        return fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); });
    }

    function schedule() {
        clearTimeout(timer);
        timer = setTimeout(tick, POLL_MS);
    }

    function tick() {
        clearTimeout(timer);
        if (document.hidden) { return schedule(); }
        if (inFlight) { return; }
        inFlight = true;
        Promise.all([
            getJson(urlStats),
            getJson(urlEvents + '?site=' + encodeURIComponent(site) + '&since=' + lastId)
        ]).then(function (res) {
            failures = 0;
            renderStats(res[0]);
            renderEvents(res[1].events, firstEvents);
            firstEvents = false;
            setStatus(true, 'En direct · mis à jour à ' + res[0].generated_at);
        }).catch(function () {
            failures += 1;
            setStatus(false, 'Données indisponibles — nouvelle tentative…');
        }).then(function () { inFlight = false; schedule(); });
    }

    document.addEventListener('visibilitychange', function () { if (!document.hidden) { tick(); } });
    tick();
})();
