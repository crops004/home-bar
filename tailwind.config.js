/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ]
}
