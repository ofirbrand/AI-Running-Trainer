/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef9f1",
          100: "#d6f0dd",
          200: "#aee0bd",
          300: "#7fcd98",
          400: "#4fb472",
          500: "#2f9a57",
          600: "#207b44",
          700: "#1b6238",
          800: "#184e2e",
          900: "#143f27",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px rgba(16, 24, 40, 0.1), 0 1px 2px rgba(16, 24, 40, 0.06)",
      },
    },
  },
  plugins: [],
};
