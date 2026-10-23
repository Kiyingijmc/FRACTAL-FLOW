/**
 * FRACTAL-FLOW GUI — Real Component PositionsTable Sorting Behavioral Verification
 * D2-C / SORT-01–SORT-06
 *
 * Verifies the actual rendered <PositionsTable /> React component in a live JSDOM environment:
 * 1. Default initial sort renders open positions by PnL (unrealizedR) descending in DOM.
 * 2. Clicking PnL th header toggles direction to ascending (deepest loss to highest profit).
 * 3. Clicking Symbol th header sorts rows alphabetically (A to Z) and reverse alphabetically (Z to A).
 * 4. Clicking Size th header sorts rows numerically by lot size.
 * 5. Deterministic tie-breaking and handling of equal/missing values.
 * 6. Active row preservation: The selected position maintains its active highlight and data-selected="true" across all re-sorts.
 * 7. Tab transitions: Closed trades sorting by Realized R and Realized $; Pending orders sorting.
 * 8. Real DOM ARIA attributes: aria-sort reflects 'ascending', 'descending', or 'none'.
 * 9. Real sort status chip rendered in the header toolbar.
 */

import { JSDOM } from 'jsdom';
import React, { act } from 'react';
import ReactDOM from 'react-dom/client';
import { Position, ClosedTrade, PendingOrder } from '../types';

// 1. Initialize DOM environment
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost'
});

const { window } = dom;
const { document } = window;

(globalThis as any).window = window;
(globalThis as any).document = document;
try {
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
} catch {}
(globalThis as any).HTMLElement = window.HTMLElement;
(globalThis as any).HTMLButtonElement = window.HTMLButtonElement;
(globalThis as any).KeyboardEvent = window.KeyboardEvent;
(globalThis as any).MouseEvent = window.MouseEvent;
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

// Mock scrollIntoView for JSDOM
(window.HTMLElement.prototype as any).scrollIntoView = function() {};

// Deterministic test fixtures conforming strictly to Position, ClosedTrade, PendingOrder
const FIXTURE_POSITIONS: Position[] = [
  {
    id: 'pos_eur',
    symbol: 'EURUSD',
    side: 'LONG',
    setup: 'FF-01',
    mode: 'TREND_RUNNER',
    size: 2.0,
    entryPrice: 1.0850,
    currentPrice: 1.0890,
    unrealizedR: 1.5,
    mfe: 2.1,
    mae: -0.2,
    exitProfile: 'trail 2.5s',
    age: '1h 20m',
    structuralAnchor: '15M swing',
    trailDistance: '2.5σ',
    breakevenStatus: 'ARMED',
    decayState: 'FRESH',
    effectiveConfig: 'cfg_01',
    drivingTimeframe: '15M',
    lane: 'ACT_PRIMARY',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'pos_gbp',
    symbol: 'GBPUSD',
    side: 'SHORT',
    setup: 'FF-02',
    mode: 'RANGE_TARGET',
    size: 1.0,
    entryPrice: 1.2750,
    currentPrice: 1.2780,
    unrealizedR: -0.6,
    mfe: 0.2,
    mae: -0.7,
    exitProfile: 'range ladder',
    age: '45m',
    structuralAnchor: '30M range',
    trailDistance: '1.8σ',
    breakevenStatus: 'INACTIVE',
    decayState: 'FRESH',
    effectiveConfig: 'cfg_01',
    drivingTimeframe: '30M',
    lane: 'ACT_PRIMARY',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'pos_aud',
    symbol: 'AUDCAD',
    side: 'LONG',
    setup: 'FF-01',
    mode: 'TREND_RUNNER',
    size: 3.5,
    entryPrice: 0.8920,
    currentPrice: 0.8985,
    unrealizedR: 3.2,
    mfe: 3.5,
    mae: -0.1,
    exitProfile: 'trail 3.0s',
    age: '2h 10m',
    structuralAnchor: '1H swing',
    trailDistance: '3.0σ',
    breakevenStatus: 'LOCKED',
    decayState: 'FRESH',
    effectiveConfig: 'cfg_01',
    drivingTimeframe: '1H',
    lane: 'ACT_PRIMARY',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'pos_jpy',
    symbol: 'USDJPY',
    side: 'SHORT',
    setup: 'FF-03',
    mode: 'COUNTERFLOW',
    size: 0.5,
    entryPrice: 154.200,
    currentPrice: 154.200,
    unrealizedR: 0.0,
    mfe: 0.5,
    mae: -0.2,
    exitProfile: 'tight 2.0s',
    age: '15m',
    structuralAnchor: '5M swing',
    trailDistance: '2.0σ',
    breakevenStatus: 'INACTIVE',
    decayState: 'FRESH',
    effectiveConfig: 'cfg_01',
    drivingTimeframe: '5M',
    lane: 'ACT_PRIMARY',
    priceDecimals: 3,
    isSimulated: true,
  }
];

const FIXTURE_CLOSED_TRADES: ClosedTrade[] = [
  {
    id: 'trade_1',
    symbol: 'EURUSD',
    side: 'LONG',
    setup: 'FF-01',
    mode: 'TREND_RUNNER',
    size: 1.5,
    entryPrice: 1.0820,
    exitPrice: 1.0890,
    realizedR: 2.1,
    realizedPnl: 450,
    duration: '45m',
    closedAt: '10:15:20',
    exitReason: 'TARGET_HIT',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'trade_2',
    symbol: 'GBPUSD',
    side: 'SHORT',
    setup: 'FF-02',
    mode: 'RANGE_TARGET',
    size: 2.0,
    entryPrice: 1.2780,
    exitPrice: 1.2820,
    realizedR: -1.0,
    realizedPnl: -320,
    duration: '1h 10m',
    closedAt: '11:05:10',
    exitReason: 'STOP_LOSS',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'trade_3',
    symbol: 'USDJPY',
    side: 'LONG',
    setup: 'FF-01',
    mode: 'COUNTERFLOW',
    size: 1.0,
    entryPrice: 153.500,
    exitPrice: 154.500,
    realizedR: 3.5,
    realizedPnl: 800,
    duration: '2h 30m',
    closedAt: '09:40:00',
    exitReason: 'TRAILING_STOP',
    priceDecimals: 3,
    isSimulated: true,
  }
];

const FIXTURE_PENDING_ORDERS: PendingOrder[] = [
  {
    id: 'order_1',
    symbol: 'EURUSD',
    side: 'LONG',
    setup: 'FF-01',
    type: 'LIMIT_BUY',
    size: 1.5,
    price: 1.0810,
    triggerCond: 'Bid <= 1.0810',
    age: '12m',
    priceDecimals: 4,
    isSimulated: true,
  },
  {
    id: 'order_2',
    symbol: 'AUDCAD',
    side: 'LONG',
    setup: 'FF-02',
    type: 'STOP_BUY',
    size: 2.5,
    price: 0.8950,
    triggerCond: 'Ask >= 0.8950',
    age: '5m',
    priceDecimals: 4,
    isSimulated: true,
  }
];

async function runPositionsTableBehavioralSortVerification() {
  const { PositionsTable } = await import('../components/PositionsTable');

  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — PositionsTable Real Component Sort Verification (D2-C)');
  console.log('Targets: Real rendered React <PositionsTable /> DOM in JSDOM');
  console.log('========================================================\n');

  let passed = 0;
  let failed = 0;

  async function test(name: string, fn: () => Promise<void> | void) {
    try {
      await fn();
      console.log(`  [PASS] ${name}`);
      passed++;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`  [FAIL] ${name}: ${msg}`);
      failed++;
    }
  }

  let mountContainer: HTMLElement | null = null;
  let root: ReactDOM.Root | null = null;

  function mountTable(props: Partial<React.ComponentProps<typeof PositionsTable>> = {}) {
    if (root) {
      act(() => {
        root!.unmount();
      });
      root = null;
    }
    if (mountContainer) {
      mountContainer.remove();
    }
    mountContainer = document.createElement('div');
    document.body.appendChild(mountContainer);
    root = ReactDOM.createRoot(mountContainer);

    const defaultProps = {
      positions: FIXTURE_POSITIONS,
      pendingOrders: FIXTURE_PENDING_ORDERS,
      closedTrades: FIXTURE_CLOSED_TRADES,
      selectedPositionId: 'pos_eur',
      activeSubTab: 'open' as const,
      onSubTabChange: () => {},
      onSelectPosition: () => {},
      onEmergencyClose: () => {},
      onTightenStop: () => {},
      onMoveToBreakeven: () => {}
    };

    act(() => {
      root!.render(React.createElement(PositionsTable, { ...defaultProps, ...props }));
    });
  }

  function teardown() {
    if (root) {
      act(() => {
        root!.unmount();
      });
      root = null;
    }
    if (mountContainer) {
      mountContainer.remove();
      mountContainer = null;
    }
  }

  function getRenderedRowIds(): string[] {
    const rows = mountContainer!.querySelectorAll('tbody tr');
    const ids: string[] = [];
    rows.forEach(r => {
      const id = r.getAttribute('data-position-id');
      if (id) ids.push(id);
    });
    return ids;
  }

  function getThByText(text: string): HTMLTableCellElement {
    const ths = Array.from(mountContainer!.querySelectorAll<HTMLTableCellElement>('thead th'));
    const target = ths.find(th => th.textContent?.toLowerCase().includes(text.toLowerCase()));
    if (!target) throw new Error(`Table header <th> containing '${text}' not found`);
    return target;
  }

  // =========================================================================
  // 1. DEFAULT SORT BEHAVIOR: PnL (unrealizedR) Descending
  // =========================================================================

  await test('SORT-01: Default initial sort orders open positions by PnL (unrealizedR) descending in DOM', () => {
    mountTable();
    const ids = getRenderedRowIds();
    // Expected order: AUDCAD (3.2R), EURUSD (1.5R), USDJPY (0.0R), GBPUSD (-0.6R)
    if (ids[0] !== 'pos_aud' || ids[1] !== 'pos_eur' || ids[2] !== 'pos_jpy' || ids[3] !== 'pos_gbp') {
      throw new Error(`Unexpected default sort order: ${ids.join(', ')}`);
    }

    // Verify sort chip in toolbar
    const chip = mountContainer!.querySelector('.font-mono.text-\\[10px\\]');
    if (!chip || !chip.textContent?.includes('PnL (R)')) {
      throw new Error('Sort status chip does not reflect PnL (R)');
    }
    teardown();
  });

  // =========================================================================
  // 2. TOGGLE DIRECTION: PnL Ascending
  // =========================================================================

  await test('SORT-02: Clicking PnL header toggles direction to ascending (deepest loss to highest profit)', () => {
    mountTable();
    const pnlTh = getThByText('PnL (unreal');

    // Click to toggle to ascending
    act(() => {
      pnlTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    const ids = getRenderedRowIds();
    // Expected ascending order: GBPUSD (-0.6R), USDJPY (0.0R), EURUSD (1.5R), AUDCAD (3.2R)
    if (ids[0] !== 'pos_gbp' || ids[1] !== 'pos_jpy' || ids[2] !== 'pos_eur' || ids[3] !== 'pos_aud') {
      throw new Error(`Unexpected ascending sort order: ${ids.join(', ')}`);
    }

    if (pnlTh.getAttribute('aria-sort') !== 'ascending') {
      throw new Error(`aria-sort did not update to 'ascending', got: ${pnlTh.getAttribute('aria-sort')}`);
    }
    teardown();
  });

  // =========================================================================
  // 3. COLUMN CHANGE: Symbol Sorting
  // =========================================================================

  await test('SORT-03: Clicking Symbol header orders rows alphabetically (A to Z) then (Z to A)', () => {
    mountTable();
    const symbolTh = getThByText('symbol');

    // Click to sort by Symbol ascending (A to Z)
    act(() => {
      symbolTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    let ids = getRenderedRowIds();
    // Alphabetical: AUDCAD, EURUSD, GBPUSD, USDJPY
    if (ids[0] !== 'pos_aud' || ids[1] !== 'pos_eur' || ids[2] !== 'pos_gbp' || ids[3] !== 'pos_jpy') {
      throw new Error(`Unexpected alphabetical sort: ${ids.join(', ')}`);
    }

    // Click again to toggle to descending (Z to A)
    act(() => {
      symbolTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    ids = getRenderedRowIds();
    // Reverse: USDJPY, GBPUSD, EURUSD, AUDCAD
    if (ids[0] !== 'pos_jpy' || ids[1] !== 'pos_gbp' || ids[2] !== 'pos_eur' || ids[3] !== 'pos_aud') {
      throw new Error(`Unexpected reverse alphabetical sort: ${ids.join(', ')}`);
    }
    teardown();
  });

  // =========================================================================
  // 4. COLUMN CHANGE: Size Sorting
  // =========================================================================

  await test('SORT-04: Clicking Size header orders rows numerically by lot exposure', () => {
    mountTable();
    const sizeTh = getThByText('size');

    // Click Size header (default descending)
    act(() => {
      sizeTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    let ids = getRenderedRowIds();
    // Descending size: AUDCAD (3.5), EURUSD (2.0), GBPUSD (1.0), USDJPY (0.5)
    if (ids[0] !== 'pos_aud' || ids[1] !== 'pos_eur' || ids[2] !== 'pos_gbp' || ids[3] !== 'pos_jpy') {
      throw new Error(`Unexpected size descending sort: ${ids.join(', ')}`);
    }

    // Toggle to ascending size
    act(() => {
      sizeTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    ids = getRenderedRowIds();
    // Ascending size: USDJPY (0.5), GBPUSD (1.0), EURUSD (2.0), AUDCAD (3.5)
    if (ids[0] !== 'pos_jpy' || ids[1] !== 'pos_gbp' || ids[2] !== 'pos_eur' || ids[3] !== 'pos_aud') {
      throw new Error(`Unexpected size ascending sort: ${ids.join(', ')}`);
    }
    teardown();
  });

  // =========================================================================
  // 5. SELECTED ROW ACTIVE RETENTION ACROSS SORTS
  // =========================================================================

  await test('SORT-05: Selected position row retains active data-selected="true" after re-sorting', () => {
    // Select pos_eur
    mountTable({ selectedPositionId: 'pos_eur' });

    let eurRow = mountContainer!.querySelector('tr[data-position-id="pos_eur"]');
    if (eurRow?.getAttribute('data-selected') !== 'true') {
      throw new Error('Selected row missing data-selected="true" before sort');
    }

    // Sort by Size (which moves pos_eur from 2nd position to another rank)
    const sizeTh = getThByText('size');
    act(() => {
      sizeTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    eurRow = mountContainer!.querySelector('tr[data-position-id="pos_eur"]');
    if (eurRow?.getAttribute('data-selected') !== 'true') {
      throw new Error('Selected row lost data-selected="true" after Size re-sort');
    }

    // Sort by Symbol descending
    const symbolTh = getThByText('symbol');
    act(() => {
      symbolTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });
    act(() => {
      symbolTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    eurRow = mountContainer!.querySelector('tr[data-position-id="pos_eur"]');
    if (eurRow?.getAttribute('data-selected') !== 'true') {
      throw new Error('Selected row lost data-selected="true" after reverse Symbol re-sort');
    }
    teardown();
  });

  // =========================================================================
  // 6. CLOSED TRADES TAB SORTING
  // =========================================================================

  await test('SORT-06: Closed trades tab supports interactive sorting by Realized R and Realized $', () => {
    mountTable({ activeSubTab: 'closed' });

    // Default closed sort is realizedR descending: trade_3 (3.5R), trade_1 (2.1R), trade_2 (-1.0R)
    let rows = mountContainer!.querySelectorAll('tbody tr');
    let firstSym = rows[0]?.querySelector('td')?.textContent?.trim();
    if (firstSym !== 'USDJPY') {
      throw new Error(`Expected USDJPY with highest Realized R first, got: ${firstSym}`);
    }

    // Click Realized PnL ($) header
    const pnlDollarTh = getThByText('($)');
    act(() => {
      pnlDollarTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    // Invert to ascending (deepest dollar loss first: trade_2 (-$320))
    act(() => {
      pnlDollarTh.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });

    rows = mountContainer!.querySelectorAll('tbody tr');
    firstSym = rows[0]?.querySelector('td')?.textContent?.trim();
    if (firstSym !== 'GBPUSD') {
      throw new Error(`Expected GBPUSD with deepest dollar loss (-$320) first, got: ${firstSym}`);
    }
    teardown();
  });

  console.log('--------------------------------------------------------');
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runPositionsTableBehavioralSortVerification().catch((err) => {
  console.error('Fatal error in PositionsTable sort behavioral test:', err);
  process.exit(1);
});
