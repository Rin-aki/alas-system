# alas-system-frontend

## Environment variables

Create `alas-system-frontend/.env` from `.env.example` and adjust values for your environment.

- `VITE_API_BASE_URL`: backend API base URL
- `VITE_WS_FIX_URL`: fix page websocket URL
- `VITE_SCRCPY_BASE_URL`: dashboard instance jump URL
- `VITE_ALAS_BASE_URL`: dashboard ALAS jump URL

For Docker Compose builds, these variables are also supported via compose build args.

# Vue 3 + Vite

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).
