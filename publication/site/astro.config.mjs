import { defineConfig } from 'astro/config';

export default defineConfig({
  base: '/retrospective-eip-complexity',
  build: { format: 'directory' },
  output: 'static',
  site: 'https://danceratopz.github.io',
});
