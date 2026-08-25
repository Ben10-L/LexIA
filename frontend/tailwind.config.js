/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          50: "#EFF6FF",
          100: "#DBEAFE",
          500: "#2563EB",
          600: "#1D4ED8",
          700: "#2563EB",
          800: "#1E40AF",
          900: "#1E3A8A",
          950: "#172554",
        },
        ivory: "#F7F7F8",
        sand: "#E5E7EB",
        slate: {
          50: "#F9FAFB",
          100: "#F3F4F6",
          200: "#E5E7EB",
          300: "#D1D5DB",
          400: "#9CA3AF",
          500: "#6B7280",
          600: "#4B5563",
          700: "#374151",
          800: "#111827",
          900: "#111827",
        },
        amber: {
          50: "#FFF7ED",
          200: "#FDBA74",
          700: "#C2410C",
          900: "#9A3412",
        },
      },
      boxShadow: {
        panel: "0 24px 70px rgba(17, 24, 39, 0.08)",
      },
    },
  },
  plugins: [],
};
