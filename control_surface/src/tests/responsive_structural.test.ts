import fs from 'fs';
import path from 'path';
import React, { act } from 'react';
import ReactDOM from 'react-dom/client';
import { JSDOM } from 'jsdom';

// Setup JSDOM environment for behavioral viewport testing
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:3000',
  pretendToBeVisual: true,
});

const { window } = dom;

// Polyfill globals for React 19 testing in Node
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
(globalThis as any).window = window;
(globalThis as any).document = window.document;
(globalThis as any).HTMLElement = window.HTMLElement;
(globalThis as any).HTMLInputElement = window.HTMLInputElement;
(globalThis as any).HTMLButtonElement = window.HTMLButtonElement;
(globalThis as any).MouseEvent = window.MouseEvent;
(globalThis as any).KeyboardEvent = window.KeyboardEvent;
(globalThis as any).Event = window.Event;

try {
  Object.defineProperty(globalThis, 'navigator', {
    value: window.navigator,
    configurable: true,
  });
} catch {}

// Mock scrollTo and scrollIntoView
window.HTMLElement.prototype.scrollIntoView = function () {};
window.scrollTo = function () {};

async function runResponsiveStructuralVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Responsive Structural & Viewport Behavioral Verification (D2-C)');
  console.log('Target Viewports: 320px, 360px, 390px, 430px, 768px, 1024px, 1280px');
  console.log('Targets: Static source analysis + Real rendered React <App /> in JSDOM');
  console.log('========================================================\n');

  let passed = 0;
  let failed = 0;

  function verify(name: string, fn: () => void | Promise<void>) {
    return Promise.resolve()
      .then(() => fn())
      .then(() => {
        console.log(`  [PASS] ${name}`);
        passed++;
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`  [FAIL] ${name}: ${msg}`);
        failed++;
      });
  }

  // -------------------------------------------------------------------------
  // PART 1: SOURCE-LEVEL STRUCTURAL INVARIANT CHECKS (UX-01 - UX-08)
  // -------------------------------------------------------------------------
  const appSrc = fs.readFileSync('src/App.tsx', 'utf8');
  const headerSrc = fs.readFileSync('src/components/Header.tsx', 'utf8');
  const navRailSrc = fs.readFileSync('src/components/NavRail.tsx', 'utf8');
  const mobileNavSrc = fs.readFileSync('src/components/MobileBottomNav.tsx', 'utf8');
  const positionsSrc = fs.readFileSync('src/components/PositionsTable.tsx', 'utf8');
  const contextSrc = fs.readFileSync('src/components/ContextPanel.tsx', 'utf8');
  const secondarySrc = fs.readFileSync('src/components/SecondaryViews.tsx', 'utf8');
  const footerSrc = fs.readFileSync('src/components/FooterLog.tsx', 'utf8');

  await verify('UX-01.1: Root container prevents document-level horizontal overflow (no w-screen)', () => {
    if (appSrc.includes('w-screen')) {
      throw new Error('App.tsx still contains w-screen causing mobile viewport overflow');
    }
    if (!appSrc.includes('w-full max-w-full overflow-hidden')) {
      throw new Error('App.tsx missing w-full max-w-full overflow-hidden container bounding');
    }
  });

  await verify('UX-04.1: Desktop NavRail hidden on mobile viewports (<768px)', () => {
    if (!navRailSrc.includes('hidden md:flex')) {
      throw new Error('NavRail is not hidden on narrow viewports with hidden md:flex');
    }
  });

  await verify('UX-04.2: MobileBottomNav docked exclusively on mobile (<768px) with 44px+ touch targets', () => {
    if (!mobileNavSrc.includes('md:hidden')) {
      throw new Error('MobileBottomNav lacks md:hidden visibility restriction');
    }
    if (!mobileNavSrc.includes('min-h-[44px]')) {
      throw new Error('MobileBottomNav tabs do not guarantee 44px minimum touch height');
    }
    if (!mobileNavSrc.includes('fixed bottom-0')) {
      throw new Error('MobileBottomNav is not fixed to viewport bottom');
    }
  });

  await verify('UX-02.1: Header implements two-tier layout on mobile and single-deck on desktop', () => {
    if (!headerSrc.includes('md:hidden') || !headerSrc.includes('hidden md:flex')) {
      throw new Error('Header lacks responsive split between mobile and desktop viewports');
    }
    if (!headerSrc.includes('SIM: OFF-BROKER')) {
      throw new Error('Header omitted unambiguous simulation mode badge on mobile');
    }
  });

  await verify('UX-03.1: PositionsTable wraps data tables in dedicated horizontal scrolling container', () => {
    if (!positionsSrc.includes('overflow-auto w-full') && !positionsSrc.includes('overflow-x-auto')) {
      throw new Error('PositionsTable missing overflow container');
    }
    if (!positionsSrc.includes('min-w-[')) {
      throw new Error('PositionsTable lacks minimum content width guarding column compression');
    }
  });

  await verify('UX-03.2: Secondary views (DEC, MODE, NEWS, CALIB) prevent wide-table overflow blowouts', () => {
    const overflowOccurrences = (secondarySrc.match(/overflow-x-auto/g) || []).length;
    if (overflowOccurrences < 4) {
      throw new Error(`SecondaryViews lacks sufficient overflow-x-auto wrappers (found ${overflowOccurrences})`);
    }
  });

  await verify('UX-05.1: Risk, News, and Stats cards use responsive multi-breakpoint column layouts', () => {
    if (!secondarySrc.includes('grid-cols-1 sm:grid-cols-2 lg:grid-cols-4')) {
      throw new Error('SecondaryViews still uses rigid 4-column layout on mobile viewports');
    }
  });

  await verify('UX-06.1: Gated execution buttons enforce 44px minimum touch targets', () => {
    const action44Count = (contextSrc.match(/min-h-\[44px\]/g) || []).length;
    if (action44Count < 3) {
      throw new Error(`ContextPanel action buttons do not all enforce min-h-[44px] (found ${action44Count})`);
    }
  });

  await verify('UX-07.1: Drawers in MobileBottomNav and FooterLog implement ARIA dialog semantics and Escape dismissal', () => {
    if (!mobileNavSrc.includes('role="dialog"') || !mobileNavSrc.includes('aria-modal="true"')) {
      throw new Error('MobileBottomNav More drawer missing ARIA dialog/modal attributes');
    }
    if (!footerSrc.includes('role="dialog"') || !footerSrc.includes('aria-modal="true"')) {
      throw new Error('FooterLog journal sheet missing ARIA dialog/modal attributes');
    }
    if (!mobileNavSrc.includes("'Escape'") || !footerSrc.includes("'Escape'")) {
      throw new Error('Modal drawers missing Escape key dismissal');
    }
  });

  await verify('UX-08.1: Main viewport container enforces bottom padding clearance for docked mobile nav', () => {
    if (!appSrc.includes('pb-14') && !appSrc.includes('pb-16')) {
      throw new Error('App.tsx missing bottom padding clearance for docked bottom navigation');
    }
  });

  // -------------------------------------------------------------------------
  // PART 2: REAL COMPONENT VIEWPORT BEHAVIORAL CHECKS ACROSS 7 VIEWPORTS (D2-C)
  // Viewports: 320px, 360px, 390px, 430px, 768px, 1024px, 1280px
  // -------------------------------------------------------------------------
  const { App } = await import('../App');

  const TARGET_VIEWPORTS = [
    { width: 320, height: 568, category: 'narrow-mobile' },
    { width: 360, height: 640, category: 'compact-mobile' },
    { width: 390, height: 844, category: 'standard-mobile' },
    { width: 430, height: 932, category: 'large-mobile' },
    { width: 768, height: 1024, category: 'tablet-portrait' },
    { width: 1024, height: 768, category: 'tablet-desktop' },
    { width: 1280, height: 800, category: 'wide-desktop' },
  ];

  let container: HTMLDivElement | null = null;
  let root: ReactDOM.Root | null = null;

  function setViewport(w: number, h: number) {
    (window as any).innerWidth = w;
    (window as any).innerHeight = h;
    window.dispatchEvent(new window.Event('resize'));
  }

  function mountApp() {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = ReactDOM.createRoot(container);
    act(() => {
      root!.render(React.createElement(App));
    });
  }

  function unmountApp() {
    if (root && container) {
      act(() => {
        root!.unmount();
      });
      container.remove();
      root = null;
      container = null;
    }
  }

  // Test behavioral mounting and layout invariants across all 7 viewports
  for (const vp of TARGET_VIEWPORTS) {
    await verify(`VIEWPORT-${vp.width}px: Document bounding, overflow prevention & safe-area clearance`, () => {
      setViewport(vp.width, vp.height);
      mountApp();

      const appRoot = container!.firstElementChild as HTMLElement;
      if (!appRoot) throw new Error('App failed to render root container element');

      // Verify no horizontal overflow classes
      const className = appRoot.className;
      if (className.includes('w-screen')) {
        throw new Error(`Viewport ${vp.width}px contains w-screen causing layout blowout`);
      }
      if (!className.includes('max-w-full') || !className.includes('overflow-hidden')) {
        throw new Error(`Viewport ${vp.width}px root lacks max-w-full overflow-hidden container bounding`);
      }

      // Verify safe-area clearance for mobile bottom nav
      if (vp.width < 768) {
        if (!className.includes('pb-14') && !className.includes('pb-16')) {
          throw new Error(`Mobile viewport ${vp.width}px lacks pb-14/pb-16 bottom nav clearance`);
        }
      }

      // Verify critical simulation badge visibility in DOM (never clipped or omitted)
      const simBadges = Array.from(container!.querySelectorAll('*')).filter(
        (el) => el.textContent?.includes('SIM: OFF-BROKER')
      );
      if (simBadges.length === 0) {
        throw new Error(`Viewport ${vp.width}px omitted required 'SIM: OFF-BROKER' mode indicator`);
      }

      // Verify telemetry health indicator in DOM
      const healthBadges = Array.from(container!.querySelectorAll('*')).filter(
        (el) => el.textContent?.includes('HEALTHY') || el.textContent?.includes('SIM_VIRTUAL_OK')
      );
      if (healthBadges.length === 0) {
        throw new Error(`Viewport ${vp.width}px omitted active telemetry status badge`);
      }

      unmountApp();
    });
  }

  // -------------------------------------------------------------------------
  // PART 3: REACHABILITY OF ALL 8 NAVIGATION DESTINATIONS (D2-C)
  // Destinations: POS, DEC, RISK, MODE, NEWS, CALIB, HEALTH, STATS
  // -------------------------------------------------------------------------

  await verify('NAV-01: Mobile reachability of all 8 destinations via MobileBottomNav and More Drawer', () => {
    setViewport(390, 844); // Standard mobile viewport
    mountApp();

    const mobileNav = container!.querySelector('nav[aria-label="Mobile Navigation"]');
    if (!mobileNav) throw new Error('Mobile bottom nav not found in DOM');

    // 1. Primary mobile tabs: POS, DEC, RISK, MODE
    const primaryTabs = ['DEC', 'RISK', 'MODE', 'POS'];
    for (const tabId of primaryTabs) {
      // Find button in mobile nav
      const buttons = Array.from(mobileNav.querySelectorAll('button'));
      const targetBtn = buttons.find((b) => b.textContent?.trim().startsWith(tabId));
      if (!targetBtn) {
        throw new Error(`Mobile bottom nav missing direct button for ${tabId}`);
      }

      act(() => {
        targetBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      });

      // Verify destination view mounted
      if (tabId === 'POS') {
        const table = container!.querySelector('table');
        if (!table) throw new Error('Switching to POS did not mount Positions table');
      } else {
        if (!container!.textContent?.includes(tabId)) {
          throw new Error(`Switching to ${tabId} did not mount corresponding view`);
        }
      }
    }

    // 2. Secondary destinations via More drawer: NEWS, CALIB, HEALTH, STATS
    const secondaryTabs = ['NEWS', 'CALIB', 'HEALTH', 'STATS'];
    for (const tabId of secondaryTabs) {
      // Find and click More button
      const buttons = Array.from(mobileNav.querySelectorAll('button'));
      const moreBtn = buttons.find((b) => b.getAttribute('aria-label')?.includes('More') || b.textContent?.includes('MORE') || b.textContent?.includes('Panels'));
      if (!moreBtn) throw new Error('Mobile bottom nav missing More drawer button');

      act(() => {
        moreBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      });

      // Verify drawer opened with ARIA dialog semantics
      const drawer = container!.querySelector('div[role="dialog"]');
      if (!drawer || drawer.getAttribute('aria-modal') !== 'true') {
        throw new Error('More drawer did not mount with role="dialog" and aria-modal="true"');
      }

      // Find secondary destination button inside drawer
      const drawerButtons = Array.from(drawer.querySelectorAll('button'));
      const secBtn = drawerButtons.find((b) => b.textContent?.includes(tabId));
      if (!secBtn) throw new Error(`More drawer missing destination button for ${tabId}`);

      act(() => {
        secBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      });

      // Drawer should close automatically on selection
      const closedDrawer = container!.querySelector('div[role="dialog"]');
      if (closedDrawer) {
        throw new Error(`More drawer remained open after selecting destination ${tabId}`);
      }

      // Corresponding secondary view should now be active
      if (!container!.textContent?.includes(tabId)) {
        throw new Error(`Selecting ${tabId} from More drawer did not activate ${tabId} view`);
      }
    }

    // Return to POS
    const posBtn = Array.from(mobileNav.querySelectorAll('button')).find((b) =>
      b.textContent?.trim().startsWith('POS')
    );
    act(() => {
      posBtn?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    unmountApp();
  });

  await verify('NAV-02: Desktop reachability of all 8 destinations via NavRail sidebar', () => {
    setViewport(1280, 800); // Desktop viewport
    mountApp();

    const ALL_8_DESTINATIONS = ['POS', 'DEC', 'RISK', 'MODE', 'NEWS', 'CALIB', 'HEALTH', 'STATS'];

    // Check desktop nav rail
    const navRail = container!.querySelector('nav.hidden.md\\:flex, nav');
    if (!navRail) throw new Error('Desktop NavRail not found in DOM');

    const navButtons = Array.from(navRail.querySelectorAll('button'));
    if (navButtons.length < 8) {
      throw new Error(`Desktop NavRail should contain 8 navigation buttons, found ${navButtons.length}`);
    }

    for (const tabId of ALL_8_DESTINATIONS) {
      const btn = navButtons.find((b) => b.textContent?.trim() === tabId);
      if (!btn) throw new Error(`Desktop NavRail missing button for ${tabId}`);

      act(() => {
        btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      });

      if (tabId === 'POS') {
        const table = container!.querySelector('table');
        if (!table) throw new Error('Navigating to POS did not display table');
      } else {
        if (!container!.textContent?.includes(tabId)) {
          throw new Error(`Navigating to ${tabId} did not update main view`);
        }
      }
    }

    unmountApp();
  });

  // -------------------------------------------------------------------------
  // PART 4: TOUCH TARGET HEIGHT INVARIANCES (D2-C)
  // -------------------------------------------------------------------------
  await verify('TOUCH-01: Critical touch controls guarantee min-h-[44px] on mobile', () => {
    setViewport(390, 844);
    mountApp();

    // 1. Mobile bottom nav buttons
    const mobileNavButtons = Array.from(container!.querySelectorAll('nav.md\\:hidden button'));
    mobileNavButtons.forEach((btn) => {
      if (!btn.className.includes('min-h-[44px]')) {
        throw new Error(`MobileBottomNav button '${btn.textContent?.trim()}' missing min-h-[44px]`);
      }
    });

    // 2. Sub-tab buttons in PositionsTable
    const subTabButtons = Array.from(container!.querySelectorAll('button')).filter(
      (b) => b.textContent?.includes('Open (') || b.textContent?.includes('Pending (') || b.textContent?.includes('Closed (')
    );
    subTabButtons.forEach((btn) => {
      if (!btn.className.includes('min-h-[44px]')) {
        throw new Error(`SubTab button '${btn.textContent?.trim()}' missing min-h-[44px]`);
      }
    });

    unmountApp();
  });

  console.log('\n========================================================');
  console.log(`Responsive Behavioral Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runResponsiveStructuralVerification().catch((err) => {
  console.error('Fatal error in Responsive Structural verification:', err);
  process.exit(1);
});
