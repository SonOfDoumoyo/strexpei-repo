# Streixpei web app

React 19, React Router 7, TanStack Query 5 and Tailwind CSS 4, built with Vite.

```bash
cp .env.example .env     # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm install
npm run dev              # http://localhost:5173
npm run build            # type-checks, then writes dist/
```

## Where things are

- `src/index.css`: colour tokens for light and dark mode. The brand gold is `--c-brand`. The accent themes (Gold, Diamond, Premium) unlock on a paid plan.
- `src/components/ui.tsx`: buttons, inputs, cards, tables, modals, drawers, badges and empty states. Every page is built from these.
- `src/lib/api.ts`: the API client.
  - The access token is kept in memory.
  - The refresh token is an httpOnly cookie, renewed once when several requests hit a 401 together.
  - Errors are returned as `ApiError` with a readable message.
- `src/pages/public`: the landing page, the staff join form (`/join/:code`) and the dev checkout.
- `src/pages/app`: the manager app.
- `src/pages/admin`: the platform console.
- `src/layouts/AppLayout.tsx`:
  - sidebar and workgroup switcher
  - ⌘K command palette
  - the SPI assistant panel

Deploy to Vercel or Netlify (configs are included), or use the `Dockerfile` (nginx). Set `VITE_API_BASE_URL` at build time.
