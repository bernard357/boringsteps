# Boring steps

A blog and book site, authored in Markdown and published as a static
[VitePress](https://vitepress.dev/) site on
[GitHub Pages](https://docs.github.com/en/pages) at
[boringsteps.org](https://boringsteps.org).

## Layout

- `documentation/` — Markdown content and the VitePress project
  - `documentation/.vitepress/config.mts` — site configuration
  - `documentation/public/CNAME` — pins the custom domain across deployments
- `comments/` — serverless comments back-end (AWS SAM), see
  [comments/README.md](comments/README.md)
- `.github/workflows/deploy.yml` — build-and-publish pipeline
- `Makefile` — the single toolbox (see below)

## Make targets

| Target | Action |
| --- | --- |
| `make setup` | Install dependencies (`npm ci`) |
| `make serve` | Start the dev server with hot reload at `localhost:5173` |
| `make build` | Build the static site into `documentation/.vitepress/dist` |
| `make preview` | Serve the built site locally for a production check |
| `make clean` | Remove the built site and the VitePress cache |
| `make comments-test` | Run the comments unit tests and ruff (`uv`) |
| `make comments-build` | SAM-build the comments back-end |
| `make comments-deploy` | Deploy the comments back-end (`sam deploy`, guided the first time) |

## Local development

```shell
$ make setup
$ make serve
```

Open the printed `localhost:5173` URL. Edits to Markdown under
`documentation/` hot-reload in the browser.

To verify the production build before publishing:

```shell
$ make build
$ make preview
```

## Publishing

Pushing to `main` triggers `.github/workflows/deploy.yml`, which builds the
site and deploys it to GitHub Pages. One-time setup: in the repository
**Settings → Pages**, set the publishing **Source** to **GitHub Actions**.

The custom domain and HTTPS are configured per the GitHub Pages documentation:
verify `boringsteps.org` at the account level, add it in **Settings → Pages**,
point apex `A`/`AAAA` records and a `www` `CNAME` at GitHub, then enable
**Enforce HTTPS**.
