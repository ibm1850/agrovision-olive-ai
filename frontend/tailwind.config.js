/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        olive: {
          50: "#f5f8ef",
          100: "#e8f0da",
          200: "#d4e2b5",
          300: "#b6ce87",
          400: "#98b95f",
          500: "#78953f",
          600: "#5b7430",
          700: "#445724",
          800: "#2d3b18",
          900: "#1b2411"
        },
        sand: {
          50: "#faf7f0",
          100: "#f2ead8",
          200: "#e8d8b9",
          300: "#ddc291"
        }
      },
      boxShadow: {
        soft: "0 14px 35px rgba(25, 35, 21, 0.18)"
      }
    },
  },
  plugins: [],
};

