# LILITH public information site

Static pages served at `https://info.lilithos.si/` (Cloudflare Pages project `lilith-info`). They exist so the Google OAuth consent screen can link to a homepage, privacy policy and terms of service.

Separate from the LILITH OS app: no build step, no scripts, no cookies, no analytics, no web fonts; strict headers in `_headers`. The private app at `lilithos.si` stays behind Cloudflare Access and is not reachable from here.

Deploy (after review):

Deploy only the five site files (this README is not published): copy `index.html`, `site.css`, `_headers`, `privacy/` and `terms/` to a staging folder, then

```bash
npx wrangler pages deploy <staging-folder> --project-name lilith-info --branch main
```
