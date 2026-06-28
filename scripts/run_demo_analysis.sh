#!/usr/bin/env bash
# M5 Demo Analysis Script
# 调用 API analyze/stream，保存完整 report JSON
#
# 用法:
#   bash scripts/run_demo_analysis.sh 0700.HK
#   bash scripts/run_demo_analysis.sh AAPL
#
# 输出: Docs/demo/{SYMBOL}_analysis_$(date +%Y%m%d).json

set -euo pipefail

SYMBOL="${1:-0700.HK}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
LANGUAGE="${LANGUAGE:-zh}"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== M5 Demo: ${SYMBOL} full_analysis ===${NC}"

# 1. Register / Login (create demo user if needed)
echo "  Logging in..."
LOGIN_RESP=$(curl -s -X POST "${BASE_URL}/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_m5","password":"alphapilot"}' || true)

TOKEN_RESP=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_m5","password":"alphapilot"}')
TOKEN=$(echo "$TOKEN_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "  Token acquired"

# 2. Create session
echo "  Creating session..."
SESSION_RESP=$(curl -s -X POST "${BASE_URL}/sessions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"stock_symbol\":\"${SYMBOL}\"}")
SESSION_ID=$(echo "$SESSION_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "  Session: ${SESSION_ID}"

# 3. Run analysis (stream, capture done event)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="Docs/demo"
mkdir -p "$OUTPUT_DIR"
RAW_FILE="${OUTPUT_DIR}/${SYMBOL//./_}_raw_${TIMESTAMP}.txt"
REPORT_FILE="${OUTPUT_DIR}/${SYMBOL//./_}_analysis_${TIMESTAMP}.json"

echo -e "  Running analysis for ${SYMBOL} (2-3 min)..."
curl -s -N -X POST "${BASE_URL}/analyze/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{
    \"stock_symbol\": \"${SYMBOL}\",
    \"message\": \"请全面分析该股票并给出中线投资建议\",
    \"language\": \"${LANGUAGE}\",
    \"session_id\": \"${SESSION_ID}\"
  }" \
  --max-time 300 \
  > "$RAW_FILE"

echo "  Raw stream saved to: $RAW_FILE"

# 4. Extract and format report
python -c "
import json, sys, re
from pathlib import Path

with open('${RAW_FILE}') as f:
    raw = f.read()

# Find the done event
done_data = None
for line in raw.split('\n'):
    line = line.strip()
    if not line.startswith('data:'):
        continue
    try:
        d = json.loads(line[5:].strip())
        if d.get('type') == 'done':
            done_data = d
            break
    except:
        pass

if not done_data:
    print('ERROR: No done event found', file=sys.stderr)
    sys.exit(1)

# Build summary
guard = done_data.get('guard_check', {}) or {}
report = done_data.get('final_report', '') or ''
citations = done_data.get('citations', {}) or {}
ep = guard.get('evidence_packet', {}) or {}
de = ep.get('document_evidence', []) or []

markers = re.findall(r'\[doc:\s*\d+\]', report, re.IGNORECASE)

summary = {
    'symbol': '${SYMBOL}',
    'timestamp': '${TIMESTAMP}',
    'guard': {
        'is_valid': guard.get('is_valid'),
        'confidence': guard.get('confidence_score'),
        'output_level': guard.get('output_level'),
        'issues': guard.get('issues', []),
        'warnings': guard.get('warnings', []),
    },
    'document_evidence_chunks': len(de),
    'report_length': len(report),
    'doc_markers': markers,
    'section_headers': [s for s in ['核心发现', '交叉验证', '整体评估', '投资建议', '风险警告', '行动计划', '文档证据'] if s in report],
    'citations': {
        'chunk_ids': citations.get('chunk_ids', []),
        'doc_markers': citations.get('doc_markers', []),
    },
    'report': report,
    'valuation': done_data.get('target_price'),
}

out = '${REPORT_FILE}'
Path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(f'  Report saved to: {out}')

# Print quick stats
print(f'\\n  Guard Valid: {summary[\"guard\"][\"is_valid\"]} (confidence={summary[\"guard\"][\"confidence\"]})')
print(f'  Doc chunks: {summary[\"document_evidence_chunks\"]}')
print(f'  [doc:N] markers: {len(markers)}')
print(f'  Report length: {summary[\"report_length\"]} chars')
print(f'  Sections: {\", \".join(summary[\"section_headers\"])}')
print(f'  Citations: {summary[\"citations\"][\"chunk_ids\"]}')
"

echo ""
echo -e "${GREEN}=== M5 Demo ${SYMBOL} complete ===${NC}"
echo "  Report: ${REPORT_FILE}"
echo "  Raw stream: ${RAW_FILE}"
echo ""
echo "  Next: check Docs/demo/ for analysis samples"
