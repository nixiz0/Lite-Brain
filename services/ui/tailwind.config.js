// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./templates/**/*.{html,js}",
    "./**/*.py",
  ],
  theme: {
    extend: {
      typography: ({ theme }) => ({
        invert: {
          css: {
            '--tw-prose-bullets': theme('colors.slate[400]'),
            '--tw-prose-counters': theme('colors.slate[400]'),
            a: { textDecoration: 'none', fontWeight: '500' },
            'a:hover': { textDecoration: 'underline' },
            code: { fontWeight: '500' },
            'h1,h2,h3': { scrollMarginTop: '6rem' },
            blockquote: { borderLeftColor: theme('colors.cyan[500]') },
            table: { overflow: 'hidden', borderRadius: theme('borderRadius.xl') },
          }
        }
      })
    }
  },
  plugins: [require('@tailwindcss/typography')],
}