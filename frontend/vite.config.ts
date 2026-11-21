import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Dane referencyjne (werdykty, model oceny prawnej) leżą w katalogu głównym repo,
// dlatego serwer deweloperski może czytać pliki o poziom wyżej.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'node',
  },
});
