(function () {
  'use strict';

  var MIN_ZOOM = 1;
  var MAX_ZOOM = 5;
  var ZOOM_STEP = 0.25;

  function createLightbox() {
    var root = document.createElement('div');
    root.className = 'image-lightbox';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-label', 'Aperçu de l’image');
    root.innerHTML =
      '<button type="button" class="image-lightbox__close" aria-label="Fermer">&times;</button>' +
      '<div class="image-lightbox__hint">Molette pour zoomer · Glisser pour déplacer · Échap pour fermer</div>' +
      '<div class="image-lightbox__stage">' +
      '  <img class="image-lightbox__img" alt="">' +
      '</div>' +
      '<div class="image-lightbox__toolbar">' +
      '  <button type="button" class="image-lightbox__btn" data-lb-action="out" aria-label="Zoom arrière">−</button>' +
      '  <span class="image-lightbox__zoom-label">100%</span>' +
      '  <button type="button" class="image-lightbox__btn" data-lb-action="in" aria-label="Zoom avant">+</button>' +
      '  <button type="button" class="image-lightbox__btn" data-lb-action="reset" aria-label="Réinitialiser">1:1</button>' +
      '</div>';
    document.body.appendChild(root);
    return root;
  }

  var root = null;
  var stage = null;
  var img = null;
  var zoomLabel = null;
  var scale = 1;
  var offsetX = 0;
  var offsetY = 0;
  var dragging = false;
  var lastX = 0;
  var lastY = 0;
  var baseWidth = 0;
  var baseHeight = 0;

  function ensure() {
    if (root) return;
    root = createLightbox();
    stage = root.querySelector('.image-lightbox__stage');
    img = root.querySelector('.image-lightbox__img');
    zoomLabel = root.querySelector('.image-lightbox__zoom-label');

    root.querySelector('.image-lightbox__close').addEventListener('click', close);
    root.addEventListener('click', function (e) {
      if (e.target === root) close();
    });

    root.querySelectorAll('[data-lb-action]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var action = btn.getAttribute('data-lb-action');
        if (action === 'in') setZoom(scale + ZOOM_STEP);
        if (action === 'out') setZoom(scale - ZOOM_STEP);
        if (action === 'reset') resetView();
      });
    });

    stage.addEventListener('wheel', function (e) {
      e.preventDefault();
      var delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
      setZoom(scale + delta);
    }, { passive: false });

    stage.addEventListener('pointerdown', function (e) {
      if (scale <= 1) return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      stage.classList.add('is-dragging');
      stage.setPointerCapture(e.pointerId);
    });

    stage.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      offsetX += e.clientX - lastX;
      offsetY += e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      applyTransform();
    });

    function endDrag(e) {
      if (!dragging) return;
      dragging = false;
      stage.classList.remove('is-dragging');
      try {
        stage.releasePointerCapture(e.pointerId);
      } catch (err) { /* ignore */ }
    }

    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);

    document.addEventListener('keydown', function (e) {
      if (!root.classList.contains('is-open')) return;
      if (e.key === 'Escape') close();
      if (e.key === '+' || e.key === '=') setZoom(scale + ZOOM_STEP);
      if (e.key === '-') setZoom(scale - ZOOM_STEP);
      if (e.key === '0') resetView();
    });
  }

  function fitBaseSize() {
    var sw = stage.clientWidth;
    var sh = stage.clientHeight;
    var nw = img.naturalWidth || sw;
    var nh = img.naturalHeight || sh;
    var ratio = Math.min(sw / nw, sh / nh, 1);
    baseWidth = Math.max(1, nw * ratio);
    baseHeight = Math.max(1, nh * ratio);
    img.style.width = baseWidth + 'px';
    img.style.height = baseHeight + 'px';
  }

  function applyTransform() {
    img.style.transform =
      'translate(calc(-50% + ' + offsetX + 'px), calc(-50% + ' + offsetY + 'px)) scale(' + scale + ')';
    zoomLabel.textContent = Math.round(scale * 100) + '%';
  }

  function setZoom(next) {
    scale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(next * 100) / 100));
    if (scale <= 1) {
      offsetX = 0;
      offsetY = 0;
    }
    applyTransform();
  }

  function resetView() {
    scale = 1;
    offsetX = 0;
    offsetY = 0;
    applyTransform();
  }

  function open(src, alt) {
    if (!src) return;
    ensure();
    img.onload = function () {
      fitBaseSize();
      resetView();
    };
    img.alt = alt || 'Image du projet';
    img.src = src;
    root.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    if (img.complete && img.naturalWidth) {
      fitBaseSize();
      resetView();
    }
  }

  function close() {
    if (!root) return;
    root.classList.remove('is-open');
    document.body.style.overflow = '';
    dragging = false;
  }

  function resolveSrc(el) {
    return (
      el.getAttribute('data-lightbox-src') ||
      el.getAttribute('data-full-src') ||
      (el.tagName === 'IMG' ? el.currentSrc || el.src : '') ||
      (el.querySelector && el.querySelector('img')
        ? (el.querySelector('img').currentSrc || el.querySelector('img').src)
        : '')
    );
  }

  function resolveAlt(el) {
    if (el.tagName === 'IMG') return el.alt || '';
    var nested = el.querySelector && el.querySelector('img');
    return (nested && nested.alt) || el.getAttribute('aria-label') || '';
  }

  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('[data-lightbox]');
    if (!trigger) return;
    var src = resolveSrc(trigger);
    if (!src) return;
    e.preventDefault();
    e.stopPropagation();
    open(src, resolveAlt(trigger));
  });

  window.MwindaLightbox = { open: open, close: close };
})();
