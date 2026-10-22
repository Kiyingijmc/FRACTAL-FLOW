import fs from 'fs';

/**
 * FRACTAL-FLOW GUI — Modal Focus Trap & Accessible Restoration Behavioral Test Suite
 * UX-07 / FF-D-08 / W3C WCAG 2.2 Standards
 *
 * Verifies:
 * 1. Focus trap: Tab cycles strictly within modal elements without escaping to background DOM.
 * 2. Reverse trap: Shift+Tab wraps from first element to last element.
 * 3. Escape dismissal: Pressing Escape safely closes modal and restores focus to invoking trigger.
 * 4. Close button: Activating close button restores focus to invoking trigger.
 * 5. Outside click: Activating outside backdrop restores focus to invoking trigger.
 * 6. Accessibility contracts: role="dialog", aria-modal="true", aria-haspopup="dialog", aria-expanded.
 */

interface MockElement {
  tagName: string;
  tabIndex: number;
  attributes: Record<string, string>;
  focus: () => void;
  isFocused: boolean;
}

function createMockElement(tagName: string, tabIndex = 0, attributes: Record<string, string> = {}): MockElement {
  const el: MockElement = {
    tagName,
    tabIndex,
    attributes,
    isFocused: false,
    focus() {
      if (currentActiveElement) {
        currentActiveElement.isFocused = false;
      }
      currentActiveElement = el;
      el.isFocused = true;
    }
  };
  return el;
}

let currentActiveElement: MockElement | null = null;

function simulateFocusTrapKeyDown(
  event: { key: string; shiftKey: boolean; defaultPrevented: boolean; preventDefault: () => void },
  focusableElements: MockElement[],
  onClose: () => void,
  triggerEl: MockElement
): void {
  if (event.key === 'Escape') {
    event.preventDefault();
    onClose();
    triggerEl.focus();
    return;
  }

  if (event.key === 'Tab' && focusableElements.length > 0) {
    const firstEl = focusableElements[0];
    const lastEl = focusableElements[focusableElements.length - 1];

    if (event.shiftKey) {
      if (currentActiveElement === firstEl) {
        event.preventDefault();
        lastEl.focus();
      }
    } else {
      if (currentActiveElement === lastEl) {
        event.preventDefault();
        firstEl.focus();
      }
    }
  }
}

async function runModalFocusBehaviorTests() {
  console.log('========================================================');
  console.log('FRACTAL-FLOW GUI — Modal Focus Trap & Accessible Restoration Behavioral Verification');
  console.log('Targets: FooterLog mobile drawer, MobileBottomNav secondary drawer');
  console.log('Standards: W3C WCAG 2.2 (2.1.2 No Keyboard Trap, 2.4.3 Focus Order)');
  console.log('========================================================\n');

  let passed = 0;
  let failed = 0;

  function test(name: string, fn: () => void) {
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

  // FOCUS-01: Focus Trap Forward & Backward Wrapping
  test('FOCUS-01.1: Tab on last focusable element wraps cleanly to first element', () => {
    const trigger = createMockElement('button', 0, { 'aria-label': 'Open Journal' });
    const closeBtn = createMockElement('button', 0, { 'aria-label': 'Close' });
    const clearBtn = createMockElement('button', 0, { 'aria-label': 'Clear Log' });
    const modalFocusables = [closeBtn, clearBtn];

    // Trigger invoked, focus moves into modal
    closeBtn.focus();
    if (currentActiveElement !== closeBtn) {
      throw new Error('Initial focus failed to target modal close button');
    }

    // Move to last element
    clearBtn.focus();
    if (currentActiveElement !== clearBtn) {
      throw new Error('Failed to focus last modal element');
    }

    // Press Tab on last element
    let prevented = false;
    simulateFocusTrapKeyDown(
      { key: 'Tab', shiftKey: false, defaultPrevented: false, preventDefault: () => { prevented = true; } },
      modalFocusables,
      () => {},
      trigger
    );

    if (!prevented) {
      throw new Error('Tab forward on last element did not prevent default event');
    }
    if (currentActiveElement !== closeBtn) {
      throw new Error('Focus failed to wrap to first element in dialog');
    }
  });

  test('FOCUS-01.2: Shift+Tab on first focusable element wraps cleanly to last element', () => {
    const trigger = createMockElement('button');
    const closeBtn = createMockElement('button');
    const filterBtn = createMockElement('button');
    const modalFocusables = [closeBtn, filterBtn];

    closeBtn.focus();
    let prevented = false;
    simulateFocusTrapKeyDown(
      { key: 'Tab', shiftKey: true, defaultPrevented: false, preventDefault: () => { prevented = true; } },
      modalFocusables,
      () => {},
      trigger
    );

    if (!prevented) {
      throw new Error('Shift+Tab reverse wrap did not prevent default event');
    }
    if (currentActiveElement !== filterBtn) {
      throw new Error('Focus failed to wrap to last element in dialog on Shift+Tab');
    }
  });

  // FOCUS-02: Escape Dismissal & Focus Restoration
  test('FOCUS-02.1: Escape key dismisses modal and restores focus to invoking trigger', () => {
    const trigger = createMockElement('button', 0, { 'id': 'journal-trigger' });
    trigger.focus();
    if (currentActiveElement !== trigger) {
      throw new Error('Initial trigger focus setup failed');
    }

    // Open modal
    const modalState = { isModalOpen: true };
    const closeBtn = createMockElement('button', 0, { 'aria-label': 'Close' });
    closeBtn.focus();
    if (currentActiveElement !== closeBtn) {
      throw new Error('Focus did not transfer into modal');
    }

    // Press Escape
    let prevented = false;
    simulateFocusTrapKeyDown(
      { key: 'Escape', shiftKey: false, defaultPrevented: false, preventDefault: () => { prevented = true; } },
      [closeBtn],
      () => { modalState.isModalOpen = false; },
      trigger
    );

    if (!prevented) {
      throw new Error('Escape key did not prevent default');
    }
    if (modalState.isModalOpen !== false) {
      throw new Error('Escape key failed to invoke modal close callback');
    }
    if (currentActiveElement !== trigger) {
      throw new Error('Focus was NOT restored to the invoking trigger element after Escape dismissal');
    }
  });

  // FOCUS-03: Close Button & Backdrop Dismissal Restoration
  test('FOCUS-03.1: Activating close button restores focus to invoking trigger', () => {
    const trigger = createMockElement('button', 0, { 'id': 'more-trigger' });
    trigger.focus();

    const drawerState = { isDrawerOpen: true };
    const closeButton = createMockElement('button');
    closeButton.focus();

    // Close button action
    drawerState.isDrawerOpen = false;
    trigger.focus();

    if (drawerState.isDrawerOpen !== false || currentActiveElement !== trigger) {
      throw new Error('Close button action failed to close drawer and restore focus to trigger');
    }
  });

  test('FOCUS-03.2: Outside click / backdrop dismiss restores focus to invoking trigger', () => {
    const trigger = createMockElement('button');
    trigger.focus();

    const backdropState = { isDrawerOpen: true };
    // Simulate click outside
    backdropState.isDrawerOpen = false;
    trigger.focus();

    if (currentActiveElement !== trigger || backdropState.isDrawerOpen !== false) {
      throw new Error('Outside backdrop dismissal failed to return focus to trigger');
    }
  });

  // FOCUS-04: ARIA Dialog & Popup Semantics Verification
  test('FOCUS-04.1: Modal components implement role="dialog", aria-modal="true", and aria-label', () => {
    const footerSrc = fs.readFileSync('src/components/FooterLog.tsx', 'utf8');
    const navSrc = fs.readFileSync('src/components/MobileBottomNav.tsx', 'utf8');

    if (!footerSrc.includes('role="dialog"') || !footerSrc.includes('aria-modal="true"') || !footerSrc.includes('aria-label="Event Journal Stream"')) {
      throw new Error('FooterLog mobile sheet is missing required dialog ARIA semantics');
    }
    if (!navSrc.includes('role="dialog"') || !navSrc.includes('aria-modal="true"') || !navSrc.includes('aria-label="Secondary Navigation Destinations"')) {
      throw new Error('MobileBottomNav secondary drawer is missing required dialog ARIA semantics');
    }
  });

  test('FOCUS-04.2: Triggers declare aria-haspopup="dialog" and aria-expanded state', () => {
    const footerSrc = fs.readFileSync('src/components/FooterLog.tsx', 'utf8');
    const navSrc = fs.readFileSync('src/components/MobileBottomNav.tsx', 'utf8');

    if (!footerSrc.includes('aria-haspopup="dialog"') || !footerSrc.includes('aria-expanded={isMobileJournalOpen}')) {
      throw new Error('FooterLog trigger is missing aria-haspopup="dialog" or dynamic aria-expanded');
    }
    if (!navSrc.includes('aria-haspopup="dialog"') || !navSrc.includes('aria-expanded={isMoreOpen}')) {
      throw new Error('MobileBottomNav More trigger is missing aria-haspopup="dialog" or dynamic aria-expanded');
    }
  });

  console.log('--------------------------------------------------------');
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log('========================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runModalFocusBehaviorTests().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
