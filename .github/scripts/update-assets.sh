#!/usr/bin/env bash
set -euo pipefail

repo_root="$(pwd)"
assets_dir="$repo_root/assets/readme"
mkdir -p "$assets_dir"

# Remote endpoints (light-mode variants / defaults)
metrics_url="https://github-readme-stats.vercel.app/api?username=ho4ngTien&show_icons=true&theme=default&border_radius=10"
toplangs_url="https://github-readme-stats.vercel.app/api/top-langs/?username=ho4ngTien&layout=compact&theme=default&border_radius=10"
streak_url="https://github-readme-streak-stats.herokuapp.com/?user=ho4ngTien&theme=default&border_radius=10"
activity_url="https://github-readme-activity-graph.vercel.app/graph?username=ho4ngTien&theme=default&hide_border=true&border_radius=10"
quotes_url="https://quotes-github-readme.vercel.app/api?type=horizontal&theme=default"
theme_dark_gif="https://media.giphy.com/media/mEZoPCmHmQIpK3jRgn/giphy.gif"

declare -A files=(
  ["metrics-stats.svg"]="$metrics_url"
  ["top-langs.svg"]="$toplangs_url"
  ["streak.svg"]="$streak_url"
  ["activity-graph.svg"]="$activity_url"
  ["quotes.svg"]="$quotes_url"
  ["theme-widget.gif"]="$theme_dark_gif"
)

changed=false
for file in "${!files[@]}"; do
  url="${files[$file]}"
  tmp="$(mktemp)"
  echo "Downloading $url -> $file"
  if ! curl -fsSL "$url" -o "$tmp"; then
    echo "Warning: failed to fetch $url"
    rm -f "$tmp"
    continue
  fi
  dest="$assets_dir/$file"
  if [ -f "$dest" ]; then
    if ! cmp -s "$tmp" "$dest"; then
      mv "$tmp" "$dest"
      changed=true
      echo "Updated $file"
    else
      rm -f "$tmp"
      echo "No change: $file"
    fi
  else
    mv "$tmp" "$dest"
    changed=true
    echo "Created $file"
  fi
done

if [ "$changed" = true ]; then
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add "$assets_dir"
  if git commit -m "chore(readme): update readme assets [skip ci]"; then
    git push
  else
    echo "Nothing to commit"
  fi
else
  echo "No asset changes detected."
fi
