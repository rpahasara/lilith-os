/**
 * Props for a control whose feature does not exist yet.
 *
 * Uses the native `disabled` attribute, so the browser itself blocks mouse,
 * keyboard (Enter/Space) and focus: nothing can activate it, and no handler is
 * attached. Assistive technology still sees the control by name, reports it as
 * unavailable, and reads the reason from `title` (its accessible description).
 *
 * Use this instead of a button that silently does nothing. When the feature is
 * built, delete the spread and wire a real handler.
 */
export function unavailable(feature: string) {
  return {
    disabled: true,
    title: `${feature} isn't available yet`,
    "data-unavailable": "",
  } as const;
}
