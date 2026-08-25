/** A running notebook returned by marimo's home API. */
export interface RunningSession {
  sessionId: string;
  name: string;
  path: string;
  initializationId: string;
  lastModified: number | null;
}

export const OPEN_RUNNING_SESSION_COMMAND = 'marimo:open-running-session';

export interface MarimoUrlOptions {
  sessionId?: string;
  kiosk?: boolean;
}

/** Create a session ID accepted by marimo's browser client. */
export function createMarimoSessionId(
  random: () => number = Math.random,
): string {
  let suffix = '';
  for (let index = 0; index < 6; index++) {
    suffix += Math.floor(random() * 36).toString(36);
  }
  return `s_${suffix}`;
}

/** Build the iframe URL for a file or scratch notebook. */
export function buildMarimoUrl(
  baseUrl: string,
  fileKey: string,
  options: MarimoUrlOptions = {},
): string {
  const params = new URLSearchParams({ file: fileKey });
  if (options.sessionId) {
    params.set('session_id', options.sessionId);
  }
  if (options.kiosk) {
    params.set('kiosk', 'true');
  }
  return `${baseUrl}?${params.toString()}`;
}

/**
 * Promote a replaying kiosk connection to the notebook's editor.
 *
 * The iframe document loads before its websocket is necessarily registered,
 * so a short retry window handles the expected 400 response during startup.
 */
export async function takeOverScratchSession(
  baseUrl: string,
  fileKey: string,
  sessionId: string,
  options: {
    attempts?: number;
    retryDelayMs?: number;
    wait?: (delayMs: number) => Promise<void>;
  } = {},
): Promise<void> {
  const attempts = options.attempts ?? 25;
  const retryDelayMs = options.retryDelayMs ?? 200;
  const wait =
    options.wait ??
    ((delayMs: number) =>
      new Promise<void>((resolve) => window.setTimeout(resolve, delayMs)));
  const params = new URLSearchParams({
    file: fileKey,
    session_id: sessionId,
    kiosk: 'true',
  });

  let lastStatus = 400;
  for (let attempt = 0; attempt < attempts; attempt++) {
    const response = await fetch(
      `${baseUrl}api/kernel/takeover?${params.toString()}`,
      {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Marimo-Session-Id': sessionId,
        },
        body: '{}',
      },
    );
    if (response.ok) {
      return;
    }

    lastStatus = response.status;
    if (response.status !== 400 || attempt === attempts - 1) {
      break;
    }
    await wait(retryDelayMs);
  }

  throw new Error(`Failed to take over scratch session (${lastStatus})`);
}

/** Read and validate the initialization ID saved by the widget tracker. */
export function getScratchInitializationId(args: {
  readonly [key: string]: unknown;
}): string {
  const initializationId = args.initializationId;
  if (
    typeof initializationId !== 'string' ||
    !initializationId.startsWith('__new__')
  ) {
    throw new Error('Invalid scratch notebook restoration state');
  }
  return initializationId;
}

/** Find the one live session that can restore a scratch notebook. */
export function resolveScratchSession(
  sessions: RunningSession[],
  initializationId: string,
): RunningSession {
  const matches = sessions.filter(
    (session) => session.initializationId === initializationId,
  );
  if (matches.length !== 1) {
    throw new Error(
      `Expected one running session for ${initializationId}. Found ${matches.length}`,
    );
  }
  return matches[0];
}

/** Fetch the running sessions used to reconcile saved scratch tabs. */
export async function fetchRunningSessions(
  baseUrl: string,
): Promise<RunningSession[]> {
  const response = await fetch(`${baseUrl}api/home/running_notebooks`, {
    method: 'POST',
    credentials: 'same-origin',
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch running sessions (${response.status})`);
  }

  const data = (await response.json()) as { files?: unknown };
  if (data.files === undefined) {
    return [];
  }
  if (!Array.isArray(data.files)) {
    throw new Error('Invalid running sessions response');
  }
  if (!data.files.every(isRunningSession)) {
    throw new Error('Invalid running session');
  }
  return data.files;
}

/** Reconcile saved scratch tabs without starting a stopped marimo proxy. */
export async function fetchRestorableScratchSessions(
  baseUrl: string,
  isProcessAlive: () => Promise<boolean>,
): Promise<RunningSession[]> {
  if (!(await isProcessAlive())) {
    return [];
  }
  return fetchRunningSessions(baseUrl);
}

function isRunningSession(value: unknown): value is RunningSession {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const session = value as Record<string, unknown>;
  return (
    typeof session.sessionId === 'string' &&
    typeof session.name === 'string' &&
    typeof session.path === 'string' &&
    typeof session.initializationId === 'string' &&
    (typeof session.lastModified === 'number' || session.lastModified === null)
  );
}
