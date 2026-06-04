/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        background: "#0A0D0B",
        foreground: "#E7EEE9",
        card: "#121714",
        "card-foreground": "#E7EEE9",
        popover: "#121714",
        "popover-foreground": "#E7EEE9",
        primary: "#84CE39",
        "primary-foreground": "#0A0D0B",
        secondary: "#1A211D",
        "secondary-foreground": "#E7EEE9",
        muted: "#1A211D",
        "muted-foreground": "#8B978F",
        accent: "#1A211D",
        "accent-foreground": "#E7EEE9",
        destructive: "#FF5A5A",
        border: "#242C27",
        input: "#242C27",
        ring: "#84CE39",
        "garage-green": "#84CE39",
        "garage-green-deep": "#78BA30",
        "garage-blue": "#3B82F6",
        "garage-amber": "#F59E0B",
        "garage-magenta": "#EC4899",
        "garage-red": "#FF5A5A",
        "garage-elevated": "#1A211D",
        sidebar: "var(--sidebar)",
        "sidebar-foreground": "var(--sidebar-foreground)",
        "sidebar-primary": "var(--sidebar-primary)",
        "sidebar-primary-foreground": "var(--sidebar-primary-foreground)",
        "sidebar-accent": "var(--sidebar-accent)",
        "sidebar-accent-foreground": "var(--sidebar-accent-foreground)",
        "sidebar-border": "var(--sidebar-border)",
        "sidebar-ring": "var(--sidebar-ring)",
        "destructive-foreground": "var(--destructive-foreground)",
      },
      boxShadow: {
        "glow-primary": "0 0 24px rgba(132, 206, 57, 0.35)",
        "glow-primary-sm": "0 0 12px rgba(132, 206, 57, 0.25)",
      },
      fontFamily: {
        heading: ["Inter", "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({
        ".no-scrollbar::-webkit-scrollbar": {
          display: "none",
        },
        ".no-scrollbar": {
          "-ms-overflow-style": "none",
          "scrollbar-width": "none",
        },
      });
    },
  ],
};
