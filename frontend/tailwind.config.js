/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Z1N placeholder palette — finalise in branding phase
        brand: {
          50: "#f5f7fb",
          100: "#e6ecf5",
          500: "#1f3a68",
          700: "#162a4d",
          900: "#0b1a33",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
