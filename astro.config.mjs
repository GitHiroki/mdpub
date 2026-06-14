// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
    integrations: [
        starlight({
            title: 'My Docs',
            social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/withastro/starlight' }],
            sidebar: [
                // TODO: 後で消す。
                // {
                //     label: 'Guides',
                //     items: [
                //         // Each item here is one entry in the navigation menu.
                //         { label: 'Example Guide', slug: 'guides/example' },
                //     ],
                // },
                // {
                //     label: 'Reference',
                //     items: [{ autogenerate: { directory: 'reference' } }],
                // },
                {
                    label: 'テスト',
                    items: [{ autogenerate: { directory: 'test' } }],
                }
            ],
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