import { PageConfig } from '@jupyterlab/coreutils';
import type { CommandRegistry } from '@lumino/commands';
import { Widget } from '@lumino/widgets';
import { marimoIcon } from './icons';
import { updateWidgetTitles } from './iframe-widget';

const SIDEBAR_CLASS = 'jp-MarimoSidebar';

interface RunningSession {
  sessionId: string;
  name: string;
  path: string;
  initializationId: string;
  lastModified: number;
}

/**
 * A sidebar panel for marimo quick actions.
 */
export class MarimoSidebar extends Widget {
  private _commands: CommandRegistry;
  private _sessionsContainer: HTMLElement | null = null;
  private _refreshInterval: number | null = null;
  private _statusDot: HTMLElement | null = null;
  private _statusText: HTMLElement | null = null;
  private _serverControlsContainer: HTMLElement | null = null;
  private _startServerContainer: HTMLElement | null = null;

  constructor(commands: CommandRegistry) {
    super();
    this._commands = commands;
    this.id = 'marimo-sidebar';
    this.addClass(SIDEBAR_CLASS);
    this.title.icon = marimoIcon;
    this.title.caption = 'marimo';

    this._buildUI();
    this._startPolling();
  }

  dispose(): void {
    if (this._refreshInterval !== null) {
      window.clearInterval(this._refreshInterval);
    }
    super.dispose();
  }

  private _getMarimoBaseUrl(): string {
    const baseUrl = PageConfig.getBaseUrl();
    return `${baseUrl}marimo/`;
  }

  private _startPolling(): void {
    // Initial check
    this._refreshStatus();
    // Refresh status and sessions every 5 seconds
    this._refreshInterval = window.setInterval(() => {
      this._refreshStatus();
    }, 5000);
  }

  private async _refreshStatus(): Promise<void> {
    const isRunning = await this._checkServerStatus();
    this._updateServerStatus(isRunning);
    if (isRunning) {
      await this._refreshSessions();
    } else {
      this._updateSessionsList([]);
    }
  }

  private async _refreshSessions(): Promise<void> {
    try {
      const baseUrl = this._getMarimoBaseUrl();
      const response = await fetch(`${baseUrl}api/home/running_notebooks`, {
        method: 'POST',
        credentials: 'same-origin',
      });
      if (response.ok) {
        const data = (await response.json()) as {
          files?: RunningSession[];
        };
        const sessions = data.files ?? [];
        this._updateSessionsList(sessions);
        // Update widget tab titles based on session names
        updateWidgetTitles(sessions);
      }
    } catch {
      // Silently fail - server may not be running
    }
  }

  private async _shutdownSession(sessionId: string): Promise<void> {
    try {
      const baseUrl = this._getMarimoBaseUrl();
      const response = await fetch(`${baseUrl}api/home/shutdown_session`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId }),
      });
      if (response.ok) {
        // Refresh the list after shutdown
        await this._refreshSessions();
      }
    } catch {
      // Silently fail - session may have already ended
    }
  }

  private async _isServerHealthy(): Promise<boolean> {
    try {
      const baseUrl = this._getMarimoBaseUrl();
      const response = await fetch(`${baseUrl}health`, {
        method: 'GET',
        credentials: 'same-origin',
      });
      if (response.ok) {
        const data = (await response.json()) as {
          status: string;
        };
        return data.status === 'healthy';
      }
      return false;
    } catch {
      return false;
    }
  }

  private async _checkServerStatus(): Promise<boolean> {
    return this._isServerHealthy();
  }

  private _updateServerStatus(isRunning: boolean): void {
    if (this._statusDot && this._statusText) {
      if (isRunning) {
        this._statusDot.className = 'jp-MarimoSidebar-statusDot jp-mod-ready';
        this._statusText.textContent = 'Running';
      } else {
        this._statusDot.className = 'jp-MarimoSidebar-statusDot jp-mod-error';
        this._statusText.textContent = 'Stopped';
      }
    }
    if (this._serverControlsContainer) {
      this._serverControlsContainer.style.display = isRunning
        ? 'flex'
        : 'none';
    }
    if (this._startServerContainer) {
      this._startServerContainer.style.display = isRunning ? 'none' : 'flex';
    }
  }

  private async _startServer(): Promise<void> {
    if (this._statusText) {
      this._statusText.textContent = 'Starting...';
    }

    try {
      // Making a request to the proxy URL triggers jupyter-server-proxy to start the process
      const maxAttempts = 15;
      for (let i = 0; i < maxAttempts; i++) {
        if (await this._isServerHealthy()) {
          this._updateServerStatus(true);
          await this._refreshSessions();
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }

      // If we get here, the server didn't start successfully
      this._updateServerStatus(false);
    } catch {
      this._updateServerStatus(false);
    }
  }

  private async _restartServer(): Promise<void> {
    const confirmRestart = window.confirm(
      'Are you sure you want to restart the marimo server? All running sessions will be interrupted.',
    );
    if (!confirmRestart) {
      return;
    }

    if (this._statusText) {
      this._statusText.textContent = 'Restarting...';
    }
    if (this._statusDot) {
      this._statusDot.className = 'jp-MarimoSidebar-statusDot jp-mod-warning';
    }
    this._updateSessionsList([]);

    try {
      const baseUrl = PageConfig.getBaseUrl();
      // Call the restart endpoint which properly manages the proxy state
      const response = await fetch(`${baseUrl}marimo-tools/restart`, {
        method: 'POST',
        credentials: 'same-origin',
      });

      if (!response.ok) {
        throw new Error('Restart request failed');
      }

      // Wait for the server to come back up
      await this._waitForServer();
    } catch {
      this._updateServerStatus(false);
    }
  }

  private async _waitForServer(): Promise<void> {
    const maxAttempts = 20;

    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      if (await this._isServerHealthy()) {
        this._updateServerStatus(true);
        await this._refreshSessions();
        return;
      }
    }

    // If we get here, the server didn't come back up
    this._updateServerStatus(false);
  }

  private _updateSessionsList(sessions: RunningSession[]): void {
    if (!this._sessionsContainer) {
      return;
    }

    this._sessionsContainer.innerHTML = '';

    if (sessions.length === 0) {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'jp-MarimoSidebar-emptyMessage';
      emptyMsg.textContent = 'No running sessions';
      this._sessionsContainer.appendChild(emptyMsg);
      return;
    }

    for (const session of sessions) {
      const sessionItem = document.createElement('div');
      sessionItem.className = 'jp-MarimoSidebar-sessionItem';

      const sessionInfo = document.createElement('div');
      sessionInfo.className = 'jp-MarimoSidebar-sessionInfo';

      const sessionName = document.createElement('span');
      sessionName.className = 'jp-MarimoSidebar-sessionName';
      sessionName.textContent = session.name;
      sessionName.title = session.path;
      sessionInfo.appendChild(sessionName);

      const killButton = document.createElement('button');
      killButton.className = 'jp-MarimoSidebar-killButton';
      killButton.innerHTML = '&times;';
      killButton.title = 'Shutdown session';
      killButton.addEventListener('click', () => {
        this._shutdownSession(session.sessionId);
      });

      sessionItem.appendChild(sessionInfo);
      sessionItem.appendChild(killButton);
      this._sessionsContainer.appendChild(sessionItem);
    }
  }

  private _buildUI(): void {
    const content = document.createElement('div');
    content.className = 'jp-MarimoSidebar-content';

    // Header
    const header = document.createElement('div');
    header.className = 'jp-MarimoSidebar-header';
    header.innerHTML = '<span class="jp-MarimoSidebar-title">marimo</span>';
    content.appendChild(header);

    // Status section
    const statusSection = document.createElement('div');
    statusSection.className = 'jp-MarimoSidebar-section';

    const statusTitle = document.createElement('div');
    statusTitle.className = 'jp-MarimoSidebar-sectionTitle';
    statusTitle.textContent = 'Server Status';
    statusSection.appendChild(statusTitle);

    const statusRow = document.createElement('div');
    statusRow.className = 'jp-MarimoSidebar-status';

    this._statusDot = document.createElement('span');
    this._statusDot.className = 'jp-MarimoSidebar-statusDot jp-mod-ready';
    statusRow.appendChild(this._statusDot);

    this._statusText = document.createElement('span');
    this._statusText.textContent = 'Running';
    statusRow.appendChild(this._statusText);

    statusSection.appendChild(statusRow);

    // Server controls
    this._serverControlsContainer = document.createElement('div');
    this._serverControlsContainer.className =
      'jp-MarimoSidebar-serverControls';

    const restartButton = document.createElement('button');
    restartButton.className = 'jp-MarimoSidebar-serverButton jp-mod-restart';
    restartButton.innerHTML = '&#8635; Restart';
    restartButton.title = 'Restart the marimo server';
    restartButton.addEventListener('click', () => {
      this._restartServer();
    });
    this._serverControlsContainer.appendChild(restartButton);

    statusSection.appendChild(this._serverControlsContainer);

    // Start server button (shown when server is stopped)
    this._startServerContainer = document.createElement('div');
    this._startServerContainer.className = 'jp-MarimoSidebar-serverControls';
    this._startServerContainer.style.display = 'none';

    const startButton = document.createElement('button');
    startButton.className = 'jp-MarimoSidebar-serverButton jp-mod-start';
    startButton.innerHTML = '&#9654; Start Server';
    startButton.title = 'Start the marimo server';
    startButton.addEventListener('click', () => {
      this._startServer();
    });
    this._startServerContainer.appendChild(startButton);

    statusSection.appendChild(this._startServerContainer);
    content.appendChild(statusSection);

    // Running Sessions section
    const sessionsSection = document.createElement('div');
    sessionsSection.className = 'jp-MarimoSidebar-section';

    const sessionsTitleRow = document.createElement('div');
    sessionsTitleRow.className = 'jp-MarimoSidebar-sectionTitleRow';

    const sessionsTitle = document.createElement('div');
    sessionsTitle.className = 'jp-MarimoSidebar-sectionTitle';
    sessionsTitle.textContent = 'Running Sessions';
    sessionsTitleRow.appendChild(sessionsTitle);

    const refreshButton = document.createElement('button');
    refreshButton.className = 'jp-MarimoSidebar-refreshButton';
    refreshButton.innerHTML = '&#8635;';
    refreshButton.title = 'Refresh sessions';
    refreshButton.addEventListener('click', () => {
      this._refreshSessions();
    });
    sessionsTitleRow.appendChild(refreshButton);

    sessionsSection.appendChild(sessionsTitleRow);

    this._sessionsContainer = document.createElement('div');
    this._sessionsContainer.className = 'jp-MarimoSidebar-sessions';
    sessionsSection.appendChild(this._sessionsContainer);

    content.appendChild(sessionsSection);

    // Quick Actions section
    const actionsSection = document.createElement('div');
    actionsSection.className = 'jp-MarimoSidebar-section';

    const actionsTitle = document.createElement('div');
    actionsTitle.className = 'jp-MarimoSidebar-sectionTitle';
    actionsTitle.textContent = 'Quick Actions';
    actionsSection.appendChild(actionsTitle);

    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'jp-MarimoSidebar-actions';

    // New Notebook button
    const newButton = document.createElement('button');
    newButton.className = 'jp-MarimoSidebar-button';
    newButton.innerHTML =
      '<span class="jp-MarimoSidebar-buttonIcon">+</span> New Notebook';
    newButton.addEventListener('click', () => {
      this._commands.execute('marimo:new-notebook');
    });
    actionsContainer.appendChild(newButton);

    // Open Editor button
    const openButton = document.createElement('button');
    openButton.className = 'jp-MarimoSidebar-button';
    openButton.innerHTML =
      '<span class="jp-MarimoSidebar-buttonIcon">&#8599;</span> Open Editor';
    openButton.addEventListener('click', () => {
      this._commands.execute('marimo:open-editor');
    });
    actionsContainer.appendChild(openButton);

    actionsSection.appendChild(actionsContainer);
    content.appendChild(actionsSection);

    // Help section
    const helpSection = document.createElement('div');
    helpSection.className = 'jp-MarimoSidebar-section';
    helpSection.innerHTML = `
      <div class="jp-MarimoSidebar-sectionTitle">Help</div>
      <div class="jp-MarimoSidebar-help">
        <p>Right-click on <code>.py</code> files to open them with marimo.</p>
        <p>Right-click on <code>.ipynb</code> files to convert them to marimo format.</p>
      </div>
    `;
    content.appendChild(helpSection);

    this.node.appendChild(content);
  }
}
