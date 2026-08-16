/**
 * Clerk theming — makes the sign-in modal read as part of Dark Glass v1
 * rather than a third-party widget dropped on top of it.
 *
 * `dark` from @clerk/themes is the base so every unstyled surface (the
 * backdrop, dividers, secondary text) starts from a dark palette instead of
 * Clerk's light default; `variables` then overrides it with this app's actual
 * tokens (see index.css for the source of truth), and `elements` fixes the
 * handful of things variables can't reach - square corners and the hairline
 * card border this whole design system is built on.
 */
import { dark } from '@clerk/themes'
import type { Appearance } from '@clerk/types'

const INK_950 = '#0A0A0A'
const INK_900 = '#0D0D0D'
const INK_800 = '#141414'
const LINE = '#272727'
const MIST_50 = '#FFFFFF'
const MIST_200 = '#E3E3E3'
const MIST_500 = '#6B6B6B'
const VIOLET_500 = '#8A05FF'
const DANGER = '#FF5C5C'

export const clerkAppearance: Appearance = {
  baseTheme: dark,
  variables: {
    colorBackground: INK_900,
    colorPrimary: MIST_50,
    colorForeground: MIST_50,
    colorText: MIST_50,
    colorTextSecondary: MIST_500,
    colorInputBackground: INK_800,
    colorInputForeground: MIST_50,
    colorNeutral: MIST_200,
    colorDanger: DANGER,
    colorBorder: LINE,
    // No radius token in this system - see ui.ts's header comment.
    borderRadius: '0px',
    fontFamily: '"Switzer", ui-sans-serif, system-ui, sans-serif',
    fontFamilyButtons: '"Switzer", ui-sans-serif, system-ui, sans-serif',
  },
  elements: {
    // Clerk's own card shadow/radius survive `variables.borderRadius` in a
    // couple of places; pinned directly rather than fighting the cascade.
    card: {
      backgroundColor: INK_900,
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      boxShadow: 'none',
    },
    modalBackdrop: {
      backgroundColor: 'rgba(10, 10, 10, 0.8)',
    },
    headerTitle: {
      fontFamily: '"General Sans", ui-sans-serif, system-ui, sans-serif',
      fontWeight: 300,
      color: MIST_50,
    },
    headerSubtitle: {
      color: MIST_500,
    },
    // White-on-black, matching BTN_PRIMARY in ui.ts - the only filled button
    // this design system uses.
    formButtonPrimary: {
      backgroundColor: MIST_50,
      color: INK_950,
      borderRadius: 0,
      fontSize: '16px',
      boxShadow: 'none',
      '&:hover': { backgroundColor: MIST_200 },
      '&:focus': { boxShadow: 'none' },
    },
    formFieldInput: {
      backgroundColor: INK_800,
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      color: MIST_50,
      '&:focus': {
        borderColor: VIOLET_500,
        boxShadow: `0 0 0 1px ${VIOLET_500}`,
      },
    },
    formFieldLabel: {
      color: MIST_200,
    },
    // Google/GitHub/etc buttons - hairline outline like BTN_OUTLINE, not a
    // filled surface, so they read as secondary next to the primary action.
    // Two different components depending on how many providers are enabled:
    // a labeled full-width button when there's one, unlabeled icon buttons in
    // a row when there's several (which is what this app's five providers
    // render as) - both styled the same, hairline-outlined like BTN_OUTLINE.
    socialButtonsBlockButton: {
      backgroundColor: 'transparent',
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      color: MIST_50,
      '&:hover': { backgroundColor: 'rgba(255,255,255,0.05)' },
    },
    socialButtonsBlockButtonText: {
      color: MIST_50,
      fontSize: '15px',
    },
    socialButtonsIconButton: {
      backgroundColor: 'transparent',
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      '&:hover': { backgroundColor: 'rgba(255,255,255,0.05)' },
    },
    dividerLine: { backgroundColor: LINE },
    dividerText: { color: MIST_500 },
    footer: {
      backgroundColor: INK_900,
      borderTop: `1px solid ${LINE}`,
    },
    footerActionText: { color: MIST_500 },
    footerActionLink: { color: VIOLET_500, '&:hover': { color: VIOLET_500 } },
    identityPreview: {
      backgroundColor: INK_800,
      border: `1px solid ${LINE}`,
      borderRadius: 0,
    },
    formFieldAction: { color: VIOLET_500 },
    otpCodeFieldInput: {
      backgroundColor: INK_800,
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      color: MIST_50,
    },
    avatarBox: { borderRadius: 0 },
    userButtonPopoverCard: {
      backgroundColor: INK_900,
      border: `1px solid ${LINE}`,
      borderRadius: 0,
      boxShadow: 'none',
    },
    userButtonPopoverActionButton: {
      color: MIST_200,
      '&:hover': { backgroundColor: 'rgba(255,255,255,0.05)' },
    },
    badge: {
      backgroundColor: 'rgba(138, 5, 255, 0.15)',
      color: '#D1B8FF',
      borderRadius: 0,
    },
  },
}
