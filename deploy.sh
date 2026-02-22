#!/bin/bash
# ARTLU.RUN Production Deployment Script

set -e  # Exit on any error

echo "🚀 ARTLU.RUN Production Deployment"
echo "=================================="

# Check current directory
if [[ ! -f "app.py" ]]; then
    echo "❌ Error: Must run from artlu-run directory"
    exit 1
fi

# Check environment file exists
if [[ ! -f ".env" ]]; then
    echo "❌ Error: .env file not found. Copy from .env.example and configure."
    exit 1
fi

# Check git status
if git status --porcelain | grep -q .; then
    echo "⚠️  Warning: You have uncommitted changes"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Commit and push changes
echo "📤 Deploying to Railway..."
git add .
git commit -m "Production deployment: OpenClaw webhook integration $(date '+%Y-%m-%d %H:%M')" || echo "No changes to commit"

# Force push to Railway (main branch)
echo "Pushing to Railway..."
git push origin main --force

# Display next steps
echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔧 Next Steps:"
echo "1. Set environment variables on Railway:"
echo "   OPENCLAW_API_KEY=742d93a61c1e275f95ac98d477026362ec40a3fa1c783786ad5ca4195fcb9ed0"
echo "   OPENCLAW_GATEWAY_URL=http://100.64.0.1:18789  # Use Tailscale IP when ready"
echo "   OPENCLAW_GATEWAY_TOKEN=5be46b22720e5259fe5752c4ef401a7b01b618288a4d87f8"
echo ""
echo "2. Test webhook integration:"
echo "   - Make a test purchase at https://artlu.run"
echo "   - Check Railway logs for OpenClaw forwarding"
echo "   - Verify race report generation in OpenClaw"
echo ""
echo "3. Set up Tailscale (run tailscale-setup.sh when ready)"
echo ""
echo "📊 Monitor at: https://railway.app/project/[your-project-id]"