/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Serif editorial para títulos (estilo prensa financiera)
        display: ["var(--font-display)", "Georgia", "serif"],
        // Sans humanista para cuerpo
        body: ["var(--font-body)", "ui-sans-serif", "system-ui"],
        // Mono para tickers, precios, métricas
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // Paper background (cremas)
        paper: {
          DEFAULT: "#F2EDE4",
          deep: "#E8E1D4",
          dark: "#1B1816",
        },
        // Ink (negro tinta, no #000)
        ink: {
          DEFAULT: "#1B1816",
          light: "#3D3A36",
          muted: "#7A7368",
        },
        // Acentos
        bear: {
          DEFAULT: "#7A1F1F",     // rojo oscuro burdeos para shorts
          bright: "#C03B3B",
          soft: "#D9A3A3",
        },
        bull: {
          DEFAULT: "#1F4D2C",
          bright: "#2D7A41",
          soft: "#A3C7B0",
        },
        amber: {
          DEFAULT: "#C8842A",
        },
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
      animation: {
        "fade-up": "fadeUp 0.6s ease-out forwards",
        "ticker-tape": "tickerTape 60s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        tickerTape: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
    },
  },
  plugins: [],
};
