import { describe, expect, it, vi } from 'vitest';

// Mock icons module to avoid JupyterLab/SVG runtime dependencies
vi.mock('./icons', () => ({
  marimoFileIcon: {},
}));

import {
  isMarimoFile,
  isNotebookFile,
  isPythonFile,
  marimoFileType,
} from './file-types';

describe('isPythonFile', () => {
  it('returns true for .py files', () => {
    expect(isPythonFile('script.py')).toBe(true);
    expect(isPythonFile('path/to/script.py')).toBe(true);
    expect(isPythonFile('my_module.py')).toBe(true);
  });

  it('returns false for non-.py files', () => {
    expect(isPythonFile('script.js')).toBe(false);
    expect(isPythonFile('notebook.ipynb')).toBe(false);
    expect(isPythonFile('script.py.bak')).toBe(false);
    expect(isPythonFile('script.pyw')).toBe(false);
  });
});

describe('isNotebookFile', () => {
  it('returns true for .ipynb files', () => {
    expect(isNotebookFile('notebook.ipynb')).toBe(true);
    expect(isNotebookFile('path/to/notebook.ipynb')).toBe(true);
  });

  it('returns false for non-.ipynb files', () => {
    expect(isNotebookFile('script.py')).toBe(false);
    expect(isNotebookFile('notebook.ipynb.bak')).toBe(false);
  });
});

describe('isMarimoFile', () => {
  it('returns true for _mo.py files', () => {
    expect(isMarimoFile('script_mo.py')).toBe(true);
    expect(isMarimoFile('path/to/script_mo.py')).toBe(true);
    expect(isMarimoFile('my_module_mo.py')).toBe(true);
  });

  it('returns false for regular .py files', () => {
    expect(isMarimoFile('script.py')).toBe(false);
    expect(isMarimoFile('demo.py')).toBe(false);
  });

  it('returns false for files with "mo" not as _mo suffix', () => {
    expect(isMarimoFile('modem.py')).toBe(false);
    expect(isMarimoFile('module.py')).toBe(false);
    expect(isMarimoFile('memo.py')).toBe(false);
  });
});

describe('marimoFileType', () => {
  describe('pattern matching', () => {
    const pattern = new RegExp(marimoFileType.pattern as string);

    it('matches _mo.py files', () => {
      expect(pattern.test('script_mo.py')).toBe(true);
      expect(pattern.test('my_module_mo.py')).toBe(true);
      expect(pattern.test('test_mo.py')).toBe(true);
    });

    it('does not match regular .py files', () => {
      expect(pattern.test('script.py')).toBe(false);
      expect(pattern.test('demo.py')).toBe(false);
      expect(pattern.test('module.py')).toBe(false);
    });

    it('does not match files ending with mo.py but without underscore', () => {
      expect(pattern.test('memo.py')).toBe(false);
      expect(pattern.test('demo.py')).toBe(false);
    });
  });

  describe('file type registration (Issue #12)', () => {
    it('should NOT have extensions that match all .py files', () => {
      // Regression test for Issue #12: if extensions includes '.py',
      // JupyterLab classifies ALL .py files as 'marimo' type, causing
      // them to open with MarimoWidgetFactory instead of the default editor.
      const extensions = marimoFileType.extensions ?? [];
      expect(extensions).not.toContain('.py');
    });

    it('should rely on pattern-only matching for _mo.py files', () => {
      expect(marimoFileType.pattern).toBeDefined();
    });
  });
});
