#!/usr/bin/env node

const { execSync } = require('child_process');
const path = require('path');

// Set the API URL for production if not already set
if (!process.env.VITE_API_URL) {
  process.env.VITE_API_URL = 'https://social-media-manager-api-wk5g.onrender.com';
}

console.log('Building frontend with VITE_API_URL:', process.env.VITE_API_URL);

// Change to frontend directory and run the build
const frontendDir = path.join(__dirname, 'frontend');
execSync('npm run build', { cwd: frontendDir, stdio: 'inherit' });
