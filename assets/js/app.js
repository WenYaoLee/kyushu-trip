import { initExpenseView } from './expense.js';

const VIEWS = [
  ['home-view', 'views/home.html', 'home'],
  ['itinerary-view', 'views/itinerary.html', 'itinerary'],
  ['checklist-view', 'views/checklist.html', 'checklist'],
  ['concierge-view', 'views/concierge.html', 'guide'],
  ['rental-view', 'views/rental.html', 'rental'],
  ['lodging-view', 'views/lodging.html', 'lodging'],
  ['necessary-cost-view', 'views/necessary-cost.html', 'cost'],
  ['expense-view', 'views/expense.html', 'expense'],
  ['map-view', 'views/maps.html', 'maps'],
  ['tools-view', 'views/tools.html', 'tools'],
];

const VIEW_IDS = VIEWS.map(([id]) => id);
const HASH_TO_VIEW = Object.fromEntries(VIEWS.map(([id,, hash]) => [hash, id]));
const VIEW_TO_HASH = Object.fromEntries(VIEWS.map(([id,, hash]) => [id, hash]));

async function loadViews() {
  const root = document.getElementById('viewsRoot');
  if (!root) return;
  const htmlParts = await Promise.all(
    VIEWS.map(async ([, path]) => {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`載入失敗：${path}`);
      return await res.text();
    })
  );
  root.innerHTML = htmlParts.join('\n');
}

function renderTicNoteMetaDate() {
  const dateEl = document.getElementById('r-date');
  if (!dateEl) return;
  dateEl.textContent = new Date().toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric'
  });
}

function initDayTabs() {
  document.querySelectorAll('.day-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.day-tab-btn').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.day-tab-pane').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('day-tab-' + btn.dataset.day)?.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}


function initInPageScrollNav() {
  const navGroups = document.querySelectorAll('.in-page-nav');
  if (!navGroups.length) return;

  navGroups.forEach(group => {
    const buttons = Array.from(group.querySelectorAll('[data-scroll-target]'));
    const sections = buttons
      .map(btn => document.getElementById(btn.dataset.scrollTarget))
      .filter(Boolean);

    function setActive(targetId) {
      buttons.forEach(btn => btn.classList.toggle('active', btn.dataset.scrollTarget === targetId));
    }

    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.scrollTarget);
        if (!target) return;
        setActive(btn.dataset.scrollTarget);
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    if ('IntersectionObserver' in window && sections.length) {
      const observer = new IntersectionObserver(entries => {
        const visible = entries
          .filter(entry => entry.isIntersecting)
          .sort((a, b) => Math.abs(a.boundingClientRect.top) - Math.abs(b.boundingClientRect.top))[0];
        if (visible?.target?.id) setActive(visible.target.id);
      }, { root: null, rootMargin: '-28% 0px -62% 0px', threshold: 0.01 });

      sections.forEach(section => observer.observe(section));
    }
  });
}

function initChecklist() {
  const STORAGE_PREFIX = 'kyushu-checklist-';
  document.querySelectorAll('[data-check]').forEach(checkbox => {
    const key = STORAGE_PREFIX + checkbox.dataset.check;
    checkbox.checked = localStorage.getItem(key) === 'true';
    checkbox.addEventListener('change', () => {
      localStorage.setItem(key, checkbox.checked ? 'true' : 'false');
    });
  });
}

function initNavigation() {
  const menuToggle = document.getElementById('menuToggle');
  const sideDrawer = document.getElementById('sideDrawer');
  const sideOverlay = document.getElementById('sideOverlay');
  const drawerLinks = document.querySelectorAll('.drawer-link');
  const pageViews = document.querySelectorAll('.page-view');
  const quickLinks = document.querySelectorAll('[data-view-link]');
  const navActionBtns = document.querySelectorAll('[data-nav-action]');

  let currentViewId = 'home-view';

  function openDrawer() {
    sideDrawer?.classList.add('open');
    sideOverlay?.classList.add('open');
    if (menuToggle) menuToggle.style.visibility = 'hidden';
  }

  function closeDrawer() {
    sideDrawer?.classList.remove('open');
    sideOverlay?.classList.remove('open');
    if (menuToggle) menuToggle.style.visibility = 'visible';
  }

  function updateActiveLinks(viewId) {
    drawerLinks.forEach(btn => btn.classList.toggle('active', btn.dataset.view === viewId));
    quickLinks.forEach(btn => btn.classList.toggle('active', btn.dataset.viewLink === viewId));
  }

  function updateNavButtons() {
    const idx = VIEW_IDS.indexOf(currentViewId);
    navActionBtns.forEach(btn => {
      const action = btn.dataset.navAction;
      if (action === 'prev') btn.disabled = idx <= 0;
      if (action === 'next') btn.disabled = idx >= VIEW_IDS.length - 1;
    });
  }

  function switchView(viewId, options = {}) {
    if (!VIEW_IDS.includes(viewId)) viewId = 'home-view';
    currentViewId = viewId;
    pageViews.forEach(view => view.classList.toggle('active', view.id === viewId));
    updateActiveLinks(viewId);
    updateNavButtons();
    closeDrawer();

    if (!options.skipHash) {
      const hash = VIEW_TO_HASH[viewId] || 'home';
      if (location.hash !== '#' + hash) history.pushState({ viewId }, '', '#' + hash);
    }

    if (!options.keepScroll) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function switchByOffset(offset) {
    const idx = VIEW_IDS.indexOf(currentViewId);
    const nextIdx = Math.min(Math.max(idx + offset, 0), VIEW_IDS.length - 1);
    switchView(VIEW_IDS[nextIdx]);
  }

  window.switchKyushuView = switchView;

  menuToggle?.addEventListener('click', () => sideDrawer?.classList.contains('open') ? closeDrawer() : openDrawer());
  sideOverlay?.addEventListener('click', closeDrawer);
  drawerLinks.forEach(btn => btn.addEventListener('click', function () { switchView(this.dataset.view); }));
  quickLinks.forEach(btn => btn.addEventListener('click', function () { switchView(this.dataset.viewLink); }));
  navActionBtns.forEach(btn => btn.addEventListener('click', function () {
    if (this.dataset.navAction === 'prev') switchByOffset(-1);
    if (this.dataset.navAction === 'next') switchByOffset(1);
  }));

  window.addEventListener('popstate', () => {
    const hash = location.hash.replace('#', '') || 'home';
    switchView(HASH_TO_VIEW[hash] || 'home-view', { skipHash: true });
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
    if (e.altKey && e.key === 'ArrowLeft') switchByOffset(-1);
    if (e.altKey && e.key === 'ArrowRight') switchByOffset(1);
  });

  const initialHash = location.hash.replace('#', '') || 'home';
  switchView(HASH_TO_VIEW[initialHash] || 'home-view', { skipHash: true, keepScroll: true });
}

function initTripCountdown() {
  const box = document.getElementById('tripCountdown');
  if (!box) return;

  const targetText = box.dataset.countdownTarget;
  const target = new Date(targetText).getTime();
  if (!Number.isFinite(target)) return;

  const daysEl = box.querySelector('[data-countdown-days]');
  const hoursEl = box.querySelector('[data-countdown-hours]');
  const minutesEl = box.querySelector('[data-countdown-minutes]');
  const secondsEl = box.querySelector('[data-countdown-seconds]');

  function pad(n) {
    return String(Math.max(0, Math.floor(n))).padStart(2, '0');
  }

  function update() {
    const diff = target - Date.now();
    if (diff <= 0) {
      box.remove();
      clearInterval(timer);
      return;
    }

    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (daysEl) daysEl.textContent = String(days);
    if (hoursEl) hoursEl.textContent = pad(hours);
    if (minutesEl) minutesEl.textContent = pad(minutes);
    if (secondsEl) secondsEl.textContent = pad(seconds);
  }

  update();
  const timer = setInterval(update, 1000);
}

function initTravelTools() {
  const yen = n => '¥' + Math.round(Number(n || 0)).toLocaleString('ja-JP');
  const twd = n => '約 NT$' + Math.round(Number(n || 0)).toLocaleString('zh-TW');
  function updateCurrency() {
    const jpy = Number(document.getElementById('jpyInput')?.value || 0);
    const rate = Number(document.getElementById('rateInput')?.value || 0);
    const out = document.getElementById('twdResult');
    if (out) out.textContent = twd(jpy * rate);
  }
  function updateFuel() {
    const km = Number(document.getElementById('kmInput')?.value || 0);
    const eco = Number(document.getElementById('fuelEcoInput')?.value || 1);
    const price = Number(document.getElementById('fuelPriceInput')?.value || 0);
    const out = document.getElementById('fuelResult');
    if (out) out.textContent = '約 ' + yen((km / Math.max(eco, 1)) * price);
  }
  ['jpyInput','rateInput'].forEach(id => document.getElementById(id)?.addEventListener('input', updateCurrency));
  ['kmInput','fuelEcoInput','fuelPriceInput'].forEach(id => document.getElementById(id)?.addEventListener('input', updateFuel));
  updateCurrency();
  updateFuel();
}

async function main() {
  renderTicNoteMetaDate();
  try {
    await loadViews();
  } catch (err) {
    console.error(err);
    const root = document.getElementById('viewsRoot');
    if (root) root.innerHTML = '<div class="concierge-card"><h3>載入失敗</h3><p>請透過 GitHub Pages 或本機伺服器開啟，不要直接用 file:// 開啟。</p></div>';
    return;
  }
  initDayTabs();
  initChecklist();
  initInPageScrollNav();
  initNavigation();
  initTravelTools();
  initTripCountdown();
  initExpenseView();
}

main();
