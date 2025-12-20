import { MainAreaWidget, IFrame } from '@jupyterlab/apputils';
import { UUID } from '@lumino/coreutils';
import { leafIcon } from './icons';

/**
 * Map of initializationId to widget for tracking new notebooks.
 * Used to update tab titles when notebook names are set.
 */
const widgetsByInitId = new Map<string, MainAreaWidget<IFrame>>();

/**
 * Create a marimo widget that embeds the editor in an iframe.
 */
export function createMarimoWidget(
  url: string,
  options: { filePath?: string; label?: string } = {},
): MainAreaWidget<IFrame> {
  const { filePath, label } = options;

  const content = new IFrame({
    sandbox: [
      'allow-same-origin',
      'allow-scripts',
      'allow-forms',
      'allow-modals',
      'allow-popups',
      'allow-downloads',
    ],
  });

  // Generate initializationId for new notebooks (include __new__ prefix to match marimo API)
  const initId = filePath ? null : `__new__${UUID.uuid4()}`;
  content.url = filePath ? url : `${url}?file=${initId}`;
  content.addClass('jp-MarimoWidget');

  const widget = new MainAreaWidget({ content });
  widget.id = `marimo-${UUID.uuid4()}`;

  if (label) {
    widget.title.label = label;
  } else if (filePath) {
    const parts = filePath.split('/');
    widget.title.label = parts[parts.length - 1] || 'marimo';
  } else {
    widget.title.label = 'marimo';
  }

  widget.title.closable = true;
  widget.title.icon = leafIcon;
  widget.title.caption = filePath ? `marimo: ${filePath}` : 'marimo Editor';

  // Track new notebooks by their initializationId
  if (initId) {
    widgetsByInitId.set(initId, widget);
    // Clean up when widget is disposed
    widget.disposed.connect(() => {
      widgetsByInitId.delete(initId);
    });
  }

  return widget;
}

/**
 * Update widget titles based on running session data.
 * Called by the sidebar when it polls for running notebooks.
 */
export function updateWidgetTitles(
  sessions: { initializationId: string; name: string; path: string }[],
): void {
  for (const session of sessions) {
    const widget = widgetsByInitId.get(session.initializationId);
    if (widget && session.name && session.path) {
      // Only update file-based notebooks, keep user-provided titles for unsaved notebooks
      if (widget.title.label !== session.name) {
        widget.title.label = session.name;
        widget.title.caption = `marimo: ${session.path}`;
      }
    }
  }
}
