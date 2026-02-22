#!/bin/bash
# Tailscale Setup for ARTLU.RUN
# Provides reliable Railway → Mac mini connectivity

echo "🔗 Setting up Tailscale for Production Reliability"
echo "==============================================="

# Check if Tailscale is already installed
if command -v tailscale &> /dev/null; then
    echo "✅ Tailscale already installed"
    tailscale version
else
    echo "📦 Installing Tailscale..."
    echo "Note: This may require your password for system installation"
    
    # Download and install Tailscale
    curl -fsSL https://tailscale.com/install.sh | sh
    
    if [[ $? -ne 0 ]]; then
        echo "❌ Failed to install Tailscale"
        echo "💡 Alternative: Install manually from https://tailscale.com/download/mac"
        exit 1
    fi
fi

# Check if already connected
if tailscale status | grep -q "100\."; then
    echo "✅ Tailscale already connected"
    echo "Your Tailscale IP:"
    tailscale ip -4
    TAILSCALE_IP=$(tailscale ip -4)
else
    echo "🔐 Connecting to Tailscale..."
    echo "This will open your browser to authenticate"
    
    tailscale up
    
    if [[ $? -ne 0 ]]; then
        echo "❌ Failed to connect to Tailscale"
        exit 1
    fi
    
    echo "✅ Connected to Tailscale!"
    TAILSCALE_IP=$(tailscale ip -4)
fi

echo ""
echo "🎯 Your Mac mini's Tailscale IP: $TAILSCALE_IP"
echo ""
echo "🔧 Next Steps:"
echo "1. Update Railway environment variables:"
echo "   OPENCLAW_GATEWAY_URL=http://$TAILSCALE_IP:18789"
echo ""
echo "2. Test connectivity from Railway:"
echo "   curl -H 'Authorization: Bearer 5be46b22720e5259fe5752c4ef401a7b01b618288a4d87f8' \\"
echo "        http://$TAILSCALE_IP:18789/health"
echo ""
echo "3. Redeploy artlu.run with new Tailscale IP"
echo ""
echo "💡 Your Mac mini is now accessible from Railway via Tailscale!"
echo "   This provides reliable connectivity even if your home IP changes."