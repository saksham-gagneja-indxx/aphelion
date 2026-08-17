#!/bin/bash

# Set the API URL for production or use localhost for development
if [ -z "$VITE_API_URL" ]; then
  export VITE_API_URL="https://social-media-manager-api-wk5g.onrender.com"
fi

# Build the frontend
cd frontend
npm run build
