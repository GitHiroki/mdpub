// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// import cloudflare from '@astrojs/cloudflare';

// https://astro.build/config
export default defineConfig({
    integrations: [
        // Starlight より前に置く必要がある
        mermaid({
            // Starlight の data-theme に追従してライト/ダークを切り替える
            autoTheme: true,
        }),
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
