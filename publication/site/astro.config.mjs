import { defineConfig } from 'astro/config';

export default defineConfig({
  base: '/retrospective-complexity-eval',
  build: { format: 'directory' },
  output: 'static',
  site: 'http://127.0.0.1:4321',
});
