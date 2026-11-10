# Deployment

Build the frontend with `npm run build` and serve the `dist/` directory. The Vercel and Netlify SPA rewrites are included for direct route loads.

For nginx, use this location block:

```nginx
location / {
    try_files $uri /index.html;
}
```