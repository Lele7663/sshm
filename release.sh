#!/bin/bash

# Check if version is provided
if [ -z "$1" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 0.1.0"
    exit 1
fi

VERSION=$1

# Update version in setup.py
sed -i "s/version='[0-9]*\.[0-9]*\.[0-9]*'/version='$VERSION'/" setup.py

# Update version in PKGBUILD
sed -i "s/pkgver=[0-9]*\.[0-9]*\.[0-9]*/pkgver=$VERSION/" PKGBUILD

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build Python package
python setup.py sdist bdist_wheel

# Upload to PyPI
echo "Uploading to PyPI..."
twine upload dist/*

# Create git tag
git tag -a "v$VERSION" -m "Release version $VERSION"
git push origin "v$VERSION"

# Create AUR package
echo "Creating AUR package..."
mkdir -p aur
cp PKGBUILD aur/
cp .SRCINFO aur/  # You'll need to create this file

# Instructions for AUR
echo "
To release to AUR:

1. Create a new AUR package:
   git clone ssh://aur@aur.archlinux.org/sshm.git aur-sshm
   cd aur-sshm

2. Copy the release files:
   cp ../aur/* .

3. Update .SRCINFO:
   makepkg --printsrcinfo > .SRCINFO

4. Commit and push:
   git add .
   git commit -m 'Release version $VERSION'
   git push origin master
"

echo "Release process completed for version $VERSION" 