/**
 * Keyboard shortcut safety guard.
 * Prevents rapid operator hotkeys ('T', 'B', 'C', 'X', 'Esc') from accidentally
 * firing while the operator is entering text into search inputs, filter boxes, or form fields.
 */
export function isSafeKeyboardShortcutTarget(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null;
  if (!target) return true;

  const tagName = target.tagName ? target.tagName.toUpperCase() : '';
  if (
    tagName === 'INPUT' ||
    tagName === 'TEXTAREA' ||
    tagName === 'SELECT' ||
    target.isContentEditable ||
    target.getAttribute('role') === 'textbox'
  ) {
    return false;
  }

  return true;
}
