import 'fake-indexeddb/auto';
import { vi } from 'vitest';

// api.ts dispatches window events (e.g. on 401); tests run in plain Node.
vi.stubGlobal('window', new EventTarget());
