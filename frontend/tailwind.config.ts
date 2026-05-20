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
        "ink-muted": theme.colors.inkMuted,
        bg: theme.colors.bg,
        surface: theme.colors.surface,
        "surface-alt": theme.colors.surfaceAlt,
        border: theme.colors.border,
        "border-strong": theme.colors.borderStrong,
        success: theme.colors.success,
        warning: theme.colors.warning,
        pill: theme.colors.pill,
        "pill-strong": theme.colors.pillStrong,
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
        sm: theme.shadow.sm,
        md: theme.shadow.md,
        xl: theme.shadow.xl,
        bar: theme.shadow.bar,
        primary: theme.shadow.primary,
      },
    },
  },
  plugins: [],
} satisfies Config;
