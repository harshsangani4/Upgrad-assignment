export const theme = {
  colors: {
    primary: "#E02B20",
    primaryDark: "#B81F17",
    ink: "#1F1F1F",
    inkSoft: "#4A4A4A",
    inkMuted: "#6E6E6E",
    bg: "#FFFFFF",
    surface: "#F7F7F8",
    surfaceAlt: "#F0F0F2",
    border: "#E5E5E5",
    borderStrong: "#D0D0D0",
    success: "#0E8C5A",
    warning: "#C47A00",
    pill: "#FDECEA",
    pillStrong: "#FAD5D1",
  },
  fonts: { sans: '"Inter", -apple-system, "Segoe UI", sans-serif' },
  radius: { sm: "6px", md: "10px", lg: "16px" },
  shadow: {
    none: "none",
    sm: "0 1px 2px rgba(0,0,0,0.04)",
    md: "0 4px 12px rgba(0,0,0,0.06)",
    xl: "0 12px 32px rgba(0,0,0,0.10)",
    bar: "0 -4px 12px rgba(0,0,0,0.05)",
    primary: "0 4px 14px rgba(224,43,32,0.30)",
  },
} as const;

export type Theme = typeof theme;
