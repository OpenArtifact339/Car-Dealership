import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// React handles JSX; Tailwind processes utility classes during the Vite build.
export default defineConfig({ plugins: [react(), tailwindcss()] })
