import {
  type JupyterFrontEnd,
  type JupyterFrontEndPlugin,
  ILayoutRestorer,
} from '@jupyterlab/application';
import { InputDialog, showErrorMessage } from '@jupyterlab/apputils';
import { ServerConnection, KernelSpecAPI } from '@jupyterlab/services';
import { IFileBrowserFactory } from '@jupyterlab/filebrowser';
import { ILauncher } from '@jupyterlab/launcher';
import { PageConfig } from '@jupyterlab/coreutils';
import { type DocumentRegistry } from '@jupyterlab/docregistry';

import { createMarimoWidget } from './iframe-widget';
import { MarimoSidebar } from './sidebar';
import { marimoIcon, marimoFileIcon, marimoIconUrl, leafIconUrl } from './icons';
import { MarimoWidgetFactory, FACTORY_NAME } from './widget-factory';

import '../style/base.css';

/**
 * Command IDs used by the extension.
 */
const CommandIDs = {
  openFile: 'marimo:open-file',
  convertNotebook: 'marimo:convert-notebook',
  newNotebook: 'marimo:new-notebook',
  openEditor: 'marimo:open-editor',
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
 * Check if a file path is a Python file.
 */
function isPythonFile(path: string): boolean {
  return path.endsWith('.py');
}

/**
 * Check if a file path is a Jupyter notebook.
 */
function isNotebookFile(path: string): boolean {
  return path.endsWith('.ipynb');
}

/**
 * Check if a file path is a Marimo notebook (.mo.py).
 */
function isMarimoFile(path: string): boolean {
  return path.endsWith('.mo.py');
}

/**
 * The Marimo file type for .mo.py files.
 */
const marimoFileType: Partial<DocumentRegistry.IFileType> = {
  name: 'marimo',
  displayName: 'Marimo Notebook',
  mimeTypes: ['text/x-python'],
  extensions: ['.mo.py'],
  fileFormat: 'text',
  contentType: 'file',
  icon: marimoFileIcon,
};

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

    // Register the Marimo file type for .mo.py files
    app.docRegistry.addFileType(marimoFileType as DocumentRegistry.IFileType);

    // Command: Edit Python file with marimo
    commands.addCommand(CommandIDs.openFile, {
      label: 'Edit with marimo',
      caption: 'Edit this Python file in the marimo editor',
      icon: marimoIcon,
      isVisible: () => {
        const path = getSelectedFilePath(fileBrowserFactory);
        return path !== null && (isPythonFile(path) || isMarimoFile(path));
      },
      execute: () => {
        const filePath = getSelectedFilePath(fileBrowserFactory);
        if (!filePath) {
          return;
        }
        const url = `${marimoBaseUrl}?file=${encodeURIComponent(filePath)}`;
        const widget = createMarimoWidget(url, { filePath });
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
          const url = `${marimoBaseUrl}?file=${encodeURIComponent(outputPath)}`;
          const widget = createMarimoWidget(url, { filePath: outputPath });
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

          // If no venv kernels, skip dropdown and open marimo directly
          if (kernelEntries.length === 0) {
            const widget = createMarimoWidget(marimoBaseUrl, {
              label: 'New Notebook',
            });
            shell.add(widget, 'main');
            shell.activateById(widget.id);
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

          // If "Default" selected, open marimo directly (no file creation)
          if (kernelResult.value === 'Default (no venv)') {
            const widget = createMarimoWidget(marimoBaseUrl, {
              label: 'New Notebook',
            });
            shell.add(widget, 'main');
            shell.activateById(widget.id);
            return;
          }

          // Get venv path from selected kernel
          const selectedKernel = kernelEntries.find(
            (k) => k.displayName === kernelResult.value,
          );
          const venv = selectedKernel?.argv[0];

          // Prompt for notebook name
          const nameResult = await InputDialog.getText({
            title: 'New marimo Notebook',
            label: 'Notebook name:',
            text: 'untitled.mo.py',
          });

          if (!nameResult.button.accept || !nameResult.value) {
            return;
          }

          let filename = nameResult.value;
          if (!filename.endsWith('.py')) {
            filename += '.mo.py';
          }

          // Get current directory from file browser
          const browser = fileBrowserFactory.tracker.currentWidget;
          const cwd = browser?.model.path || '';
          const filePath = cwd ? `${cwd}/${filename}` : filename;

          // Create stub file via backend
          const settings = ServerConnection.makeSettings();
          const response = await ServerConnection.makeRequest(
            `${settings.baseUrl}marimo-tools/create-stub`,
            {
              method: 'POST',
              body: JSON.stringify({ path: filePath, venv }),
            },
            settings,
          );

          const result = (await response.json()) as {
            success: boolean;
            error?: string;
          };
          if (!response.ok || !result.success) {
            throw new Error(result.error ?? 'Failed to create notebook');
          }

          // Refresh file browser
          if (browser) {
            await browser.model.refresh();
          }

          // Open the created file in marimo
          const url = `${marimoBaseUrl}?file=${encodeURIComponent(filePath)}`;
          const widget = createMarimoWidget(url, { filePath });
          shell.add(widget, 'main');
          shell.activateById(widget.id);
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

    // Command: Open marimo editor (in new tab)
    commands.addCommand(CommandIDs.openEditor, {
      label: 'Open marimo Editor',
      caption: 'Open the marimo editor in a new tab',
      icon: marimoIcon,
      execute: () => {
        window.open(marimoBaseUrl, '_blank');
      },
    });

    // Add context menu items programmatically for proper visibility support
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
      defaultFor: ['marimo'], // Default for .mo.py files, "Open With" for .py files
    });
    app.docRegistry.addWidgetFactory(widgetFactory);
  },
};

export default plugin;
