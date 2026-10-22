import fs from 'fs';
import path from 'path';

function runResponsiveStructuralVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Responsive Structural Verification');
  console.log('Target Viewports: 320px, 360px, 390px, 430px, 768px, 1024px, 1280px');
  console.log('========================================================\n');

  let passed = 0;
  let failed = 0;

  function verify(name: string, fn: () => void) {
    try {
      fn();
      console.log(`  [PASS] ${name}`);
      passed++;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`  [FAIL] ${name}: ${msg}`);
      failed++;
    }
  }

  const appSrc = fs.readFileSync('src/App.tsx', 'utf8');
  const headerSrc = fs.readFileSync('src/components/Header.tsx', 'utf8');
  const navRailSrc = fs.readFileSync('src/components/NavRail.tsx', 'utf8');
  const mobileNavSrc = fs.readFileSync('src/components/MobileBottomNav.tsx', 'utf8');
  const positionsSrc = fs.readFileSync('src/components/PositionsTable.tsx', 'utf8');
  const contextSrc = fs.readFileSync('src/components/ContextPanel.tsx', 'utf8');
  const secondarySrc = fs.readFileSync('src/components/SecondaryViews.tsx', 'utf8');
  const footerSrc = fs.readFileSync('src/components/FooterLog.tsx', 'utf8');
  const gateSrc = fs.readFileSync('src/components/GateChainStrip.tsx', 'utf8');

  // 1. Root Container Viewport Invariance
  verify('UX-01.1: Root container prevents document-level horizontal overflow (no w-screen)', () => {
    if (appSrc.includes('w-screen')) {
      throw new Error('App.tsx still contains w-screen causing mobile viewport overflow');
    }
    if (!appSrc.includes('w-full max-w-full overflow-hidden')) {
      throw new Error('App.tsx missing w-full max-w-full overflow-hidden container bounding');
    }
  });

  // 2. Navigation Segregation across Breakpoints
  verify('UX-04.1: Desktop NavRail hidden on mobile viewports (<768px)', () => {
    if (!navRailSrc.includes('hidden md:flex')) {
      throw new Error('NavRail is not hidden on narrow viewports with hidden md:flex');
    }
  });

  verify('UX-04.2: MobileBottomNav docked exclusively on mobile (<768px) with 44px+ touch targets', () => {
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

  // 3. Responsive Header Architecture
  verify('UX-02.1: Header implements two-tier layout on mobile and single-deck on desktop', () => {
    if (!headerSrc.includes('md:hidden') || !headerSrc.includes('hidden md:flex')) {
      throw new Error('Header lacks responsive split between mobile and desktop viewports');
    }
    if (!headerSrc.includes('SIM: OFF-BROKER')) {
      throw new Error('Header omitted unambiguous simulation mode badge on mobile');
    }
  });

  // 4. Data Tables Overflow Containment
  verify('UX-03.1: PositionsTable wraps data tables in dedicated horizontal scrolling container', () => {
    if (!positionsSrc.includes('overflow-auto w-full') && !positionsSrc.includes('overflow-x-auto')) {
      throw new Error('PositionsTable missing overflow container');
    }
    if (!positionsSrc.includes('min-w-[')) {
      throw new Error('PositionsTable lacks minimum content width guarding column compression');
    }
  });

  verify('UX-03.2: Secondary views (DEC, MODE, NEWS, CALIB) prevent wide-table overflow blowouts', () => {
    const overflowOccurrences = (secondarySrc.match(/overflow-x-auto/g) || []).length;
    if (overflowOccurrences < 4) {
      throw new Error(`SecondaryViews lacks sufficient overflow-x-auto wrappers (found ${overflowOccurrences})`);
    }
  });

  // 5. Responsive Grid Layouts
  verify('UX-05.1: Risk, News, and Stats cards use responsive multi-breakpoint column layouts', () => {
    if (!secondarySrc.includes('grid-cols-1 sm:grid-cols-2 lg:grid-cols-4')) {
      throw new Error('SecondaryViews still uses rigid 4-column layout on mobile viewports');
    }
  });

  // 6. Accessible Action Controls & Touch Targets
  verify('UX-06.1: Gated execution buttons enforce 44px minimum touch targets', () => {
    const action44Count = (contextSrc.match(/min-h-\[44px\]/g) || []).length;
    if (action44Count < 3) {
      throw new Error(`ContextPanel action buttons do not all enforce min-h-[44px] (found ${action44Count})`);
    }
  });

  // 7. Accessible Modal Drawer Semantics
  verify('UX-07.1: Drawers in MobileBottomNav and FooterLog implement ARIA dialog semantics and Escape dismissal', () => {
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

  // 8. Safe-Area and Bottom Navigation Clearance
  verify('UX-08.1: Main viewport container enforces bottom padding clearance for docked mobile nav', () => {
    if (!appSrc.includes('pb-14') && !appSrc.includes('pb-16')) {
      throw new Error('App.tsx missing bottom padding clearance for docked bottom navigation');
    }
  });

  console.log('\n========================================================');
  console.log(`Responsive Structural Results: ${passed} PASSED, ${failed} FAILED`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runResponsiveStructuralVerification();
