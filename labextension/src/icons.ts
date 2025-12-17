import { LabIcon } from '@jupyterlab/ui-components';
import marimoIconSvg from '../style/marimo.svg';

export const marimoIcon = new LabIcon({
  name: '@jupyter-marimo-proxy:marimo',
  svgstr: marimoIconSvg
});

/**
 * SVG string as a data URI for use with kernelIconUrl
 */
export const marimoIconUrl = `data:image/svg+xml,${encodeURIComponent(marimoIconSvg)}`;

/**
 * Leaf emoji (🍃) SVG for new notebook launcher icon
 */
const leafIconSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <text x="50" y="75" font-size="80" text-anchor="middle" font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">🍃</text>
</svg>`;

export const leafIcon = new LabIcon({
  name: '@jupyter-marimo-proxy:leaf',
  svgstr: leafIconSvg
});

/**
 * Leaf icon as a data URI for use with kernelIconUrl
 */
export const leafIconUrl = `data:image/svg+xml,${encodeURIComponent(leafIconSvg)}`;
