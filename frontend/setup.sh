#!/bin/bash

# AI Services Frontend - Dependency Resolution Script
# Run this script on your local machine to fix all dependency issues

echo "🔧 AI Services Frontend - Dependency Resolution"
echo "================================================"

# Step 1: Clean existing installation
echo "Step 1: Cleaning existing installation..."
rm -rf node_modules package-lock.json yarn.lock pnpm-lock.yaml

# Step 2: Clear npm cache
echo "Step 2: Clearing npm cache..."
npm cache clean --force

# Step 3: Update npm to latest version  
echo "Step 3: Updating npm..."
npm install -g npm@latest

# Step 4: Install with legacy peer deps flag
echo "Step 4: Installing dependencies..."
npm install --legacy-peer-deps

# Step 5: Run security audit
echo "Step 5: Running security audit..."
npm audit

# Step 6: Fix vulnerabilities
echo "Step 6: Fixing vulnerabilities..."
npm audit fix

# Step 7: Check for remaining issues
echo "Step 7: Final security check..."
npm audit

# Step 8: Verify installation
echo "Step 8: Verifying installation..."
npm run type-check

# Step 9: Test build
echo "Step 9: Testing production build..."
npm run build

echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. npm run dev    - Start development server"
echo "2. npm run lint   - Run linter"
echo "3. npm audit      - Check for vulnerabilities"
echo ""
echo "Demo accounts:"
echo "Admin: admin@aiservices.com / password123"
echo "User:  user@aiservices.com / password123"