import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  buildMarimoUrl,
  createMarimoSessionId,
  fetchRestorableScratchSessions,
  fetchRunningSessions,
  getScratchInitializationId,
  resolveScratchSession,
  takeOverScratchSession,
  type RunningSession,
} from './scratch-notebook';

const session: RunningSession = {
  sessionId: 's_abc123',
  name: 'new notebook',
  path: 's_abc123',
  initializationId: '__new__notebook-1',
  lastModified: 0,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('buildMarimoUrl', () => {
  it('builds a fresh scratch notebook URL without a session ID', () => {
    expect(buildMarimoUrl('/marimo/', '__new__notebook-1')).toBe(
      '/marimo/?file=__new__notebook-1',
    );
  });

  it('builds a recovery URL with encoded identifiers', () => {
    expect(
      buildMarimoUrl('/user/test/marimo/', '__new__a/b c', {
        sessionId: 's_1/2',
        kiosk: true,
      }),
    ).toBe(
      '/user/test/marimo/?file=__new__a%2Fb+c&session_id=s_1%2F2&kiosk=true',
    );
  });
});

describe('createMarimoSessionId', () => {
  it('uses the session ID format accepted by marimo', () => {
    expect(createMarimoSessionId(() => 0.5)).toBe('s_iiiiii');
    expect(createMarimoSessionId(() => 0.5)).toMatch(/^s_[0-9a-z]{6}$/);
  });
});

describe('takeOverScratchSession', () => {
  it('retries until the iframe consumer is connected', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 400 })
      .mockResolvedValueOnce({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);
    const wait = vi.fn().mockResolvedValue(undefined);

    await takeOverScratchSession('/marimo/', '__new__notebook-1', 's_abc123', {
      wait,
    });

    expect(wait).toHaveBeenCalledWith(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/marimo/api/kernel/takeover?file=__new__notebook-1&session_id=s_abc123&kiosk=true',
      {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Marimo-Session-Id': 's_abc123',
        },
        body: '{}',
      },
    );
  });

  it('does not retry a terminal takeover failure', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal('fetch', fetchMock);
    const wait = vi.fn().mockResolvedValue(undefined);

    await expect(
      takeOverScratchSession('/marimo/', '__new__notebook-1', 's_abc123', {
        wait,
      }),
    ).rejects.toThrow('Failed to take over scratch session (403)');
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(wait).not.toHaveBeenCalled();
  });
});

describe('getScratchInitializationId', () => {
  it('accepts a scratch initialization ID', () => {
    expect(
      getScratchInitializationId({
        initializationId: '__new__notebook-1',
      }),
    ).toBe('__new__notebook-1');
  });

  it.each([
    {},
    { initializationId: null },
    { initializationId: 'not-a-scratch-notebook' },
  ])('rejects invalid restoration state', (args) => {
    expect(() => getScratchInitializationId(args)).toThrow(
      'Invalid scratch notebook restoration state',
    );
  });
});

describe('resolveScratchSession', () => {
  it('returns the single matching running session', () => {
    const otherSession = {
      ...session,
      sessionId: 's_def456',
      initializationId: '__new__notebook-2',
    };
    expect(
      resolveScratchSession([otherSession, session], session.initializationId),
    ).toEqual(session);
  });

  it('rejects a missing running session', () => {
    expect(() => resolveScratchSession([], session.initializationId)).toThrow(
      'Found 0',
    );
  });

  it('rejects ambiguous running sessions', () => {
    expect(() =>
      resolveScratchSession(
        [session, { ...session, sessionId: 's_def456' }],
        session.initializationId,
      ),
    ).toThrow('Found 2');
  });
});

describe('fetchRunningSessions', () => {
  it('loads running sessions from marimo', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ files: [session] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchRunningSessions('/marimo/')).resolves.toEqual([session]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/marimo/api/home/running_notebooks',
      {
        method: 'POST',
        credentials: 'same-origin',
      },
    );
  });

  it('treats an omitted files field as an empty list', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({}),
      }),
    );

    await expect(fetchRunningSessions('/marimo/')).resolves.toEqual([]);
  });

  it('rejects when session discovery fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      }),
    );

    await expect(fetchRunningSessions('/marimo/')).rejects.toThrow(
      'Failed to fetch running sessions (503)',
    );
  });

  it('rejects malformed session data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ files: 'not-an-array' }),
      }),
    );

    await expect(fetchRunningSessions('/marimo/')).rejects.toThrow(
      'Invalid running sessions response',
    );
  });

  it('rejects a malformed session entry', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ files: [{ initializationId: '__new__bad' }] }),
      }),
    );

    await expect(fetchRunningSessions('/marimo/')).rejects.toThrow(
      'Invalid running session',
    );
  });
});

describe('fetchRestorableScratchSessions', () => {
  it('does not start a stopped marimo proxy', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      fetchRestorableScratchSessions('/marimo/', async () => false),
    ).resolves.toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('loads sessions from an already-running marimo proxy', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ files: [session] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      fetchRestorableScratchSessions('/marimo/', async () => true),
    ).resolves.toEqual([session]);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
