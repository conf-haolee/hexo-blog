# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run server     # Local preview at http://localhost:4000
npm run build      # Generate static files to public/
npm run clean      # Clear cache (db.json) and generated files
npm run deploy     # Build + push to GitHub Pages (conf-haolee.github.io, branch: main)
```

New post via Hexo CLI:
```bash
npx hexo new post "Post Title"
```

Fix Windows NTFS creation timestamps for .md files (run after cloning/moving files):
```bash
python fix_md_creation_time.py --only-posts   # fix source/_posts only
python fix_md_creation_time.py --dry-run      # preview without modifying
```

## Architecture

- **Framework**: Hexo 6.3.0 with Volantis theme
- **Theme config**: `_config.volantis.yml` (overrides theme defaults; site-level config is `_config.yml`)
- **Deploy target**: GitHub Pages at `conf-haolee/conf-haolee.github.io` via `hexo-deployer-git`
- **Encryption**: `hexo-blog-encrypt` — posts tagged `感悟` or `404实验室` are password-protected (passwords in `_config.yml`)
- **Asset folders**: `post_asset_folder: true` — each post gets a same-name folder for images/attachments

## Post Frontmatter

```yaml
---
title: Post Title
date: YYYY-MM-DD
tags:
  - TagName
categories:
  - [ParentCategory, SubCategory]   # nested array syntax for Hexo
pin: false
plugins:
  - mathjax   # enable LaTeX math rendering if needed
---
```

## Content Organization

Four top-level categories. Posts live under `source/_posts/` in matching subdirectories:
- `工作/` — work logs, machine vision, engineering projects
- `学习/` — programming tutorials, quick-reference guides, reading notes
- `生活/` — life notes (user-maintained)
- `科研/` — research notes (user-maintained)

The draft template `source/_drafts/博客模板头.md` is a frontmatter reference (not published).
