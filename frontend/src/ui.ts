/**
 * The class strings that make up the violet/white/black system.
 *
 * Nine files were repeating the same twelve recipes, so they live here once.
 * Sizes, weights and tracking come from render.com; see the header comment in
 * index.css for what was measured and what was substituted.
 *
 * Everything is square — no radius token, because there is no radius.
 */

/* ---- Type ---------------------------------------------------------- */

/** Page title. Light, large, tight — weight carries no emphasis at this size. */
export const H1 =
  'font-display text-[32px] font-light leading-[1.05] tracking-[-.02em] text-mist-50 sm:text-[40px]'

/** The line under an H1. */
export const SUB = 'mt-3 text-[18px] leading-[1.6] text-mist-500'

/** Card and section heading. */
export const H2 = 'font-display text-[18px] font-normal text-mist-50'

/** All-caps section label. */
export const EYEBROW = 'text-[12px] font-medium uppercase tracking-[.12em] text-mist-500'

/** Timestamps, counts, anything secondary. */
export const META = 'text-[14px] text-mist-500'

/* ---- Buttons -------------------------------------------------------- */

const BTN_BASE = 'inline-flex items-center justify-center gap-2.5 text-[16px] transition disabled:cursor-not-allowed disabled:opacity-40'

/** White on black. The only primary action on a view. */
export const BTN_PRIMARY = `${BTN_BASE} bg-mist-50 px-[18px] py-2.5 text-ink-950 hover:bg-mist-200`

/** Outlined in white. Sits next to a primary without competing. */
export const BTN_OUTLINE = `${BTN_BASE} border border-mist-50 px-[18px] py-2.5 text-mist-50 hover:bg-mist-50/10`

/** Hairline. For Refresh, Cancel, and other low-stakes controls. */
export const BTN_QUIET = `${BTN_BASE} border border-line bg-ink-900 px-[15px] py-2 text-[15px] text-mist-200 hover:border-mist-500 hover:text-mist-50`

/** Destructive, always outlined — nothing red is ever a filled button. */
export const BTN_DANGER = `${BTN_BASE} border border-danger/50 px-[15px] py-2 text-[15px] text-danger hover:bg-danger/10`

/* ---- Fields --------------------------------------------------------- */

export const FIELD =
  'w-full border border-line bg-ink-800 px-4 py-3 text-[16px] text-mist-50 transition placeholder:text-mist-500 focus:border-violet-500 focus:outline-none'

export const LABEL = 'block text-[14px] text-mist-200'

/* ---- Banners -------------------------------------------------------- */

export const BANNER_DANGER = 'border border-danger/40 bg-danger/[0.07] px-4 py-3.5'
export const BANNER_OK = 'border border-violet-500/40 bg-violet-500/[0.08] px-4 py-3.5'
export const BANNER_QUIET = 'border border-line bg-ink-900 px-4 py-3.5'
