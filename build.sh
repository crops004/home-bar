#!/usr/bin/env bash

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies and build Tailwind
npm install
npm run build:css
