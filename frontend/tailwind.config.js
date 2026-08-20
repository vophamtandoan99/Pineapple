/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
    // Tắt preflight: reset của Tailwind xung đột style PrimeVue/PrimeFlex
    corePlugins: {
        preflight: false
    },
    theme: {
        extend: {}
    },
    plugins: []
};
