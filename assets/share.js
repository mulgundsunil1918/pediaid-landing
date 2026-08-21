/* ===========================================================================
 * share.js — "Share with a colleague" for every landing page.
 *
 * Three tiers, best available wins:
 *   1. navigator.share()  — the real OS share sheet. Phones and Safari.
 *   2. WhatsApp deep link — how this audience actually forwards things, and
 *      the only fallback that keeps the full message rather than just a URL.
 *   3. Clipboard          — last resort, with visible confirmation.
 *
 * The message is loaded from assets/share-message.json, which is generated
 * from the Flutter app's lib/utils/share_message.dart. There is deliberately
 * no second copy of the text here: the web share and the in-app share must
 * never make different claims about what the app contains.
 * ======================================================================== */
(function () {
  'use strict';

  var FALLBACK = {
    subject: 'PediAid — paediatric & neonatal clinical reference',
    message: 'PediAid — paediatric & neonatal clinical reference. Calculators, ' +
             'clinical scores, growth charts, drug formulary and immunisation ' +
             'catch-up. Free on iOS, Android and web.\n\n' +
             'https://info.pediaid.bridgr.co.in',
    url: 'https://info.pediaid.bridgr.co.in'
  };

  var payload = null;

  /* Resolve the JSON relative to this script, not to the page: tool pages sit
     two directories deep and hub pages one, so a fixed path breaks on all but
     the homepage. */
  function jsonUrl() {
    var s = document.currentScript;
    if (!s) {
      var all = document.getElementsByTagName('script');
      for (var i = all.length - 1; i >= 0; i--) {
        if (all[i].src && all[i].src.indexOf('share.js') !== -1) { s = all[i]; break; }
      }
    }
    return s ? s.src.replace(/share\.js(\?.*)?$/, 'share-message.json') : null;
  }

  function load() {
    if (payload) return Promise.resolve(payload);
    var u = jsonUrl();
    if (!u || !window.fetch) return Promise.resolve(FALLBACK);
    return fetch(u)
      .then(function (r) { return r.ok ? r.json() : FALLBACK; })
      .then(function (d) { payload = d && d.message ? d : FALLBACK; return payload; })
      .catch(function () { return FALLBACK; });
  }

  function toast(text) {
    var el = document.createElement('div');
    el.className = 'pediaid-share-toast';
    el.setAttribute('role', 'status');
    el.textContent = text;
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('is-in'); });
    setTimeout(function () {
      el.classList.remove('is-in');
      setTimeout(function () { el.remove(); }, 320);
    }, 2600);
  }

  function whatsapp(text) {
    window.open('https://wa.me/?text=' + encodeURIComponent(text),
                '_blank', 'noopener');
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:-1000px;opacity:0;';
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove();
      ok ? resolve() : reject();
    });
  }

  function share(btn) {
    load().then(function (d) {
      /* navigator.share exists in some desktop browsers but throws
         NotAllowedError with no share targets, so failure falls through to
         WhatsApp rather than leaving the button looking broken. */
      if (navigator.share) {
        navigator.share({ title: d.subject, text: d.message, url: d.url })
          .catch(function (err) {
            if (err && err.name === 'AbortError') return;  // user dismissed
            whatsapp(d.message);
          });
        return;
      }
      if (btn && btn.dataset.shareMode === 'copy') {
        copy(d.message)
          .then(function () { toast('Message copied — paste it anywhere'); })
          .catch(function () { whatsapp(d.message); });
        return;
      }
      whatsapp(d.message);
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-pediaid-share]') : null;
    if (!btn) return;
    e.preventDefault();
    share(btn);
  });

  /* Warm the JSON on idle so the first tap opens the sheet immediately
     instead of waiting on a network round trip. */
  if (window.requestIdleCallback) { requestIdleCallback(function () { load(); }); }
  else { setTimeout(load, 1200); }
})();
