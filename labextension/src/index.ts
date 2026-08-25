import {
  ILayoutRestorer,
  type JupyterFrontEnd,
  type JupyterFrontEndPlugin,
} from '@jupyterlab/application';
import {
  Clipboard,
  Dialog,
  InputDialog,
  Notification,
  WidgetTracker,
  showDialog,
  showErrorMessage,
} from '@jupyterlab/apputils';
import { PageConfig } from '@jupyterlab/coreutils';
import { IFileBrowserFactory } from '@jupyterlab/filebrowser';
import { ILauncher } from '@jupyterlab/launcher';
import { KernelSpecAPI, ServerConnection } from '@jupyterlab/services';

import { runIcon } from '@jupyterlab/ui-components';
import {
  isPythonFile,
  isNotebookFile,
  isMarimoFile,
  marimoFileType,
} from './file-types';
import {
  leafIconUrl,
  marimoFileIcon,
  marimoIcon,
  marimoIconUrl,
} from './icons';
import {
  createMarimoWidget,
  disconnectWidgetByFilePath,
  getWidgetByFilePath,
  getWidgetByInitializationId,
  type MarimoScratchWidget,
  refreshWidgetByFilePath,
} from './iframe-widget';
import {
  createMarimoSessionId,
  fetchRunningSessions,
  fetchRestorableScratchSessions,
  getScratchInitializationId,
  OPEN_RUNNING_SESSION_COMMAND,
  resolveScratchSession,
  takeOverScratchSession,
  type RunningSession,
} from './scratch-notebook';
import { MarimoSidebar } from './sidebar';
import {
  FACTORY_NAME,
  type MarimoDocWidget,
  MarimoWidgetFactory,
} from './widget-factory';

import '../style/base.css';

/**
 * Command IDs used by the extension.
 */
const CommandIDs = {
  openFile: 'marimo:open-file',
  convertNotebook: 'marimo:convert-notebook',
  newNotebook: 'marimo:new-notebook',
  openEditor: 'marimo:open-editor',
  copyAppLink: 'marimo:copy-app-link',
  changeEnvironment: 'marimo:change-environment',
  newNotebookInFolder: 'marimo:new-notebook-in-folder',
  restoreScratchNotebook: 'marimo:restore-scratch-notebook',
  openRunningSession: OPEN_RUNNING_SESSION_COMMAND,
} as const;

/**
 * The JupyterLab command that opens a path with a given document factory.
 * Used both to open marimo notebooks and to reopen them on layout restore.
 */
const DOCUMENT_OPEN_COMMAND = 'docmanager:open';

/**
 * Get the base URL for the Marimo proxy.
 */
function getMarimoBaseUrl(): string {
  const baseUrl = PageConfig.getBaseUrl();
  return `${baseUrl}marimo/`;
}

/** Check proxy process state without spawning marimo. */
async function isMarimoProcessAlive(): Promise<boolean> {
  const settings = ServerConnection.makeSettings();
  const response = await ServerConnection.makeRequest(
    `${settings.baseUrl}marimo-tools/health`,
    { method: 'GET' },
    settings,
  );
  if (!response.ok) {
    throw new Error(`Failed to check marimo process (${response.status})`);
  }
  const data = (await response.json()) as { process_alive?: unknown };
  if (typeof data.process_alive !== 'boolean') {
    throw new Error('Invalid marimo health response');
  }
  return data.process_alive;
}

/**
 * Get the selected file path from the file browser.
 */
function getSelectedFilePath(
  fileBrowserFactory: IFileBrowserFactory,
): string | null {
  const browser = fileBrowserFactory.tracker.currentWidget;
  if (!browser) {
    return null;
  }

  const item = browser.selectedItems().next();
  if (item.done || !item.value) {
    return null;
  }

  return item.value.path;
}

interface PythonEnvironment {
  name: string;
  displayName: string;
  pythonPath: string;
}

interface EnvironmentSelection {
  accepted: boolean;
  displayName: string;
  venv: string | undefined;
}

async function getPythonEnvironments(): Promise<PythonEnvironment[]> {
  const specs = await KernelSpecAPI.getSpecs();
  const environments: PythonEnvironment[] = [];
  if (!specs?.kernelspecs) {
    return environments;
  }

  for (const [name, spec] of Object.entries(specs.kernelspecs)) {
    if (spec?.language && spec.language.toLowerCase() !== 'python') {
      continue;
    }
    const pythonPath = spec?.argv?.[0];
    if (
      !pythonPath ||
      (!pythonPath.includes('/') && !pythonPath.includes('\\'))
    ) {
      continue;
    }
    environments.push({
      name,
      displayName: spec.display_name ?? name,
      pythonPath,
    });
  }
  return environments;
}

async function selectPythonEnvironment(
  options: {
    currentVenv?: string;
    showDefaultOnly?: boolean;
  } = {},
): Promise<EnvironmentSelection> {
  const environments = await getPythonEnvironments();
  if (environments.length === 0 && !options.showDefaultOnly) {
    return {
      accepted: true,
      displayName: 'Default',
      venv: undefined,
    };
  }

  const normalizeEnvironmentPath = (path: string): string => {
    const normalized = path.replaceAll('\\', '/').replace(/\/$/, '');
    const withoutInterpreter = normalized.replace(
      /\/(?:bin|scripts)\/[^/]+$/i,
      '',
    );
    return /^[a-z]:/i.test(withoutInterpreter)
      ? withoutInterpreter.toLowerCase()
      : withoutInterpreter;
  };
  let currentEnvironmentIndex = -1;
  if (options.currentVenv) {
    const currentPath = normalizeEnvironmentPath(options.currentVenv);
    currentEnvironmentIndex = environments.findIndex(
      (environment) =>
        normalizeEnvironmentPath(environment.pythonPath) === currentPath,
    );
    if (currentEnvironmentIndex === -1) {
      environments.push({
        name: 'current',
        displayName: `Current (${options.currentVenv})`,
        pythonPath: options.currentVenv,
      });
      currentEnvironmentIndex = environments.length - 1;
    }
  }

  const defaultLabel = 'Default (no venv)';
  const displayNameCounts = new Map<string, number>();
  for (const environment of environments) {
    displayNameCounts.set(
      environment.displayName,
      (displayNameCounts.get(environment.displayName) ?? 0) + 1,
    );
  }
  const environmentLabels = environments.map((environment) =>
    displayNameCounts.get(environment.displayName) === 1
      ? environment.displayName
      : `${environment.displayName} (${environment.name})`,
  );
  const labels = [defaultLabel, ...environmentLabels];
  const result = await InputDialog.getItem({
    title: 'Select Python Environment',
    label: 'Kernel:',
    items: labels,
    current: currentEnvironmentIndex + 1,
  });
  if (!result.button.accept || result.value === null) {
    return { accepted: false, displayName: '', venv: undefined };
  }

  const selectedIndex = labels.indexOf(result.value) - 1;
  const environment = environments[selectedIndex];
  return {
    accepted: true,
    displayName: environment?.displayName ?? 'Default',
    venv: environment?.pythonPath,
  };
}

interface NotebookEnvironment {
  isMarimo: boolean;
  venv: string | undefined;
}

async function getNotebookEnvironment(
  filePath: string,
): Promise<NotebookEnvironment> {
  const settings = ServerConnection.makeSettings();
  const query = new URLSearchParams({ path: filePath });
  const response = await ServerConnection.makeRequest(
    `${settings.baseUrl}marimo-tools/set-venv?${query.toString()}`,
    { method: 'GET' },
    settings,
  );
  const result = (await response.json()) as {
    success: boolean;
    isMarimo?: boolean;
    venv?: string | null;
    error?: string;
  };
  if (!response.ok || !result.success) {
    throw new Error(result.error ?? 'Failed to inspect notebook');
  }
  return {
    isMarimo: result.isMarimo === true,
    venv: result.venv ?? undefined,
  };
}

async function isSandboxDisabled(): Promise<boolean> {
  const settings = ServerConnection.makeSettings();
  try {
    const response = await ServerConnection.makeRequest(
      `${settings.baseUrl}marimo-tools/config`,
      { method: 'GET' },
      settings,
    );
    if (response.ok) {
      const config = (await response.json()) as { no_sandbox: boolean };
      return config.no_sandbox;
    }
  } catch {
    // Sandbox mode is the default when configuration cannot be read.
  }
  return false;
}

/**
 * The main plugin that provides marimo integration.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: '@marimo-team/jupyter-extension:plugin',
  description: 'JupyterLab extension for marimo notebook integration',
  autoStart: true,
  requires: [IFileBrowserFactory],
  optional: [ILauncher, ILayoutRestorer],
  activate: (
    app: JupyterFrontEnd,
    fileBrowserFactory: IFileBrowserFactory,
    launcher: ILauncher | null,
    restorer: ILayoutRestorer | null,
  ) => {
    const { commands, shell } = app;
    const marimoBaseUrl = getMarimoBaseUrl();
    const scratchTracker = new WidgetTracker<MarimoScratchWidget>({
      namespace: 'marimo-scratch-notebooks',
    });
    let restorableScratchSessions: RunningSession[] | null = null;

    // Register the Marimo file type for _mo.py files
    app.docRegistry.addFileType(marimoFileType);

    /**
     * Open a file in the marimo editor via the document registry.
     */
    async function openMarimoDocument(filePath: string): Promise<void> {
      await commands.execute(DOCUMENT_OPEN_COMMAND, {
        path: filePath,
        factory: FACTORY_NAME,
      });
    }

    /**
     * Open the marimo editor on a notebook that has no file yet.
     */
    async function openScratchNotebook(
      options: {
        initId?: string;
        label?: string;
        activate?: boolean;
        recover?: boolean;
      } = {},
    ): Promise<MarimoScratchWidget> {
      const recoverySessionId = options.recover
        ? createMarimoSessionId()
        : undefined;
      const widget = createMarimoWidget(marimoBaseUrl, {
        initId: options.initId,
        sessionId: recoverySessionId,
        kiosk: options.recover,
        label: options.label ?? 'New Notebook',
      });

      shell.add(widget, 'main');
      await scratchTracker.add(widget);
      if (options.recover && recoverySessionId && options.initId) {
        void takeOverScratchSession(
          marimoBaseUrl,
          options.initId,
          recoverySessionId,
        ).catch(() => {
          Notification.warning(
            'Notebook recovered read-only. Select “Take over” to edit it.',
          );
        });
      }
      if (options.activate !== false) {
        shell.activateById(widget.id);
      }
      return widget;
    }

    commands.addCommand(CommandIDs.restoreScratchNotebook, {
      execute: async (args) => {
        const initializationId = getScratchInitializationId(args);
        if (restorableScratchSessions === null) {
          throw new Error('Running sessions are not available');
        }
        const session = resolveScratchSession(
          restorableScratchSessions,
          initializationId,
        );
        return openScratchNotebook({
          initId: initializationId,
          label: session.name || 'New Notebook',
          activate: false,
          recover: true,
        });
      },
    });

    commands.addCommand(CommandIDs.openRunningSession, {
      execute: async (args) => {
        const session = args as Partial<RunningSession>;
        if (
          typeof session.path !== 'string' ||
          typeof session.name !== 'string' ||
          typeof session.initializationId !== 'string'
        ) {
          throw new Error('Invalid running session');
        }

        if (session.initializationId.startsWith('__new__')) {
          const existing = getWidgetByInitializationId(
            session.initializationId,
          );
          if (existing) {
            shell.activateById(existing.id);
            return existing;
          }
          return openScratchNotebook({
            initId: session.initializationId,
            label: session.name || 'New Notebook',
            recover: true,
          });
        }

        await openMarimoDocument(session.path);
        return undefined;
      },
    });

    if (restorer) {
      const sessionsReady = fetchRestorableScratchSessions(
        marimoBaseUrl,
        isMarimoProcessAlive,
      ).then((sessions) => {
        restorableScratchSessions = sessions;
      });
      void restorer.restore(scratchTracker, {
        command: CommandIDs.restoreScratchNotebook,
        args: (widget) => ({
          initializationId: widget.initializationId,
        }),
        name: (widget) => widget.initializationId,
        when: sessionsReady,
      });
    }

    // Shared helper: prompt for filename and create a notebook stub in the given directory
    async function createNotebookAt(
      cwd: string,
      venv: string | undefined,
    ): Promise<void> {
      const browser = fileBrowserFactory.tracker.currentWidget;
      const contentsManager = app.serviceManager.contents;
      let done = false;
      while (!done) {
        const nameResult = await InputDialog.getText({
          title: 'New marimo Notebook',
          label: 'Notebook name:',
          text: '',
        });
        if (!nameResult.button.accept) {
          return;
        }

        let filename = (nameResult.value ?? '').trim();
        if (!filename) {
          await showErrorMessage(
            'Invalid Filename',
            'Please enter a notebook name.',
          );
          continue;
        }

        filename = filename.replace(/[ -]/g, '_');
        if (!filename.endsWith('.py') && !filename.endsWith('.md')) {
          filename += '.py';
        }

        const filePath = cwd ? `${cwd}/${filename}` : filename;

        let fileExists = false;
        try {
          await contentsManager.get(filePath, { content: false });
          fileExists = true;
        } catch {
          // File doesn't exist - good to proceed
        }

        const existingWidget = fileExists
          ? getWidgetByFilePath(filePath)
          : null;

        if (fileExists) {
          const confirmResult = await showDialog({
            title: 'File Exists',
            body: `"${filename}" already exists. Overwrite?`,
            buttons: [
              Dialog.cancelButton(),
              Dialog.warnButton({ label: 'Overwrite' }),
            ],
          });
          if (!confirmResult.button.accept) {
            continue;
          }

          if (existingWidget) {
            try {
              const sessionsResponse = await fetch(
                `${marimoBaseUrl}api/home/running_notebooks`,
                { method: 'POST', credentials: 'same-origin' },
              );
              if (sessionsResponse.ok) {
                const data = (await sessionsResponse.json()) as {
                  files?: { sessionId: string; path: string }[];
                };
                const session = data.files?.find((s) => s.path === filePath);
                if (session) {
                  await fetch(`${marimoBaseUrl}api/home/shutdown_session`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sessionId: session.sessionId }),
                  });
                }
              }
            } catch {
              // Continue even if shutdown fails
            }
          }
        }

        const settings = ServerConnection.makeSettings();
        const response = await ServerConnection.makeRequest(
          `${settings.baseUrl}marimo-tools/create-stub`,
          { method: 'POST', body: JSON.stringify({ path: filePath, venv }) },
          settings,
        );
        const result = (await response.json()) as {
          success: boolean;
          error?: string;
        };
        if (!response.ok || !result.success) {
          throw new Error(result.error ?? 'Failed to create notebook');
        }

        if (browser) {
          await browser.model.refresh();
        }

        if (existingWidget) {
          refreshWidgetByFilePath(filePath);
          shell.activateById(existingWidget.id);
          done = true;
          continue;
        }

        await openMarimoDocument(filePath);
        done = true;
      }
    }

    // Command: Edit Python file with marimo
    commands.addCommand(CommandIDs.openFile, {
      label: 'Edit with marimo',
      caption: 'Edit this Python file in the marimo editor',
      icon: marimoFileIcon,
      isVisible: () => {
        const path = getSelectedFilePath(fileBrowserFactory);
        return path !== null && (isPythonFile(path) || isMarimoFile(path));
      },
      execute: async () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }
        await openMarimoDocument(filePath);
      },
    });

    // Command: Convert Jupyter notebook to marimo
    commands.addCommand(CommandIDs.convertNotebook, {
      label: 'Convert to marimo',
      caption: 'Convert this Jupyter notebook to marimo format',
      icon: marimoIcon,
      isVisible: () => {
        const path = getSelectedFilePath(fileBrowserFactory);
        return path !== null && isNotebookFile(path);
      },
      execute: async () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }

        // Generate default output path (replace .ipynb with .py)
        const defaultOutput = filePath.replace(/\.ipynb$/, '.py');

        // Show dialog to confirm/edit output filename
        const result = await InputDialog.getText({
          title: 'Convert to marimo',
          label: 'Output filename:',
          text: defaultOutput,
        });

        if (!result.button.accept || !result.value) {
          return;
        }

        const outputPath = result.value;

        try {
          const settings = ServerConnection.makeSettings();
          const response = await ServerConnection.makeRequest(
            `${settings.baseUrl}marimo-tools/convert`,
            {
              method: 'POST',
              body: JSON.stringify({ input: filePath, output: outputPath }),
            },
            settings,
          );

          const result = (await response.json()) as {
            success: boolean;
            error?: string;
          };

          if (!response.ok || !result.success) {
            throw new Error(result.error ?? 'Conversion failed');
          }

          // Refresh the file browser to show the new file
          const browser = fileBrowserFactory.tracker.currentWidget;
          if (browser) {
            await browser.model.refresh();
          }

          // Open the converted file in marimo
          await openMarimoDocument(outputPath);
        } catch (error) {
          showErrorMessage(
            'Conversion failed',
            `Failed to convert notebook: ${error}`,
          );
        }
      },
    });

    // Command: Create new marimo notebook
    commands.addCommand(CommandIDs.newNotebook, {
      label: 'New marimo Notebook',
      caption: 'Create a new marimo notebook',
      execute: async () => {
        try {
          const browser = fileBrowserFactory.tracker.currentWidget;
          const cwd = browser?.model.path || '';

          // If navigated into a subdirectory, prompt for name so file lands there
          if (await isSandboxDisabled()) {
            if (cwd) {
              await createNotebookAt(cwd, undefined);
            } else {
              await openScratchNotebook();
            }
            return;
          }

          const selection = await selectPythonEnvironment();
          if (!selection.accepted) {
            return;
          }

          // If Default selected and at root, open marimo directly
          if (!selection.venv && !cwd) {
            await openScratchNotebook();
            return;
          }

          await createNotebookAt(cwd, selection.venv);
        } catch {
          // Fall back to opening marimo directly on any error
          await openScratchNotebook();
        }
      },
    });

    // Command: Create new marimo notebook (right-click context menu)
    commands.addCommand(CommandIDs.newNotebookInFolder, {
      label: 'New marimo Notebook',
      caption: 'Create a new marimo notebook here',
      icon: marimoIcon,
      execute: async () => {
        const browser = fileBrowserFactory.tracker.currentWidget;
        const selectedItem = browser?.selectedItems().next();
        const cwd =
          !selectedItem?.done && selectedItem?.value?.type === 'directory'
            ? selectedItem.value.path
            : browser?.model.path || '';

        try {
          let venv: string | undefined;
          if (!(await isSandboxDisabled())) {
            const selection = await selectPythonEnvironment();
            if (!selection.accepted) {
              return;
            }
            venv = selection.venv;
          }

          await createNotebookAt(cwd, venv);
        } catch {
          showErrorMessage('Error', 'Failed to create notebook in folder');
        }
      },
    });

    commands.addCommand(CommandIDs.changeEnvironment, {
      label: 'Change Python Environment',
      caption: 'Change the Python environment used by this marimo notebook',
      icon: marimoIcon,
      isVisible: () => {
        const path = getSelectedFilePath(fileBrowserFactory);
        return path !== null && isPythonFile(path);
      },
      execute: async () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }
        const widget = getWidgetByFilePath(filePath);
        let widgetDisconnected = false;

        try {
          if (await isSandboxDisabled()) {
            await showErrorMessage(
              'Python environments unavailable',
              'This marimo server is running without sandbox support.',
            );
            return;
          }

          const notebookEnvironment = await getNotebookEnvironment(filePath);
          if (!notebookEnvironment.isMarimo) {
            await showErrorMessage(
              'Not a marimo notebook',
              `“${filePath}” does not define a marimo app.`,
            );
            return;
          }
          const selection = await selectPythonEnvironment({
            currentVenv: notebookEnvironment.venv,
            showDefaultOnly: true,
          });
          if (!selection.accepted) {
            return;
          }

          const sessions = (await isMarimoProcessAlive())
            ? await fetchRunningSessions(marimoBaseUrl)
            : [];
          const session = sessions.find(
            (candidate) => candidate.path === filePath,
          );
          if (session) {
            const confirmation = await showDialog({
              title: 'Restart marimo notebook?',
              body: `Changing the Python environment will restart “${filePath}”. Make sure your latest edits are saved.`,
              buttons: [
                Dialog.cancelButton(),
                Dialog.okButton({ label: 'Restart' }),
              ],
            });
            if (!confirmation.button.accept) {
              return;
            }

            if (widget) {
              disconnectWidgetByFilePath(filePath);
              widgetDisconnected = true;
            }
            const shutdownResponse = await fetch(
              `${marimoBaseUrl}api/home/shutdown_session`,
              {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sessionId: session.sessionId }),
              },
            );
            if (!shutdownResponse.ok) {
              throw new Error(
                `Failed to stop the current session (${shutdownResponse.status})`,
              );
            }
          }

          const settings = ServerConnection.makeSettings();
          const response = await ServerConnection.makeRequest(
            `${settings.baseUrl}marimo-tools/set-venv`,
            {
              method: 'POST',
              body: JSON.stringify({ path: filePath, venv: selection.venv }),
            },
            settings,
          );
          const result = (await response.json()) as {
            success: boolean;
            error?: string;
          };
          if (!response.ok || !result.success) {
            throw new Error(result.error ?? 'Failed to update environment');
          }

          if (widget) {
            refreshWidgetByFilePath(filePath);
            widgetDisconnected = false;
            shell.activateById(widget.id);
          }
          Notification.success(
            `Python environment changed to ${selection.displayName}`,
          );
        } catch (error) {
          if (widgetDisconnected) {
            refreshWidgetByFilePath(filePath);
          }
          await showErrorMessage(
            'Failed to change Python environment',
            `${error}`,
          );
        }
      },
    });

    // Command: Open marimo editor (in new tab)
    commands.addCommand(CommandIDs.openEditor, {
      label: 'Open marimo Editor',
      caption: 'Open the marimo editor in a new tab',
      icon: marimoIcon,
      execute: () => {
        window.open(marimoBaseUrl, '_blank');
      },
    });

    // Command: Copy app link for sharing
    commands.addCommand(CommandIDs.copyAppLink, {
      label: 'Copy App Link',
      caption: 'Copy a shareable link to run this notebook as an app',
      icon: runIcon,
      isVisible: () => {
        const path = getSelectedFilePath(fileBrowserFactory);
        return path !== null && isPythonFile(path);
      },
      execute: async () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }

        // Extract proxy name from marimoBaseUrl (e.g., '/user/foo/marimo/' → 'marimo')
        const proxyName =
          marimoBaseUrl.split('/').filter(Boolean).pop() || 'marimo';

        // Detect JupyterHub vs standalone JupyterLab
        const hubPrefix = PageConfig.getOption('hubPrefix');
        let appUrl: string;

        if (hubPrefix) {
          // JupyterHub: use /user-redirect/ for cross-user sharing
          appUrl = `${window.location.origin}${hubPrefix}user-redirect/${proxyName}/?file=${encodeURIComponent(filePath)}&show-chrome=false&view-as=present`;
        } else {
          // Standalone JupyterLab: use marimo base URL directly
          // marimoBaseUrl may be absolute (http://...) or relative (/marimo/)
          const baseUrl = marimoBaseUrl.startsWith('http')
            ? marimoBaseUrl
            : `${window.location.origin}${marimoBaseUrl}`;
          appUrl = `${baseUrl}?file=${encodeURIComponent(filePath)}&show-chrome=false&view-as=present`;
        }

        Clipboard.copyToSystem(appUrl);
        Notification.success('App link copied to clipboard');
      },
    });

    // Add context menu items programmatically for proper visibility support
    // Separator before marimo edit section
    app.contextMenu.addItem({
      type: 'separator',
      selector: '.jp-DirListing-item[data-isdir="false"]',
      rank: 49.5,
    });

    app.contextMenu.addItem({
      command: CommandIDs.openFile,
      selector: '.jp-DirListing-item[data-isdir="false"]',
      rank: 50,
    });

    app.contextMenu.addItem({
      command: CommandIDs.changeEnvironment,
      selector: '.jp-DirListing-item[data-isdir="false"]',
      rank: 50.5,
    });

    app.contextMenu.addItem({
      command: CommandIDs.convertNotebook,
      selector: '.jp-DirListing-item[data-isdir="false"]',
      rank: 51,
    });

    // Separator for marimo section
    app.contextMenu.addItem({
      command: CommandIDs.copyAppLink,
      selector: '.jp-DirListing-item[data-isdir="false"]',
      rank: 49,
    });

    app.contextMenu.addItem({
      command: CommandIDs.newNotebookInFolder,
      selector: '.jp-DirListing',
      rank: 59,
    });

    // Add to launcher if available
    if (launcher) {
      launcher.add({
        command: CommandIDs.newNotebook,
        category: 'Notebook',
        rank: 3,
        kernelIconUrl: leafIconUrl,
      });

      launcher.add({
        command: CommandIDs.openEditor,
        category: 'Other',
        rank: 1,
        kernelIconUrl: marimoIconUrl,
      });
    }

    // Create and add sidebar panel
    const sidebar = new MarimoSidebar(commands);
    shell.add(sidebar, 'left', { rank: 200 });

    // Restore sidebar state if restorer available
    if (restorer) {
      restorer.add(sidebar, 'marimo-sidebar');
    }

    // Register widget factory for Marimo files and "Open With" menu for Python files
    const widgetFactory = new MarimoWidgetFactory({
      name: FACTORY_NAME,
      fileTypes: ['marimo', 'python'],
      defaultFor: ['marimo'], // Default for _mo.py files, "Open With" for .py files
    });
    app.docRegistry.addWidgetFactory(widgetFactory);

    // Track the tabs the factory opens. Without a tracker registered with the
    // layout restorer, JupyterLab has no record of these widgets and drops
    // them on reload, while .ipynb tabs (whose plugin does register one) come
    // back.
    const documentTracker = new WidgetTracker<MarimoDocWidget>({
      namespace: 'marimo-documents',
    });
    widgetFactory.widgetCreated.connect((_factory, widget) => {
      void documentTracker.add(widget);
    });

    if (restorer) {
      void restorer.restore(documentTracker, {
        command: DOCUMENT_OPEN_COMMAND,
        args: (widget) => ({
          path: widget.context.path,
          factory: FACTORY_NAME,
        }),
        name: (widget) => widget.context.path,
      });
    }
  },
};

export default plugin;
