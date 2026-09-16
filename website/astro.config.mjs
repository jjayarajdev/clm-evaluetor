import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://evaluetor.com',
  integrations: [
    tailwind(),
    sitemap({
      filter: (page) => !page.endsWith('/404/'),
    }),
  ],
  output: 'static',
});
