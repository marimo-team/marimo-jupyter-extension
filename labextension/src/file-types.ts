import type { DocumentRegistry } from '@jupyterlab/docregistry';
import { marimoFileIcon } from './icons';

/**
 * Check if a file path is a Python file.
 */
export function isPythonFile(path: string): boolean {
  return path.endsWith('.py');
}

/**
 * Check if a file path is a Jupyter notebook.
 */
export function isNotebookFile(path: string): boolean {
  return path.endsWith('.ipynb');
}

/**
 * Check if a file path is a Marimo notebook (_mo.py).
 */
export function isMarimoFile(path: string): boolean {
  return path.endsWith('_mo.py');
}

/**
 * The Marimo file type for _mo.py files.
 * Note: We intentionally omit `extensions` to avoid JupyterLab classifying
 * ALL .py files as marimo type. The `pattern` regex is sufficient for
 * matching only *_mo.py files. See Issue #12.
 */
export const marimoFileType: Partial<DocumentRegistry.IFileType> = {
  name: 'marimo',
  displayName: 'Marimo Notebook',
  mimeTypes: ['text/x-python'],
  pattern: '.*_mo\\.py$',
  fileFormat: 'text',
  contentType: 'file',
  icon: marimoFileIcon,
};
