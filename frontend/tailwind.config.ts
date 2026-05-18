import type { Config } from "tailwindcss";
import { theme } from "./src/theme";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: theme.colors.primary,
        "primary-dark": theme.colors.primaryDark,
        ink: theme.colors.ink,
        "ink-soft": theme.colors.inkSoft,
        surface: theme.colors.surface,
        border: theme.colors.border,
        success: theme.colors.success,
        pill: theme.colors.pill,
      },
      fontFamily: {
        sans: ['"Inter"', "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      borderRadius: {
        sm: theme.radius.sm,
        md: theme.radius.md,
        lg: theme.radius.lg,
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
