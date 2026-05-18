export const theme = {
  colors: {
    primary: "#E02B20",
    primaryDark: "#B81F17",
    ink: "#1F1F1F",
    inkSoft: "#4A4A4A",
    bg: "#FFFFFF",
    surface: "#F7F7F8",
    border: "#E5E5E5",
    success: "#0E8C5A",
    pill: "#FDECEA",
  },
  fonts: { sans: '"Inter", -apple-system, "Segoe UI", sans-serif' },
  radius: { sm: "6px", md: "10px", lg: "16px" },
} as const;

export type Theme = typeof theme;
