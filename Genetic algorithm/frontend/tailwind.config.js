/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        rc: {
          blue: "#3B4FE4",
          "blue-light": "#5B6EF7",
          "blue-dark": "#2D3DB8",
          green: "#00D9A5",
          "green-light": "#4AEDC4",
          "green-dark": "#00B589",
          violet: "#7C5CFF",
          "violet-light": "#9F7AFF",
          "violet-dark": "#5A3FCC",
        },
        page: "#F7F8FA",
        surface: "#FFFFFF",
        subtle: "#F1F3F7",
        heading: "#1A1D26",
        primary: "#2D3142",
        secondary: "#5A6178",
        muted: "#8B92A5",
        border: "#E2E5EB",
        "border-light": "#EBEEF3",
      },
      fontFamily: {
        heading: ["'Plus Jakarta Sans'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "'SF Mono'", "monospace"],
      },
      borderRadius: {
        rc: "12px",
      },
      boxShadow: {
        rc: "0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)",
        "rc-md": "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};
