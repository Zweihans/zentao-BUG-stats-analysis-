/**
 * 禅道 BUG 分析工具 — GSAP 动画模块
 *
 * 设计原则（办公软件）：
 * - 时长 150-250ms，快速流畅
 * - power2.out / power3.out 缓动，无弹性
 * - 交错入场 0.03-0.05s，克制不拖沓
 * - 尊重 prefers-reduced-motion
 */

var Anim = (function() {
  var REDUCED = false;
  try {
    var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    REDUCED = mq.matches;
    mq.addEventListener('change', function() { REDUCED = mq.matches; });
  } catch(e) {}

  function dur(ms) { return REDUCED ? 0 : ms / 1000; }
  function ease() { return REDUCED ? 'none' : 'power2.out'; }

  // 页面切换 — 旧页淡出 + 新页内容交错过渡
  function pageIn(containerSelector) {
    var el = typeof containerSelector === 'string' ? document.querySelector(containerSelector) : containerSelector;
    if (!el) return;
    // 直接可见的子元素（卡片、区块），交错淡入上移
    var items = el.querySelectorAll(':scope > .card, :scope > .section-group, :scope > .topbar, :scope > .page-title, :scope > .controls-row, :scope > .stats-cards > div');
    if (!items.length) {
      gsap.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: dur(200), ease: ease() });
      return;
    }
    gsap.set(items, { autoAlpha: 0, y: 6 });
    gsap.to(items, {
      autoAlpha: 1, y: 0,
      duration: dur(220), ease: ease(),
      stagger: REDUCED ? 0 : 0.04
    });
  }

  // 弹窗打开
  function modalOpen(modalSelector) {
    var modal = typeof modalSelector === 'string' ? document.querySelector(modalSelector) : modalSelector;
    if (!modal) return;
    var card = modal.querySelector('.modal-card') || modal.querySelector('.card') || modal.firstElementChild;
    var overlay = modal;
    modal.style.display = 'flex';
    gsap.set(overlay, { autoAlpha: 0 });
    if (card) {
      gsap.set(card, { autoAlpha: 0, scale: 0.97, y: 8 });
      gsap.to(overlay, { autoAlpha: 1, duration: dur(160), ease: ease() });
      gsap.to(card, { autoAlpha: 1, scale: 1, y: 0, duration: dur(220), ease: ease(), delay: dur(40) });
    } else {
      gsap.to(overlay, { autoAlpha: 1, duration: dur(200), ease: ease() });
    }
  }

  // 弹窗关闭
  function modalClose(modalSelector, onComplete) {
    var modal = typeof modalSelector === 'string' ? document.querySelector(modalSelector) : modalSelector;
    if (!modal) { if (onComplete) onComplete(); return; }
    var card = modal.querySelector('.modal-card') || modal.querySelector('.card');
    var targets = card ? [modal, card] : [modal];
    gsap.to(targets, {
      autoAlpha: 0, scale: card ? 0.98 : 1,
      duration: dur(150), ease: 'power2.in',
      onComplete: function() {
        modal.style.display = 'none';
        if (onComplete) onComplete();
      }
    });
  }

  // 横幅展开
  function bannerShow(el) {
    if (!el || el.style.display === 'flex') return;
    el.style.display = 'flex';
    el.style.overflow = 'hidden';
    gsap.fromTo(el, { height: 0, autoAlpha: 0 }, { height: 'auto', autoAlpha: 1, duration: dur(200), ease: ease(), onComplete: function() { el.style.overflow = ''; } });
  }

  // 横幅收起
  function bannerHide(el) {
    if (!el || el.style.display === 'none') return;
    el.style.overflow = 'hidden';
    gsap.to(el, {
      height: 0, autoAlpha: 0,
      duration: dur(150), ease: 'power2.in',
      onComplete: function() {
        el.style.display = 'none';
        el.style.height = '';
        el.style.overflow = '';
      }
    });
  }

  // 列表行交错入场
  function staggerIn(containerSelector, itemSelector) {
    var container = typeof containerSelector === 'string' ? document.querySelector(containerSelector) : containerSelector;
    if (!container) return;
    var items = container.querySelectorAll(itemSelector);
    if (!items.length) return;
    gsap.set(items, { autoAlpha: 0, y: 4 });
    gsap.to(items, {
      autoAlpha: 1, y: 0,
      duration: dur(180),
      ease: ease(),
      stagger: REDUCED ? 0 : 0.03
    });
  }

  // 按钮按压微反馈
  function buttonPress(el) {
    if (!el || REDUCED) return;
    gsap.timeline()
      .to(el, { scale: 0.96, duration: 0.06, ease: 'power2.in' })
      .to(el, { scale: 1, duration: 0.12, ease: 'power2.out' });
  }

  // 通用淡入（简单场景）
  function fadeIn(el, d) {
    if (!el) return;
    gsap.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: dur(d || 200), ease: ease() });
  }

  return {
    reduced: function() { return REDUCED; },
    pageIn: pageIn,
    modalOpen: modalOpen,
    modalClose: modalClose,
    bannerShow: bannerShow,
    bannerHide: bannerHide,
    staggerIn: staggerIn,
    buttonPress: buttonPress,
    fadeIn: fadeIn,
  };
})();
