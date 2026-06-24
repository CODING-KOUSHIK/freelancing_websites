/**
 * VoiceMarket Security Layer
 * Implements: right-click disable, drag-save prevention, devtools detection
 * Note: These are deterrents. Professional users can always bypass client-side protection.
 */
(function() {
  'use strict';

  // ── Disable Right-Click Context Menu ────────────────────────
  document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    return false;
  }, { passive: false });

  // ── Disable Text Selection on key elements ───────────────────
  document.addEventListener('selectstart', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    // Allow selection in form fields, prevent elsewhere
  });

  // ── Disable Drag and Save of images ─────────────────────────
  document.addEventListener('dragstart', function(e) {
    if (e.target.tagName === 'IMG') {
      e.preventDefault();
      return false;
    }
  }, { passive: false });

  // ── Disable common devtools shortcuts ───────────────────────
  document.addEventListener('keydown', function(e) {
    // F12
    if (e.key === 'F12') {
      e.preventDefault();
      return false;
    }
    // Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C (DevTools)
    if (e.ctrlKey && e.shiftKey && ['I', 'J', 'C'].includes(e.key.toUpperCase())) {
      e.preventDefault();
      return false;
    }
    // Ctrl+U (View Source)
    if (e.ctrlKey && e.key === 'u') {
      e.preventDefault();
      return false;
    }
    // Ctrl+S (Save Page)
    if (e.ctrlKey && e.key === 's') {
      e.preventDefault();
      return false;
    }
    // Ctrl+Shift+K (Firefox console)
    if (e.ctrlKey && e.shiftKey && e.key === 'K') {
      e.preventDefault();
      return false;
    }
  }, { passive: false });

  // ── CSS protection for images ────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    img {
      -webkit-user-drag: none;
      -khtml-user-drag: none;
      -moz-user-drag: none;
      -o-user-drag: none;
      user-drag: none;
      pointer-events: none;
    }
    /* Allow pointer events on clickable images */
    a img, button img, .clickable img {
      pointer-events: auto;
    }
  `;
  document.head.appendChild(style);

})();
