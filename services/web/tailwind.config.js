/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        space: {
          deep: "#030712",
          dark: "#080c16",
          card: "#0f172a",
          border: "#1e293b",
        },
      },
      fontFamily: {
        sans: ["'Space Grotesk'", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        glow: "0 0 25px -5px rgba(56, 189, 248, 0.3)",
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};
