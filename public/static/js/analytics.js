/*
 * Suivi du trafic Djona (anonyme, sans service externe).
 *   - une page vue à chaque chargement ;
 *   - un « heartbeat » toutes les 15 s tant que l'onglet est visible (visiteurs en ligne) ;
 *   - window.track('nom_action', {cle: 'valeur'}) pour une action métier ;
 *   - clics WhatsApp / téléphone et éléments [data-track="nom"] suivis automatiquement.
 * Aucune donnée personnelle : identifiant de session aléatoire (cookie djona_sid, 30 min glissantes),
 * chemin de la page, nom d'action. Les numéros de téléphone et les contenus de formulaires ne sont jamais envoyés.
 */
(function () {
    var script = document.currentScript;
    if (!script || window.djonaAnalytics) { return; }
    var key = script.getAttribute('data-site-key');
    var endpoint = script.getAttribute('data-endpoint');
    if (!key || !endpoint) { return; }
    window.djonaAnalytics = true;

    var COOKIE = 'djona_sid';
    var COOKIE_TTL = 30 * 60;      // secondes, renouvelé à chaque envoi
    var HEARTBEAT_MS = 15000;

    function readCookie() {
        var match = document.cookie.match(new RegExp('(?:^|; )' + COOKIE + '=([A-Za-z0-9_-]{8,40})'));
        return match ? match[1] : '';
    }

    function randomId() {
        var bytes = new Uint8Array(16);
        if (window.crypto && window.crypto.getRandomValues) {
            window.crypto.getRandomValues(bytes);
        } else {
            for (var i = 0; i < bytes.length; i++) { bytes[i] = Math.floor(Math.random() * 256); }
        }
        var id = '';
        for (var j = 0; j < bytes.length; j++) { id += (bytes[j] + 256).toString(16).slice(1); }
        return id;
    }

    function sessionId() {
        var id = readCookie() || randomId();
        document.cookie = COOKIE + '=' + id + '; path=/; max-age=' + COOKIE_TTL + '; SameSite=Lax' +
            (location.protocol === 'https:' ? '; Secure' : '');
        return id;
    }

    function send(type, name, meta) {
        var body = { k: key, sid: sessionId(), t: type, p: location.pathname };
        if (name) { body.n = name; }
        if (meta) { body.m = meta; }
        if (type === 'pageview' && document.referrer) { body.r = document.referrer; }
        var payload = JSON.stringify(body);
        try {
            // text/plain : pas de requête de pré-vérification (CORS), le serveur lit le JSON tel quel.
            if (navigator.sendBeacon && navigator.sendBeacon(endpoint, new Blob([payload], { type: 'text/plain' }))) { return; }
        } catch (e) { /* repli sur fetch */ }
        try {
            fetch(endpoint, { method: 'POST', body: payload, headers: { 'Content-Type': 'text/plain' }, keepalive: true, credentials: 'same-origin' })
                .catch(function () {});
        } catch (e) { /* le suivi ne doit jamais gêner la page */ }
    }

    window.track = function (name, meta) {
        if (typeof name === 'string' && name) { send('action', name, meta); }
    };

    send('pageview');

    setInterval(function () {
        if (document.visibilityState === 'visible') { send('heartbeat'); }
    }, HEARTBEAT_MS);
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible') { send('heartbeat'); }
    });

    document.addEventListener('click', function (event) {
        var target = event.target;
        if (!target || !target.closest) { return; }
        var tagged = target.closest('[data-track]');
        if (tagged) { window.track(tagged.getAttribute('data-track')); return; }
        var link = target.closest('a[href]');
        if (!link) { return; }
        var href = link.getAttribute('href') || '';
        if (/^https?:\/\/(wa\.me|api\.whatsapp\.com)\//i.test(href)) {
            window.track('clic_whatsapp');
        } else if (/^tel:/i.test(href)) {
            window.track('clic_telephone');
        }
    }, true);
})();
