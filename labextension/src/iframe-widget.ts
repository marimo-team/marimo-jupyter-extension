import { IFrame, MainAreaWidget } from '@jupyterlab/apputils';
import { UUID } from '@lumino/coreutils';
import type { ISignal } from '@lumino/signaling';
import { leafIcon } from './icons';

/**
 * Sandbox settings for marimo IFrames.
 * Centralized here to ensure consistency across all IFrame creation paths.
 */
const IFRAME_SANDBOX_SETTINGS: IFrame.SandboxExceptions[] = [
  'allow-same-origin',
  'allow-scripts',
  'allow-forms',
  'allow-modals',
  'allow-popups',
  'allow-downloads',
];

/**
 * Tracked widget with metadata for session management.
 */
interface TrackedWidget {
  widget: MainAreaWidget<IFrame>;
  originalUrl: string;
  widgetId: string;
  /** Whether this widget has been seen in the active sessions list at least once */
  wasConnected: boolean;
  /** Whether this is a new notebook (not file-based) - controls title modification on disconnect */
  isNewNotebook: boolean;
}

/**
 * Map of initializationId to tracked widget for managing new notebooks.
 * Used to update tab titles and handle disconnection states.
 */
const widgetsByInitId = new Map<string, TrackedWidget>();

/**
 * Map of filePath to tracked widget for managing file-based notebooks.
 * Used to handle disconnection states for notebooks opened from files.
 */
const widgetsByFilePath = new Map<string, TrackedWidget>();

/**
 * Get an existing widget for a file path, if one exists.
 */
export function getWidgetByFilePath(
  filePath: string,
): MainAreaWidget<IFrame> | undefined {
  return widgetsByFilePath.get(filePath)?.widget;
}

/**
 * Refresh a widget's iframe by resetting its URL.
 * This forces marimo to reconnect.
 */
export function refreshWidgetByFilePath(filePath: string): void {
  const tracked = widgetsByFilePath.get(filePath);
  if (tracked) {
    // Reset URL to force iframe reload
    tracked.widget.content.url = tracked.originalUrl;
  }
}

/**
 * Generate a data URL containing the disconnected page HTML.
 */
function createDisconnectedPageUrl(widgetId: string): string {
  const html = `
<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      background: #f5f5f5;
      color: #333;
    }
    .icon {
      font-size: 64px;
      margin-bottom: 16px;
    }
    h2 {
      margin: 0 0 8px 0;
      font-weight: 500;
    }
    p {
      margin: 0 0 24px 0;
      color: #666;
    }
    button {
      background: #2196f3;
      color: white;
      border: none;
      padding: 12px 24px;
      font-size: 14px;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover {
      background: #1976d2;
    }
  </style>
</head>
<body>
  <div class="icon">🌿</div>
  <h2>Session Disconnected</h2>
  <p>The marimo session has been closed.</p>
  <button onclick="reconnect()">Reconnect</button>
  <script>
    function reconnect() {
      window.parent.postMessage({ type: 'marimo-reconnect', widgetId: '${widgetId}' }, '*');
    }
  </script>
</body>
</html>
  `.trim();
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

/**
 * Initialize the message listener for reconnect requests.
 * Should be called once when the extension loads.
 */
let messageListenerInitialized = false;

function initializeMessageListener(): void {
  if (messageListenerInitialized) {
    return;
  }
  messageListenerInitialized = true;

  window.addEventListener('message', (event: MessageEvent<unknown>) => {
    const data = event.data as { type?: string; widgetId?: string } | null;
    if (data?.type === 'marimo-reconnect' && data?.widgetId) {
      const widgetId = data.widgetId;
      // Find the tracked widget by its widgetId in both maps
      for (const tracked of [
        ...widgetsByInitId.values(),
        ...widgetsByFilePath.values(),
      ]) {
        if (tracked.widgetId === widgetId) {
          // Restore the original URL to reconnect
          tracked.widget.content.url = tracked.originalUrl;
          // Remove "(disconnected)" from title if present (only for new notebooks)
          if (
            tracked.isNewNotebook &&
            tracked.widget.title.label.endsWith(' (disconnected)')
          ) {
            tracked.widget.title.label = tracked.widget.title.label.replace(
              ' (disconnected)',
              '',
            );
          }
          break;
        }
      }
    }
  });
}

/**
 * Result from createMarimoIFrame containing the IFrame and tracking metadata.
 */
export interface MarimoIFrameResult {
  /** The configured IFrame ready for use */
  iframe: IFrame;
  /** The final URL set on the IFrame */
  url: string;
  /** The initialization ID for new notebooks, or null for file-based */
  initId: string | null;
}

/**
 * Create a marimo IFrame with proper sandbox settings and URL configuration.
 * This is the single entry point for creating marimo IFrames - ensures
 * consistent sandbox settings and URL building across all code paths.
 *
 * Note: Callers are responsible for registering the widget for tracking
 * using registerWidgetForTracking() after wrapping in a widget.
 */
export function createMarimoIFrame(
  baseUrl: string,
  options: { filePath?: string; initId?: string } = {},
): MarimoIFrameResult {
  const iframe = new IFrame({
    sandbox: IFRAME_SANDBOX_SETTINGS,
  });
  iframe.addClass('jp-MarimoWidget');

  // Generate initId if not file-based (and not provided)
  const initId = options.filePath
    ? null
    : (options.initId ?? `__new__${UUID.uuid4()}`);

  // Build URL: file-based uses encoded filePath, new notebooks use initId
  const url = options.filePath
    ? `${baseUrl}?file=${encodeURIComponent(options.filePath)}`
    : `${baseUrl}?file=${initId}`;

  iframe.url = url;
  return { iframe, url, initId };
}

/**
 * Create a marimo widget that embeds the editor in an iframe.
 * Uses createMarimoIFrame internally for consistent IFrame creation.
 */
export function createMarimoWidget(
  baseUrl: string,
  options: { filePath?: string; label?: string } = {},
): MainAreaWidget<IFrame> {
  const { filePath, label } = options;

  // Use centralized IFrame creation
  const {
    iframe: content,
    url: finalUrl,
    initId,
  } = createMarimoIFrame(baseUrl, { filePath });

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

  // Track widgets for disconnection handling
  if (initId) {
    // New notebook - track by initializationId
    const widgetId = `marimo-widget-${UUID.uuid4()}`;
    widgetsByInitId.set(initId, {
      widget,
      originalUrl: finalUrl,
      widgetId,
      wasConnected: false,
      isNewNotebook: true,
    });
    widget.disposed.connect(() => {
      widgetsByInitId.delete(initId);
    });
    initializeMessageListener();
  } else if (filePath) {
    // File-based notebook - track by filePath
    registerWidgetForTracking(widget, filePath, finalUrl);
  }

  return widget;
}

/**
 * Update widget titles based on running session data.
 * Called by the sidebar when it polls for running notebooks.
 * Also detects disconnected sessions and shows reconnect UI.
 */
export function updateWidgetTitles(
  sessions: { initializationId: string; name: string; path: string }[],
): void {
  // Build sets of active identifiers for quick lookup
  const activeInitIds = new Set(sessions.map((s) => s.initializationId));
  const activePaths = new Set(sessions.map((s) => s.path));

  // Update titles for active sessions (initId-based widgets)
  for (const session of sessions) {
    const tracked = widgetsByInitId.get(session.initializationId);
    if (tracked && session.name && session.path) {
      const { widget } = tracked;
      // Mark as connected now that we've seen it in the sessions list
      tracked.wasConnected = true;
      // Remove "(disconnected)" suffix if session is back (only for new notebooks)
      let currentLabel = widget.title.label;
      if (tracked.isNewNotebook && currentLabel.endsWith(' (disconnected)')) {
        currentLabel = currentLabel.replace(' (disconnected)', '');
        widget.title.label = currentLabel;
      }
      // Update title if it differs
      if (currentLabel !== session.name) {
        widget.title.label = session.name;
        widget.title.caption = `marimo: ${session.path}`;
      }
    }
  }

  // Mark file-based widgets as connected when their path appears in sessions
  for (const session of sessions) {
    const tracked = widgetsByFilePath.get(session.path);
    if (tracked) {
      tracked.wasConnected = true;
      // Note: file-based widgets (isNewNotebook: false) don't add "(disconnected)"
      // suffix, so we don't need to remove it here
    }
  }

  // Check for disconnected widgets (initId-based)
  // Only show disconnected if the widget was previously connected
  for (const [initId, tracked] of widgetsByInitId.entries()) {
    if (!activeInitIds.has(initId) && tracked.wasConnected) {
      showDisconnectedPage(tracked);
    }
  }

  // Check for disconnected widgets (filePath-based)
  // Only show disconnected if the widget was previously connected
  for (const [filePath, tracked] of widgetsByFilePath.entries()) {
    if (!activePaths.has(filePath) && tracked.wasConnected) {
      showDisconnectedPage(tracked);
    }
  }
}

/**
 * Show the disconnected page for a tracked widget.
 */
function showDisconnectedPage(tracked: TrackedWidget): void {
  const { widget, widgetId, isNewNotebook } = tracked;
  const disconnectedUrl = createDisconnectedPageUrl(widgetId);

  // Only update if not already showing disconnected page
  if (widget.content.url !== disconnectedUrl) {
    widget.content.url = disconnectedUrl;
    // Only add "(disconnected)" suffix for new notebooks
    // File-based notebooks shouldn't modify title (causes file rename in DocumentWidget)
    if (isNewNotebook && !widget.title.label.endsWith(' (disconnected)')) {
      widget.title.label = `${widget.title.label} (disconnected)`;
    }
  }
}

/**
 * Widget-like interface for registration.
 * Allows MarimoWidgetFactory widgets to be registered for tracking.
 */
interface WidgetLike {
  content: IFrame;
  title: { label: string; caption: string };
  disposed: ISignal<unknown, void>;
}

/**
 * Register an externally-created widget for disconnection tracking.
 * Used by MarimoWidgetFactory for widgets created via "Open With" menu.
 */
export function registerWidgetForTracking(
  widget: WidgetLike,
  filePath: string,
  originalUrl: string,
): void {
  const widgetId = `marimo-widget-${UUID.uuid4()}`;
  widgetsByFilePath.set(filePath, {
    widget: widget as unknown as MainAreaWidget<IFrame>,
    originalUrl,
    widgetId,
    wasConnected: false,
    isNewNotebook: false,
  });
  widget.disposed.connect(() => {
    widgetsByFilePath.delete(filePath);
  });
  initializeMessageListener();
}
