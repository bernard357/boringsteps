.PHONY: help setup posts serve build preview test clean rebase push \
	comments-build comments-deploy comments-test skills-check

DIST := documentation/.vitepress/dist
CACHE := documentation/.vitepress/cache
POSTS := documentation/public/posts.json

# Everything a production build depends on. New files under these globs are
# picked up automatically on the next make run.
SOURCES := $(shell find documentation -type f \
	\( -name '*.md' -o -name '*.mts' -o -name '*.ts' -o -name '*.css' -o -name '*.vue' \) \
	-not -path '$(DIST)/*' -not -path '$(CACHE)/*') \
	package.json scripts/build_posts.py \
	$(wildcard skills/*/scripts/*.py)

help:
	@echo "Targets:"
	@echo "  setup    Install dependencies (npm ci)"
	@echo "  posts    Build the blog index ($(POSTS)) from post frontmatter"
	@echo "  serve    Start the dev server with hot reload (localhost:5173)"
	@echo "  build    Force a static build into $(DIST)"
	@echo "  preview  Build if sources changed, then serve the built site"
	@echo "  test     Build if needed, then validate GFM+Mermaid rendering"
	@echo "  rebase   Pull and rebase the current branch onto origin/main"
	@echo "  push     Rebase onto origin/main, then push the current branch"
	@echo "  clean    Remove the built site, cache, and generated post index"
	@echo "  comments-build   SAM-build the comments back-end (comments/)"
	@echo "  comments-deploy  Deploy the comments back-end with sam deploy (guided first time)"
	@echo "  comments-test    Run comments unit tests and ruff (uv)"
	@echo "  skills-check     Run the map-reduce skill offline on its fixtures (uv)"

setup:
	npm ci

posts:
	python3 scripts/build_posts.py

serve: posts
	npm run dev

# File target: rebuild only when a source is newer than the last build.
# touch $(DIST) marks the directory current after a successful build, so
# `preview` skips the rebuild when nothing changed.
$(DIST): $(SOURCES)
	python3 scripts/build_posts.py
	npm run build
	@touch $(DIST)

# Explicit, unconditional build.
build:
	python3 scripts/build_posts.py
	npm run build
	@touch $(DIST)

# Build only if needed (via the $(DIST) dependency), then serve.
preview: $(DIST)
	npm run preview

# Build if needed, then validate the rendering-test page renders every
# GFM + Mermaid feature. Exits non-zero on any regression.
test: $(DIST)
	python3 scripts/test_rendering.py

rebase:
	git pull --rebase origin main

push: rebase
	git push

clean:
	rm -rf $(DIST) $(CACHE) $(POSTS)

# Comments back-end (AWS SAM, see comments/README.md).
comments-build:
	cd comments && sam build

# First run is guided and writes comments/samconfig.toml (gitignored).
comments-deploy: comments-build
	cd comments && sam deploy $(if $(wildcard comments/samconfig.toml),,--guided)

comments-test:
	cd comments && uv run pytest -q && uv run ruff check . && uv run ruff format --check .

# Agent skills (skills/, outside the VitePress source). Offline stub backend:
# no AWS credentials, no cost.
skills-check:
	uv run skills/map-reduce/scripts/map_reduce.py --dry-run skills/map-reduce/fixtures
