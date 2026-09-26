# invest-nav SEO 改动（手动同步 + GitHub Actions 部署）

Cloud Agent 无法 push `invest-nav` 时，用手机在 GitHub 网页完成上线。

## 1. GitHub Secrets

**推荐（Cloud Agent 已接好）：** 在 **invest-agent** 仓库添加（用于 `Deploy invest-nav (SEO)` workflow）：

`https://github.com/zhenfeng95/invest-agent/settings/secrets/actions`

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

（若改为只推 invest-nav 的 `main` 自动部署，也可把同名 Secret 配在 **invest-nav** 仓库。）

## 2. 同步文件到 invest-nav

在本目录按路径覆盖 `zhenfeng95/invest-nav` 同名文件：

| 本目录文件 | 目标路径 |
|-----------|----------|
| `seo-index.ts` | `utils/seo-index.ts` |
| `usePageSeo.ts` | `composables/usePageSeo.ts` |
| `nuxt.config.ts` | `nuxt.config.ts` |
| `sitemap.xml.ts` | `server/routes/sitemap.xml.ts` |
| `indexnow.ts` | `server/utils/indexnow.ts` |
| `.github/workflows/deploy.yml` | `.github/workflows/deploy.yml` |

或在本机 / Codespace：`git am output/invest-nav-seo-sitemap-noindex.patch`

## 3. 部署

推送到 `main` 后：`Actions → Deploy to Cloudflare` 自动运行；或手动 **Run workflow**。

## 4. 验证

- `https://zheninvest.com/sitemap.xml` 不应含 `/notes`、`/market`、`/tools`
- `curl -sI https://zheninvest.com/market | grep -i robots` 含 `noindex`
