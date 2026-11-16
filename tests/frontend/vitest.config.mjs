import vue from './node_modules/@vitejs/plugin-vue/dist/index.mjs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../../', import.meta.url));
export default {
    root,
    cacheDir: '/tmp/menutor-frontend-vite-cache',
    plugins: [vue()],
    resolve: { alias: { '@': root + 'frontend/src', 'vue': root + 'frontend/node_modules/vue/dist/vue.runtime.esm-bundler.js', 'pinia': root + 'frontend/node_modules/pinia/dist/pinia.mjs', 'axios': root + 'frontend/node_modules/axios/index.js', 'vue-router': root + 'frontend/node_modules/vue-router/dist/vue-router.js' } },
    define: { __APP_VERSION__: JSON.stringify('test') },
    test: {
        environment: 'happy-dom', globals: true, fileParallelism: false,
        include: ['tests/frontend/**/*.test.ts', 'frontend/src/**/*.test.ts'],
        setupFiles: ['tests/frontend/setup.ts'],
    },
};
