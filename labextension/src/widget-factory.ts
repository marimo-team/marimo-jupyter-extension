import {
  ABCWidgetFactory,
  type DocumentRegistry,
  DocumentWidget,
} from '@jupyterlab/docregistry';
import type { IFrame } from '@jupyterlab/apputils';
import { PageConfig } from '@jupyterlab/coreutils';
import { leafIcon } from './icons';
import {
  createMarimoIFrame,
  registerWidgetForTracking,
} from './iframe-widget';

/**
 * A widget that wraps a marimo IFrame for document viewing.
 */
export class MarimoDocWidget extends DocumentWidget<IFrame> {}

/**
 * A widget factory for marimo documents.
 * This allows Python files to be opened with marimo via the "Open With" menu.
 */
export class MarimoWidgetFactory extends ABCWidgetFactory<MarimoDocWidget> {
  /**
   * Create a new widget given a context.
   */
  protected createNewWidget(
    context: DocumentRegistry.Context,
  ): MarimoDocWidget {
    const baseUrl = PageConfig.getBaseUrl();
    const marimoBaseUrl = `${baseUrl}marimo/`;
    const filePath = context.path;

    // Use centralized IFrame creation for consistent sandbox settings and URL building
    const { iframe: content, url } = createMarimoIFrame(marimoBaseUrl, {
      filePath,
    });

    const widget = new MarimoDocWidget({ content, context });
    widget.title.icon = leafIcon;
    widget.title.caption = `marimo: ${filePath}`;

    // Register for disconnection tracking
    registerWidgetForTracking(widget, filePath, url);

    return widget;
  }
}

/**
 * The name of the factory for marimo widgets.
 */
export const FACTORY_NAME = 'marimo';
