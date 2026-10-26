/**
 * FRACTAL-FLOW Keyboard Shortcut Safety Guard
 *
 * Invariants:
 * 1. Suppress all shortcuts when focus is in any editable or text-entry target.
 * 2. Suppress shortcuts during IME composition (isComposing || keyCode === 229).
 * 3. Suppress repeated keydown events (event.repeat) for command triggers to prevent key chatter.
 * 4. Reject unintended modifier combinations (e.g. accidental Alt+key or Ctrl+key if not required).
 * 5. Suppress destructive or command actions when a modal is open or another command is in flight.
 */

export interface KeyboardSafetyContext {
  isModalOpen?: boolean;
  isCommandInFlight?: boolean;
}

export interface ShortcutValidationOptions {
  requireCtrlOrMeta?: boolean;
  requireShift?: boolean;
  requireAlt?: boolean;
  allowRepeat?: boolean;
}

/**
 * Checks if the event target is an interactive text-entry field or editable element.
 */
export function isSafeKeyboardShortcutTarget(event: KeyboardEvent): boolean {
  if (!event) return false;
  const target = event.target as HTMLElement | null;
  if (!target) return true;

  const tagName = target.tagName ? target.tagName.toUpperCase() : '';
  if (
    tagName === 'INPUT' ||
    tagName === 'TEXTAREA' ||
    tagName === 'SELECT' ||
    Boolean(target.isContentEditable) ||
    (typeof target.getAttribute === 'function' && (
      target.getAttribute('role') === 'textbox' ||
      target.getAttribute('role') === 'combobox' ||
      target.getAttribute('role') === 'searchbox'
    ))
  ) {
    return false;
  }
  return true;
}

/**
 * Validates whether a KeyboardEvent is safe and matches modifier constraints.
 */
export function isValidShortcutEvent(
  event: KeyboardEvent,
  options: ShortcutValidationOptions = {}
): boolean {
  if (!event) return false;

  // 1. Text input target guard
  if (!isSafeKeyboardShortcutTarget(event)) {
    return false;
  }

  // 2. IME composition guard (crucial for CJK input and virtual keyboards)
  if (event.isComposing || event.keyCode === 229) {
    return false;
  }

  // 3. Key chatter / repeated keydown guard
  if (event.repeat && !options.allowRepeat) {
    return false;
  }

  // 4. Modifier combination validation
  const hasCtrlOrMeta = event.ctrlKey || event.metaKey;
  if (options.requireCtrlOrMeta && !hasCtrlOrMeta) {
    return false;
  }
  if (!options.requireCtrlOrMeta && hasCtrlOrMeta) {
    // If Ctrl/Meta is pressed but not requested, reject to prevent hijacking browser shortcuts
    return false;
  }

  if (Boolean(options.requireShift) !== Boolean(event.shiftKey)) {
    return false;
  }

  if (Boolean(options.requireAlt) !== Boolean(event.altKey)) {
    return false;
  }

  return true;
}

/**
 * Comprehensive shortcut gate integrating application state (modal open, command in flight).
 */
export function isKeyboardShortcutAllowed(
  event: KeyboardEvent,
  context: KeyboardSafetyContext = {},
  options: ShortcutValidationOptions = {}
): boolean {
  if (context.isModalOpen) {
    return false;
  }
  if (context.isCommandInFlight) {
    return false;
  }
  return isValidShortcutEvent(event, options);
}
