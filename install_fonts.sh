#!/bin/bash
echo "Installing Arabic fonts..."

# Create fonts directory
mkdir -p fonts

# Download and install Arabic fonts
wget -O fonts/amiri.zip "https://fonts.google.com/download?family=Amiri"
wget -O fonts/times.zip "https://fonts.google.com/download?family=Times%20New%20Roman"
wget -O fonts/tahoma.ttf "https://github.com/rastikerdar/tahoma-font/raw/master/tahoma.ttf"
wget -O fonts/arial.ttf "https://github.com/rastikerdar/vazir-font/raw/master/dist/Vazir.ttf"

# Extract zip files
unzip -o fonts/amiri.zip -d fonts/amiri/
unzip -o fonts/times.zip -d fonts/times/

# Copy TTF files to main fonts directory
find fonts/ -name "*.ttf" -exec cp {} fonts/ \;

echo "Fonts installation completed!"
