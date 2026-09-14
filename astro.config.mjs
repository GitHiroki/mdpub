// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
    integrations: [
        starlight({
            title: 'mdpub',
            social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/GitHiroki/mdpub' }],
            head: [
                {
                    tag: 'meta',
                    attrs: { name: 'robots', content: 'noindex, nofollow' },
                },
            ],
            components: {
                Footer: './src/components/GiscusComments.astro',
            },
        }),
    ],

    //   adapter: cloudflare(),
});