export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        'fg-primary': '#3b82f6',
        'fg-primary-dark': '#1d4ed8',
        'fg-accent': '#6366f1',
        'fg-danger': '#ef4444',
        'fg-success': '#22c55e',
        'fg-warning': '#f59e0b',
        'fg-dark': '#0a0f1e',
        'fg-surface': '#111827',
        'fg-card': '#1e2535',
        'fg-border': '#2a3349',
        'fg-muted': '#64748b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
        'gradient-dark': 'linear-gradient(180deg, #0a0f1e 0%, #111827 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-dot': 'bounceDot 1.2s ease-in-out infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'wave': 'wave 1.5s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
        'glow': 'glow 2s ease-in-out infinite',
      },
      keyframes: {
        bounceDot: {
          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: '0.4' },
          '40%': { transform: 'scale(1)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        wave: {
          '0%, 100%': { transform: 'scaleY(0.4)' },
          '50%': { transform: 'scaleY(1)' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 12px rgba(99,102,241,0.4)' },
          '50%': { boxShadow: '0 0 28px rgba(99,102,241,0.8)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};
