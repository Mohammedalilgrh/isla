#!/bin/bash
echo "Starting build process on Render..."

# Install system dependencies for fonts
apt-get update
apt-get install -y wget unzip fontconfig

# Create fonts directory
mkdir -p fonts

# Download Arabic fonts
echo "Downloading Arabic fonts..."
wget -q -O fonts/amiri.zip "https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip"
wget -q -O fonts/noto.ttf "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf"

# Extract fonts
unzip -q -o fonts/amiri.zip -d fonts/
find fonts/ -name "*.ttf" -exec mv {} fonts/ \; 2>/dev/null || true

echo "Build process completed!"
