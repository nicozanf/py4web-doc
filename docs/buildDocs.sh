#!/bin/bash
set -xeuo pipefail
################################################################################
# File:    buildDocs.sh
# Purpose: Script that builds our documentation using sphinx and updates GitHub
#          Pages. This script is executed by:
#            .github/workflows/docs_pages_workflow.yml
#
# Authors: Michael Altfield <michael@michaelaltfield.net>
# Updated: 2025-12-22
# Version: 0.3
################################################################################

# Controls (set via env in CI):
# BUILD_RINOH=true to enable PDF (rinoh) builds (defaults to false in CI)
# BUILD_EPUB=true to enable EPUB builds (defaults to false in CI)
BUILD_RINOH=${BUILD_RINOH:-true}
BUILD_EPUB=${BUILD_EPUB:-true}

###################
# INSTALL DEPENDS #
###################

# Some CI runners may not need package installs; keep install attempts idempotent
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get -y install git rsync python3-sphinx python3-sphinx-rtd-theme python3-stemmer python3-git python3-pip python3-virtualenv python3-setuptools || true
fi

# Use virtualenv/venv when available in the environment (workflow should have created .venv)
if [ -f ".venv/bin/activate" ]; then
  . .venv/bin/activate
fi

# Ensure required Python packages are available in the active environment
python3 -m pip install --upgrade pip || true
python3 -m pip install --upgrade rinohtype pygments sphinx-rtd-theme sphinx-tabs docutils GitPython || true
python3 -m pip list || true

#####################
# DECLARE VARIABLES #
#####################

pwd
ls -lah
# mark repo safe for git operations in CI
git config --global --add safe.directory "$(pwd)"
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct || echo 0)

# make a new temp dir which will be our GitHub Pages docroot
docroot=$(mktemp -d)

export REPO_NAME="${GITHUB_REPOSITORY##*/}"

##############
# BUILD DOCS #
##############

# first, cleanup any old builds' static assets
make -C docs clean || true

# get a list of branches, excluding 'HEAD' and 'gh-pages'
# limit to remote branches only under refs/remotes/origin
versions="$(git for-each-ref --format='%(refname:lstrip=-1)' refs/remotes/origin/ | grep -viE '^(HEAD|gh-pages)$' || true)"

# If no versions found, fall back to the current branch
if [ -z "${versions}" ]; then
  versions="$(git rev-parse --abbrev-ref HEAD)"
fi

# Build controls:
ALL_VERSIONS=${ALL_VERSIONS:-false}      # set true to process all remote branches
MAX_VERSIONS=${MAX_VERSIONS:-5}          # hard-cap the number of branches to process
SPHINX_TIMEOUT=${SPHINX_TIMEOUT:-1800}  # timeout for each sphinx build in seconds (default 30m)

# If ALL_VERSIONS is false, prefer master/main only
if [ "${ALL_VERSIONS}" != "true" ]; then
  if git show-ref --verify --quiet refs/remotes/origin/master || git show-ref --verify --quiet refs/heads/master; then
    versions="master"
  elif git show-ref --verify --quiet refs/remotes/origin/main || git show-ref --verify --quiet refs/heads/main; then
    versions="main"
  fi
fi

# Limit number of versions to avoid runaway loops
if [ -n "$versions" ]; then
  versions="$(echo $versions | awk -v max="$MAX_VERSIONS" '{ for (i=1;i<=max && i<=NF;i++) printf "%s%s",$i,(i<max && i<NF?" ":"") }')"
fi

for current_version in ${versions}; do

   # make the current version available to conf.py
   export current_version
   # checkout branch (may result in detached HEAD on CI if using refs)
   git checkout ${current_version} || git checkout --detach ${current_version} || true

   echo "INFO: Building sites for ${current_version}"

   # skip this branch if it doesn't have our docs dir & sphinx config
   if [ ! -e 'docs/conf.py' ]; then
      echo -e "\tINFO: Couldn't find 'docs/conf.py' (skipped)"
      continue
   fi

   if [ -d "docs/locales" ]; then
     languages="en $(find docs/locales/ -mindepth 1 -maxdepth 1 -type d -exec basename '{}' \; 2>/dev/null || true)"
   else
     languages="en"
   fi

   for current_language in ${languages}; do

      # make the current language available to conf.py
      export current_language

      ##########
      # BUILDS #
      ##########
      echo "INFO: Building for ${current_language}"

      # HTML (always), with timeout
      echo "INFO: Running HTML build with timeout ${SPHINX_TIMEOUT}s"
      timeout ${SPHINX_TIMEOUT} python -m sphinx -b html docs/ docs/_build/html/${current_language}/${current_version} -D language="${current_language}" || {
        echo "ERROR: HTML build failed or timed out for ${current_language}/${current_version}"
        continue
      }

      # PDF (rinoh) - optional to avoid extremely long runs; enabled by BUILD_RINOH env var
      if [ "${BUILD_RINOH}" = "true" ]; then
        echo "INFO: Building PDF (rinoh) for ${current_language}"
        timeout ${SPHINX_TIMEOUT} python -m sphinx -v -b rinoh docs/ docs/_build/rinoh -D language="${current_language}" || echo "WARN: rinoh build failed for ${current_language} on ${current_version}"
        mkdir -p "${docroot}/${current_language}/${current_version}"
        if [ -f "docs/_build/rinoh/target.pdf" ]; then
          cp "docs/_build/rinoh/target.pdf" "${docroot}/${current_language}/${current_version}/${REPO_NAME}_${current_language}_${current_version}.pdf"
        else
          echo "WARN: rinoh produced no PDF for ${current_language}/${current_version}"
        fi
      else
        echo "INFO: Skipping rinoh (PDF) build. Set BUILD_RINOH=true to enable."
      fi

      # EPUB - optional
      if [ "${BUILD_EPUB}" = "true" ]; then
        echo "INFO: Building EPUB for ${current_language}"
        timeout ${SPHINX_TIMEOUT} python -m sphinx -b epub docs/ docs/_build/epub -D language="${current_language}" || echo "WARN: epub build failed for ${current_language} on ${current_version}"
        mkdir -p "${docroot}/${current_language}/${current_version}"
        if [ -f "docs/_build/epub/target.epub" ]; then
          cp "docs/_build/epub/target.epub" "${docroot}/${current_language}/${current_version}/${REPO_NAME}_${current_language}_${current_version}.epub"
        else
          echo "WARN: epub produced no file for ${current_language}/${current_version}"
        fi
      else
        echo "INFO: Skipping EPUB build. Set BUILD_EPUB=true to enable."
      fi

      # copy the static assets produced by the above build into our docroot
      mkdir -p "${docroot}/${current_language}/${current_version}"
      rsync -av "docs/_build/html/${current_language}/${current_version}/" "${docroot}/${current_language}/${current_version}/" || echo "WARN: rsync had problems for ${current_language}/${current_version}"

   done

done

# return to master branch (or attempt to restore original HEAD)
git checkout master || true

#######################
# Update GitHub Pages #
#######################

git config --global user.name "${GITHUB_ACTOR:-github-actions}"
git config --global user.email "${GITHUB_ACTOR:-github-actions}@users.noreply.github.com"

pushd "${docroot}"

# don't bother maintaining history; just generate fresh
git init
git remote add deploy "https://token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
git checkout -b gh-pages

# add .nojekyll to the root so that github won't 404 on content added to dirs
# that start with an underscore (_), such as our "_content" dir..
touch .nojekyll

# add redirect from the docroot to our default docs language/version
cat > index.html <<EOF
<!DOCTYPE html>
<html>
   <head>
      <title>${REPO_NAME} Docs</title>
      <meta http-equiv = "refresh" content="0; url='/${REPO_NAME}/en/master/'" />
   </head>
   <body>
      <p>Please wait while you're redirected to our <a href="/${REPO_NAME}/en/master/">documentation</a>.</p>
   </body>
</html>
EOF

# Add README
cat > README.md <<EOF
# GitHub Pages Cache

Nothing to see here. The contents of this branch are essentially a cache that's not intended to be viewed on github.com.


If you're looking to update our documentation, check the relevant development branch's 'docs/' dir.

For more information on how this documentation is built using Sphinx, Read the Docs, and GitHub Actions/Pages, see:

 * https://tech.michaelaltfield.net/2020/07/18/sphinx-rtd-github-pages-1
EOF

# copy the resulting html pages built from sphinx above to our new git repo
git add .

# commit all the new files
msg="Updating Docs for commit ${GITHUB_SHA} made on $(date -d"@${SOURCE_DATE_EPOCH}" --iso-8601=seconds) from ${GITHUB_REF} by ${GITHUB_ACTOR}"
git commit -am "${msg}" || echo "No changes to commit"

# overwrite the contents of the gh-pages branch on our github.com repo
git push deploy gh-pages --force || echo "WARN: failed to push gh-pages"

popd # return to main repo sandbox root

# exit cleanly
exit 0
