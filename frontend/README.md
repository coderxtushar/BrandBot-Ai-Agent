# Brand Bot web app

Next.js 16 (App Router) + Tailwind 4 + shadcn/ui (Radix) + Framer Motion + TanStack Query.

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, if the API isn't on :8000
npm run dev                  # http://localhost:3000
```

- `/` landing page
- `/studio` the app: brands, runs, drafts, visuals. `?run=<id>` opens a saved run.

Design: "risograph press". Fluorescent inks overprinting on cool paper. Tokens live in
`src/app/globals.css`; ink colours are signal (blue = actions, pink = AI at work, sun = highlights).
