#!/bin/bash
# Test ARTLU.RUN → OpenClaw Integration

echo "🧪 Testing ARTLU.RUN → OpenClaw Integration"
echo "========================================="

# Load environment variables
if [[ -f ".env" ]]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found"
    exit 1
fi

echo "🔍 Configuration Check:"
echo "OPENCLAW_GATEWAY_URL: $OPENCLAW_GATEWAY_URL"
echo "OPENCLAW_API_KEY: ${OPENCLAW_API_KEY:0:10}..."
echo "OPENCLAW_GATEWAY_TOKEN: ${OPENCLAW_GATEWAY_TOKEN:0:10}..."
echo ""

# Test 1: OpenClaw Gateway Health Check
echo "🏥 Test 1: OpenClaw Gateway Health Check"
echo "----------------------------------------"

if curl -s -f "$OPENCLAW_GATEWAY_URL/health" >/dev/null; then
    echo "✅ OpenClaw Gateway is reachable"
else
    echo "❌ OpenClaw Gateway unreachable at $OPENCLAW_GATEWAY_URL"
    echo "💡 Make sure OpenClaw is running and check the URL"
    echo ""
fi

# Test 2: Mock Purchase Webhook
echo "🎬 Test 2: Mock Purchase Webhook"
echo "--------------------------------"

# Create test purchase data
TEST_MESSAGE="ARTLU_PURCHASE: Generate premium race report for Test User. Race: Western States 100 (western-states-100), Goal: 24:00, Location: Denver, CO, Purchase ID: test_123, Email: test@example.com"

echo "Sending test message to OpenClaw..."
echo "Message: $TEST_MESSAGE"
echo ""

# Test the OpenClaw message endpoint (this might need adjustment based on actual API)
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/openclaw_response.txt \
    -X POST "$OPENCLAW_GATEWAY_URL/api/message" \
    -H "Authorization: Bearer $OPENCLAW_GATEWAY_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"channel\": \"main\", \"message\": \"$TEST_MESSAGE\"}" 2>/dev/null)

HTTP_CODE="${RESPONSE: -3}"

if [[ "$HTTP_CODE" == "200" ]]; then
    echo "✅ Test message sent successfully to OpenClaw"
    echo "💡 Check your OpenClaw main session for the trigger message"
    echo "💡 The artlu-race-report skill should activate"
elif [[ "$HTTP_CODE" == "405" ]]; then
    echo "⚠️  Method not allowed - OpenClaw API endpoint may be different"
    echo "💡 Will use alternative trigger method in production"
else
    echo "❌ Failed to send message to OpenClaw (HTTP $HTTP_CODE)"
    if [[ -f /tmp/openclaw_response.txt ]]; then
        echo "Response: $(cat /tmp/openclaw_response.txt)"
    fi
fi

rm -f /tmp/openclaw_response.txt
echo ""

# Test 3: Database Connection
echo "🗄️  Test 3: Database & App Health"
echo "--------------------------------"

if python3 -c "
import sys
sys.path.append('.')
from models import get_all_races
races = get_all_races()
print(f'✅ Database connected - found {len(races)} races')
" 2>/dev/null; then
    echo "✅ Database and models working correctly"
else
    echo "❌ Database connection failed"
    echo "💡 Run: python3 setup.py"
fi

echo ""

# Test 4: API Key Validation
echo "🔑 Test 4: API Key Validation"
echo "-----------------------------"

if [[ "$OPENCLAW_API_KEY" == "dev-key" ]]; then
    echo "⚠️  Using default API key - update for production"
elif [[ ${#OPENCLAW_API_KEY} -lt 20 ]]; then
    echo "⚠️  API key seems too short"
else
    echo "✅ API key looks properly configured"
fi

echo ""
echo "🎯 Next Steps:"
echo "1. Deploy to Railway: ./deploy.sh"
echo "2. Make test purchase at https://artlu.run"
echo "3. Check OpenClaw logs for race report generation"
echo "4. Verify premium data appears on race page"
echo ""
echo "📊 Monitor Railway logs at: https://railway.app/project/[your-project]"