// Keep the test harness and its writable artifacts outside frontend/.
import { existsSync, symlinkSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root = fileURLToPath(new URL('../../', import.meta.url));
const link = new URL('./node_modules', import.meta.url);
if (!existsSync(link))
    symlinkSync(root + 'frontend/node_modules', link, 'dir');
const result = spawnSync(process.execPath, [root + 'frontend/node_modules/vitest/vitest.mjs', 'run', '--config', root + 'tests/frontend/vitest.config.mjs', '--configLoader', 'native', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
process.exit(result.status ?? 1);
