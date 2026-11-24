# Renaming the product

The product is called **pomale**. If you fork it under a different name, change:

1. `frontend/src/app/brand.ts`: `APP_NAME`, `APP_SHORT_NAME` (also feeds `index.html` and the web app manifest)
2. `backend/app/config.py`: `APP_NAME`
3. Image name in `compose.yaml` and the docs (`ghcr.io/<owner>/<name>`)
4. Repository URLs in `README.md`, `docs/self-hosting.md`, `.github/ISSUE_TEMPLATE/config.yml` and `.github/workflows/cla.yml`
5. Package names in `frontend/package.json` and `e2e/package.json` (cosmetic)
6. `LICENSE` required notice and `COMMERCIAL.md`

`git grep -i pomale` lists what is left. Internal identifiers (the IndexedDB name, the session cookie, the CSRF header and the `ht_` key prefix) are deliberately not part of the name: changing them would drop queued offline changes or sign everyone out.
