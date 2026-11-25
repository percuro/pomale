/*
 * Colour roles of the theme: every pair that carries text or marks a control meets
 * WCAG 2.2 in the light and in the dark scheme. This file is identical in fahrma and
 * pomale and reads the project's own theme.css. See docs/design-language.md.
 */
import { describe, expect, it } from 'vitest';
import theme from './theme.css?raw';

/** [foreground, background, minimum ratio]: 4.5 for text, 3 for edges, fills and focus */
const PAIRS: [string, string, number][] = [
  ['text', 'bg', 4.5], ['text', 'surface', 4.5], ['text', 'surface-2', 4.5],
  ['muted', 'bg', 4.5], ['muted', 'surface', 4.5], ['muted', 'surface-2', 4.5],
  ['accent', 'bg', 4.5], ['accent', 'surface', 4.5],
  ['on-accent-fill', 'accent-fill', 4.5], ['on-accent-soft', 'accent-soft', 4.5],
  ['on-highlight', 'highlight', 4.5],
  ['on-chrome', 'chrome', 4.5], ['chrome-muted', 'chrome', 4.5], ['chrome-brand', 'chrome', 4.5],
  ['chrome-focus', 'chrome', 3],
  ['feature-text', 'feature-bg', 4.5], ['feature-muted', 'feature-bg', 4.5], ['feature-accent', 'feature-bg', 4.5],
  ['on-feature-fill', 'feature-fill', 4.5], ['feature-danger', 'feature-bg', 4.5],
  ['feature-focus', 'feature-bg', 3], ['feature-fill', 'feature-bg', 3],
  ['plus', 'surface', 4.5], ['minus', 'surface', 4.5], ['plus', 'bg', 4.5], ['minus', 'bg', 4.5],
  ['on-danger', 'danger', 4.5], ['danger-text', 'surface', 4.5], ['danger-text', 'bg', 4.5], ['danger-text', 'danger-bg', 4.5],
  ['warn-text', 'warn-bg', 4.5], ['info-text', 'info-bg', 4.5], ['ok-text', 'ok-bg', 4.5],
  ['border-strong', 'surface', 3], ['border-strong', 'bg', 3],
  ['accent-fill', 'surface', 3], ['accent-fill', 'bg', 3],
  ['focus', 'surface', 3], ['focus', 'bg', 3], ['focus', 'surface-2', 3],
];

/** Roles every theme defines; fahrma and pomale use the same names. */
const ROLES = [
  'bg', 'surface', 'surface-2', 'text', 'muted', 'border', 'border-strong',
  'accent', 'accent-fill', 'on-accent-fill', 'accent-soft', 'on-accent-soft', 'highlight', 'on-highlight',
  'chrome', 'on-chrome', 'chrome-muted', 'chrome-brand', 'chrome-border', 'chrome-focus',
  'feature-bg', 'feature-text', 'feature-muted', 'feature-border', 'feature-accent', 'feature-fill',
  'on-feature-fill', 'feature-danger', 'feature-focus',
  'plus', 'minus', 'danger', 'on-danger', 'danger-text', 'danger-bg',
  'warn-bg', 'warn-text', 'info-bg', 'info-text', 'ok-bg', 'ok-text',
  'focus', 'shadow',
  'radius-s', 'radius-m', 'radius-l', 'radius-button', 'radius-field', 'radius-pill', 'font-display',
];

const blocks = [...theme.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/:root\s*\{([^}]*)\}/g)].map(
  (block) => Object.fromEntries([...block[1].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)].map((d) => [d[1], d[2].trim()])),
);
const [light, darkOnly] = blocks;
const schemes: Record<string, Record<string, string>> = { light, dark: { ...light, ...darkOnly } };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('theme', () => {
  it('has one light and one dark block', () => {
    expect(blocks).toHaveLength(2);
  });

  it('defines exactly the shared roles', () => {
    expect(Object.keys(light).sort()).toEqual([...ROLES].sort());
  });

  it('gives every colour a dark value', () => {
    const colours = Object.keys(light).filter((role) => light[role].startsWith('#'));
    expect(colours.filter((role) => !(role in darkOnly))).toEqual([]);
  });

  for (const scheme of ['light', 'dark']) {
    it(`meets the contrast minimum in the ${scheme} scheme`, () => {
      const roles = schemes[scheme];
      const failed = PAIRS.filter(([fg, bg, min]) => contrast(roles[fg], roles[bg]) < min).map(
        ([fg, bg, min]) => `${fg} on ${bg}: ${contrast(roles[fg], roles[bg]).toFixed(2)} < ${min}`,
      );
      expect(failed).toEqual([]);
    });
  }
});
