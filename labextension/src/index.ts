import {
  ILayoutRestorer,
  type JupyterFrontEnd,
  type JupyterFrontEndPlugin,
} from '@jupyterlab/application';
import {
  Dialog,
  InputDialog,
  Notification,
  showDialog,
  showErrorMessage,
} from '@jupyterlab/apputils';
import { PageConfig } from '@jupyterlab/coreutils';
import type { DocumentRegistry } from '@jupyterlab/docregistry';
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
  getWidgetByFilePath,
  refreshWidgetByFilePath,
} from './iframe-widget';
import { MarimoSidebar } from './sidebar';
import { FACTORY_NAME, MarimoWidgetFactory } from './widget-factory';

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
  newNotebookInFolder: 'marimo:new-notebook-in-folder',
} as const;

/**
 * Get the base URL for the Marimo proxy.
 */
function getMarimoBaseUrl(): string {
  const baseUrl = PageConfig.getBaseUrl();
  return `${baseUrl}marimo/`;
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

    // Register the Marimo file type for _mo.py files
    app.docRegistry.addFileType(marimoFileType as DocumentRegistry.IFileType);

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

        const widget = createMarimoWidget(marimoBaseUrl, { filePath });
        shell.add(widget, 'main');
        shell.activateById(widget.id);
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
      execute: () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }
        const widget = createMarimoWidget(marimoBaseUrl, { filePath });
        shell.add(widget, 'main');
        shell.activateById(widget.id);
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
          const widget = createMarimoWidget(marimoBaseUrl, {
            filePath: outputPath,
          });
          shell.add(widget, 'main');
          shell.activateById(widget.id);
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
          // Check if sandbox is disabled (venv selection requires --sandbox)
          const settings = ServerConnection.makeSettings();
          let noSandbox = false;
          try {
            const configResponse = await ServerConnection.makeRequest(
              `${settings.baseUrl}marimo-tools/config`,
              { method: 'GET' },
              settings,
            );
            if (configResponse.ok) {
              const configData = (await configResponse.json()) as {
                no_sandbox: boolean;
              };
              noSandbox = configData.no_sandbox;
            }
          } catch {
            // If config fetch fails, assume sandbox enabled (default)
          }

          const browser = fileBrowserFactory.tracker.currentWidget;
          const cwd = browser?.model.path || '';

          // If sandbox is disabled, skip venv picker
          // If navigated into a subdirectory, prompt for name so file lands there
          if (noSandbox) {
            if (cwd) {
              await createNotebookAt(cwd, undefined);
            } else {
              const widget = createMarimoWidget(marimoBaseUrl, {
                label: 'New Notebook',
              });
              shell.add(widget, 'main');
              shell.activateById(widget.id);
            }
            return;
          }

          // Fetch available kernel specs
          const specs = await KernelSpecAPI.getSpecs();

          // Extract kernel names and display names, filtering out non-venv entries
          const kernelEntries: {
            name: string;
            displayName: string;
            argv: string[];
          }[] = [];
          if (specs?.kernelspecs) {
            for (const [name, spec] of Object.entries(specs.kernelspecs)) {
              if (!spec) {
                continue;
              }
              const argv = spec.argv ?? [];
              if (argv.length > 0) {
                const pythonPath = argv[0];
                // Skip entries that are just "python" or "python3" (not a venv path)
                // A venv path contains a directory separator
                if (!pythonPath.includes('/') && !pythonPath.includes('\\')) {
                  continue;
                }
                kernelEntries.push({
                  name,
                  displayName: spec.display_name ?? name,
                  argv,
                });
              }
            }
          }

          // If no venv kernels, skip dropdown
          if (kernelEntries.length === 0) {
            if (cwd) {
              await createNotebookAt(cwd, undefined);
            } else {
              const widget = createMarimoWidget(marimoBaseUrl, {
                label: 'New Notebook',
              });
              shell.add(widget, 'main');
              shell.activateById(widget.id);
            }
            return;
          }

          // Show dropdown dialog to select kernel, with "Default" as first option
          const items = [
            'Default (no venv)',
            ...kernelEntries.map((k) => k.displayName),
          ];
          const kernelResult = await InputDialog.getItem({
            title: 'Select Python Environment',
            label: 'Kernel:',
            items,
            current: 0,
          });

          // If user cancelled or no selection, return early
          if (!kernelResult.button.accept || kernelResult.value === null) {
            return;
          }

          // Get venv path from selected kernel (undefined if Default)
          const selectedKernel = kernelEntries.find(
            (k) => k.displayName === kernelResult.value,
          );
          const venv = selectedKernel?.argv[0];

          // If Default selected and at root, open marimo directly
          if (!venv && !cwd) {
            const widget = createMarimoWidget(marimoBaseUrl, {
              label: 'New Notebook',
            });
            shell.add(widget, 'main');
            shell.activateById(widget.id);
            return;
          }

          await createNotebookAt(cwd, venv);
        } catch {
          // Fall back to opening marimo directly on any error
          const widget = createMarimoWidget(marimoBaseUrl, {
            label: 'New Notebook',
          });
          shell.add(widget, 'main');
          shell.activateById(widget.id);
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
          const settings = ServerConnection.makeSettings();
          let noSandbox = false;
          try {
            const configResponse = await ServerConnection.makeRequest(
              `${settings.baseUrl}marimo-tools/config`,
              { method: 'GET' },
              settings,
            );
            if (configResponse.ok) {
              const configData = (await configResponse.json()) as {
                no_sandbox: boolean;
              };
              noSandbox = configData.no_sandbox;
            }
          } catch {
            // assume sandbox enabled
          }

          let venv: string | undefined;

          if (!noSandbox) {
            const specs = await KernelSpecAPI.getSpecs();
            const kernelEntries: {
              name: string;
              displayName: string;
              argv: string[];
            }[] = [];
            if (specs?.kernelspecs) {
              for (const [name, spec] of Object.entries(specs.kernelspecs)) {
                if (!spec) {
                  continue;
                }
                const argv = spec.argv ?? [];
                if (argv.length > 0) {
                  const pythonPath = argv[0];
                  if (
                    !pythonPath.includes('/') &&
                    !pythonPath.includes('\\')
                  ) {
                    continue;
                  }
                  kernelEntries.push({
                    name,
                    displayName: spec.display_name ?? name,
                    argv,
                  });
                }
              }
            }

            if (kernelEntries.length > 0) {
              const items = [
                'Default (no venv)',
                ...kernelEntries.map((k) => k.displayName),
              ];
              const kernelResult = await InputDialog.getItem({
                title: 'Select Python Environment',
                label: 'Kernel:',
                items,
                current: 0,
              });
              if (!kernelResult.button.accept || kernelResult.value === null) {
                return;
              }
              if (kernelResult.value !== 'Default (no venv)') {
                const selectedKernel = kernelEntries.find(
                  (k) => k.displayName === kernelResult.value,
                );
                venv = selectedKernel?.argv[0];
              }
            }
          }

          await createNotebookAt(cwd, venv);
        } catch {
          showErrorMessage('Error', 'Failed to create notebook in folder');
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

        await navigator.clipboard.writeText(appUrl);
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
  },
};

export default plugin;
