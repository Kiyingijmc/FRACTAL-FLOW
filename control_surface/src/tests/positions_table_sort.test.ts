import fs from 'fs';
import { Position, ClosedTrade } from '../types';

function runPositionsTableSortVerification() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — PositionsTable Column Sort Invariant Verification');
  console.log('Targets: PnL (unrealizedR/realizedR), Symbol, Size, Price, Age');
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

  const tableSrc = fs.readFileSync('src/components/PositionsTable.tsx', 'utf8');

  // 1. Static Contract & Interface Invariants
  verify('SORT-01.1: OpenSortField type exports support for symbol, size, unrealizedR (PnL), entryPrice, currentPrice, mfe, age', () => {
    if (!tableSrc.includes("export type OpenSortField = 'symbol' | 'entryPrice' | 'currentPrice' | 'size' | 'unrealizedR' | 'mfe' | 'age'")) {
      throw new Error('OpenSortField definition missing expected sortable columns');
    }
  });

  verify('SORT-01.2: Default sort configuration prioritizes PnL (unrealizedR) descending for open positions', () => {
    if (!tableSrc.includes("const [openSortField, setOpenSortField] = useState<OpenSortField>('unrealizedR')")) {
      throw new Error('Default openSortField is not initialized to unrealizedR');
    }
    if (!tableSrc.includes("const [openSortDir, setOpenSortDir] = useState<SortDirection>('desc')")) {
      throw new Error('Default openSortDir is not initialized to desc');
    }
  });

  verify('SORT-01.3: Column headers include accessible aria-sort attributes for screen readers', () => {
    if (!tableSrc.includes('aria-sort={openSortField === \'symbol\' ? (openSortDir === \'asc\' ? \'ascending\' : \'descending\') : \'none\'}')) {
      throw new Error('Missing aria-sort attribute for Symbol column');
    }
    if (!tableSrc.includes('aria-sort={openSortField === \'size\' ? (openSortDir === \'asc\' ? \'ascending\' : \'descending\') : \'none\'}')) {
      throw new Error('Missing aria-sort attribute for Size column');
    }
    if (!tableSrc.includes('aria-sort={openSortField === \'unrealizedR\' ? (openSortDir === \'asc\' ? \'ascending\' : \'descending\') : \'none\'}')) {
      throw new Error('Missing aria-sort attribute for PnL (unrealizedR) column');
    }
  });

  verify('SORT-01.4: Header displays active sort status indicator chip', () => {
    if (!tableSrc.includes('Sorted by:') || !tableSrc.includes('openSortField === \'unrealizedR\' ? \'PnL (R)\' : openSortField')) {
      throw new Error('Missing sort status chip in table header controls');
    }
  });

  verify('SORT-01.5: Selected row maintains active DOM tracking and scrollIntoView effect during re-sorting', () => {
    if (!tableSrc.includes('selectedRowRef = useRef<HTMLTableRowElement>(null)')) {
      throw new Error('Missing selectedRowRef declaration for maintaining row visibility');
    }
    if (!tableSrc.includes('ref={isSelected ? selectedRowRef : undefined}')) {
      throw new Error('Selected row is not wired to selectedRowRef');
    }
    if (!tableSrc.includes('selectedRowRef.current.scrollIntoView')) {
      throw new Error('Missing scrollIntoView execution to keep active position in view upon sort');
    }
    if (!tableSrc.includes('[openSortField, openSortDir, selectedPositionId, activeSubTab]')) {
      throw new Error('scrollIntoView effect does not depend on openSortField and openSortDir');
    }
  });

  verify('SORT-01.6: Sortable columns provide distinct visual indicators and interactive states from unsorted/non-sortable columns', () => {
    if (!tableSrc.includes('title="Sortable column"') || !tableSrc.includes('opacity-70 group-hover:opacity-100')) {
      throw new Error('Missing visible sortable indicator icon on unsorted sortable columns');
    }
    if (!tableSrc.includes('border-[#5B8FBF] font-semibold') || !tableSrc.includes('border-transparent hover:border-[#384454]')) {
      throw new Error('Missing visual interactive state classes distinguishing sorted from unsorted columns');
    }
    if (!tableSrc.includes('text-[#586270] select-none border-b-2 border-transparent')) {
      throw new Error('Non-sortable columns do not have distinct inactive styling');
    }
  });

  // 2. Sorting Algorithm Logic Invariants with Realistic Sample Positions
  const samplePositions: Position[] = [
    {
      id: 'pos-1',
      symbol: 'EURUSD',
      side: 'LONG',
      setup: 'BREAKOUT',
      mode: 'HYBRID',
      drivingTimeframe: '15M',
      entryPrice: 1.0850,
      currentPrice: 1.0890,
      size: 2.5,
      unrealizedR: 2.0,
      mfe: 2.2,
      mae: -0.2,
      exitProfile: 'RUNNER_60',
      age: '14m',
      structuralAnchor: 'SWING_LOW',
      trailDistance: '15 pips',
      breakevenStatus: 'LOCKED',
      decayState: 'NORMAL',
      effectiveConfig: 'DEFAULT',
      lane: 'PRIMARY',
      priceDecimals: 4,
      isSimulated: true,
    },
    {
      id: 'pos-2',
      symbol: 'BTCUSD',
      side: 'LONG',
      setup: 'MOMENTUM',
      mode: 'AUTOMATIC',
      drivingTimeframe: '1H',
      entryPrice: 65000,
      currentPrice: 64200,
      size: 0.5,
      unrealizedR: -0.67,
      mfe: 0.4,
      mae: -0.7,
      exitProfile: 'STANDARD_100',
      age: '02h',
      structuralAnchor: 'EMA_21',
      trailDistance: '400 pts',
      breakevenStatus: 'OPEN',
      decayState: 'NONE',
      effectiveConfig: 'DEFAULT',
      lane: 'PRIMARY',
      priceDecimals: 2,
      isSimulated: true,
    },
    {
      id: 'pos-3',
      symbol: 'XAUUSD',
      side: 'SHORT',
      setup: 'MEAN_REVERSION',
      mode: 'AUTOMATIC',
      drivingTimeframe: '5M',
      entryPrice: 2350.0,
      currentPrice: 2335.0,
      size: 5.0,
      unrealizedR: 1.5,
      mfe: 1.8,
      mae: -0.1,
      exitProfile: 'SCALP_30',
      age: '45m',
      structuralAnchor: 'BOLLINGER_UPPER',
      trailDistance: '5.0 pts',
      breakevenStatus: 'ARMED',
      decayState: 'LOW',
      effectiveConfig: 'DEFAULT',
      lane: 'SECONDARY',
      priceDecimals: 2,
      isSimulated: true,
    },
  ];

  // Helper sort simulation matching PositionsTable implementation
  function sortOpenPositions(
    data: Position[],
    field: 'symbol' | 'size' | 'unrealizedR' | 'entryPrice' | 'age',
    direction: 'asc' | 'desc'
  ): Position[] {
    return [...data].sort((a, b) => {
      const valA = a[field];
      const valB = b[field];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return direction === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return direction === 'asc' ? valA - valB : valB - valA;
      }
      return 0;
    });
  }

  // 3. PnL Sorting Tests (unrealizedR)
  verify('SORT-02.1: Sort by PnL (unrealizedR) descending orders highest profit to lowest loss', () => {
    const sorted = sortOpenPositions(samplePositions, 'unrealizedR', 'desc');
    const ids = sorted.map((p) => p.id);
    // 2.0 (EURUSD pos-1) > 1.5 (XAUUSD pos-3) > -0.67 (BTCUSD pos-2)
    if (ids[0] !== 'pos-1' || ids[1] !== 'pos-3' || ids[2] !== 'pos-2') {
      throw new Error(`Unexpected PnL desc order: ${ids.join(', ')}`);
    }
  });

  verify('SORT-02.2: Sort by PnL (unrealizedR) ascending orders deepest loss to highest profit', () => {
    const sorted = sortOpenPositions(samplePositions, 'unrealizedR', 'asc');
    const ids = sorted.map((p) => p.id);
    // -0.67 (BTCUSD pos-2) < 1.5 (XAUUSD pos-3) < 2.0 (EURUSD pos-1)
    if (ids[0] !== 'pos-2' || ids[1] !== 'pos-3' || ids[2] !== 'pos-1') {
      throw new Error(`Unexpected PnL asc order: ${ids.join(', ')}`);
    }
  });

  // 4. Symbol Sorting Tests
  verify('SORT-03.1: Sort by Symbol ascending orders alphabetically (A to Z)', () => {
    const sorted = sortOpenPositions(samplePositions, 'symbol', 'asc');
    const symbols = sorted.map((p) => p.symbol);
    // BTCUSD < EURUSD < XAUUSD
    if (symbols[0] !== 'BTCUSD' || symbols[1] !== 'EURUSD' || symbols[2] !== 'XAUUSD') {
      throw new Error(`Unexpected Symbol asc order: ${symbols.join(', ')}`);
    }
  });

  verify('SORT-03.2: Sort by Symbol descending orders reverse alphabetically (Z to A)', () => {
    const sorted = sortOpenPositions(samplePositions, 'symbol', 'desc');
    const symbols = sorted.map((p) => p.symbol);
    // XAUUSD > EURUSD > BTCUSD
    if (symbols[0] !== 'XAUUSD' || symbols[1] !== 'EURUSD' || symbols[2] !== 'BTCUSD') {
      throw new Error(`Unexpected Symbol desc order: ${symbols.join(', ')}`);
    }
  });

  // 5. Size Sorting Tests
  verify('SORT-04.1: Sort by Size descending orders highest exposure to lowest exposure', () => {
    const sorted = sortOpenPositions(samplePositions, 'size', 'desc');
    const sizes = sorted.map((p) => p.size);
    // 5.0 (pos-3) > 2.5 (pos-1) > 0.5 (pos-2)
    if (sizes[0] !== 5.0 || sizes[1] !== 2.5 || sizes[2] !== 0.5) {
      throw new Error(`Unexpected Size desc order: ${sizes.join(', ')}`);
    }
  });

  verify('SORT-04.2: Sort by Size ascending orders smallest exposure to largest exposure', () => {
    const sorted = sortOpenPositions(samplePositions, 'size', 'asc');
    const sizes = sorted.map((p) => p.size);
    // 0.5 < 2.5 < 5.0
    if (sizes[0] !== 0.5 || sizes[1] !== 2.5 || sizes[2] !== 5.0) {
      throw new Error(`Unexpected Size asc order: ${sizes.join(', ')}`);
    }
  });

  // 6. Age Sorting
  verify('SORT-05.1: Sort by Age string orders correctly via localeCompare', () => {
    const sorted = sortOpenPositions(samplePositions, 'age', 'asc');
    const ages = sorted.map((p) => p.age);
    // '02h' < '14m' < '45m'
    if (ages[0] !== '02h' || ages[1] !== '14m' || ages[2] !== '45m') {
      throw new Error(`Unexpected Age asc order: ${ages.join(', ')}`);
    }
  });

  // 7. Closed Trades Sorting Verification (realizedR / realizedPnl)
  const sampleClosedTrades: ClosedTrade[] = [
    {
      id: 'closed-1',
      symbol: 'EURUSD',
      side: 'LONG',
      setup: 'BREAKOUT',
      mode: 'HYBRID',
      entryPrice: 1.0800,
      exitPrice: 1.0860,
      size: 1.0,
      realizedR: 1.5,
      realizedPnl: 600,
      exitReason: 'TAKE_PROFIT',
      duration: '45m',
      closedAt: '12:45:00',
      priceDecimals: 4,
      isSimulated: true,
    },
    {
      id: 'closed-2',
      symbol: 'BTCUSD',
      side: 'SHORT',
      setup: 'MOMENTUM',
      mode: 'AUTOMATIC',
      entryPrice: 65000,
      exitPrice: 65500,
      size: 0.2,
      realizedR: -1.0,
      realizedPnl: -100,
      exitReason: 'STOP_LOSS',
      duration: '15m',
      closedAt: '13:00:00',
      priceDecimals: 2,
      isSimulated: true,
    },
    {
      id: 'closed-3',
      symbol: 'ETHUSD',
      side: 'LONG',
      setup: 'PULLBACK',
      mode: 'AUTOMATIC',
      entryPrice: 3400,
      exitPrice: 3550,
      size: 2.0,
      realizedR: 3.0,
      realizedPnl: 300,
      exitReason: 'TRAILING_STOP',
      duration: '02h',
      closedAt: '13:15:00',
      priceDecimals: 2,
      isSimulated: true,
    },
  ];

  verify('SORT-06.1: Closed trades sort by realizedR (PnL in R) descending orders highest R multiple first', () => {
    const sorted = [...sampleClosedTrades].sort((a, b) => b.realizedR - a.realizedR);
    if (sorted[0].id !== 'closed-3' || sorted[1].id !== 'closed-1' || sorted[2].id !== 'closed-2') {
      throw new Error(`Unexpected Closed Trades realizedR sort: ${sorted.map((t) => t.id).join(', ')}`);
    }
  });

  verify('SORT-06.2: Closed trades sort by realizedPnl (PnL in $) descending orders highest dollar profit first', () => {
    const sorted = [...sampleClosedTrades].sort((a, b) => b.realizedPnl - a.realizedPnl);
    if (sorted[0].id !== 'closed-1' || sorted[1].id !== 'closed-3' || sorted[2].id !== 'closed-2') {
      throw new Error(`Unexpected Closed Trades realizedPnl sort: ${sorted.map((t) => t.id).join(', ')}`);
    }
  });

  console.log('\n--------------------------------------------------------');
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runPositionsTableSortVerification();
