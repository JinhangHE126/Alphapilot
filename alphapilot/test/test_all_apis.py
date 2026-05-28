from pathlib import Path
import sys, requests, json
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://localhost:8001"

NO_PROXY = {"http": None, "https": None}

def test_api():
    print("🚀 开始 AlphaPilot 全接口集成测试...\n")

    # 0. 根路径
    r = requests.get(f"{BASE_URL}/", proxies=NO_PROXY)
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /        {r.status_code} {'OK' if ok else 'FAIL'}")

    # 0. 健康检查
    r = requests.get(f"{BASE_URL}/health", proxies=NO_PROXY)
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /health  {r.status_code} {'OK' if ok else 'FAIL'}")

    # 1. 分析接口
    r = requests.post(f"{BASE_URL}/analyze", proxies=NO_PROXY, json={
        "message": "请全面分析 TSLA 并给出中线投资建议",
        "stock_symbol": "TSLA"
    })
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /analyze  {r.status_code} {'OK' if ok else 'FAIL'}")

    # 2. 对比接口
    r = requests.post(f"{BASE_URL}/compare", proxies=NO_PROXY, json={
        "stock_symbols": ["TSLA", "NVDA"]
    })
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /compare  {r.status_code} {'OK' if ok else 'FAIL'}")

    # 3. 回测接口
    r = requests.post(f"{BASE_URL}/backtest", proxies=NO_PROXY, json={
        "stock_symbol": "TSLA",
        "strategy_desc": "买入持有策略"
    })
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /backtest {r.status_code} {'OK' if ok else 'FAIL'}")

    # 4. 警报接口
    r = requests.post(f"{BASE_URL}/alert", proxies=NO_PROXY, json={
        "stock_symbol": "TSLA",
        "condition": "价格跌破200日均线"
    })
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /alert    {r.status_code} {'OK' if ok else 'FAIL'}")

    # 5. 组合优化接口
    r = requests.post(f"{BASE_URL}/optimize", proxies=NO_PROXY, json={
        "stock_symbols": ["TSLA", "NVDA", "AAPL"],
        "risk_preference": "medium"
    })
    ok = r.ok
    print(f"{'✅' if ok else '❌'} /optimize {r.status_code} {'OK' if ok else 'FAIL'}")
    
    print("\n🎉 所有接口测试完成！")

if __name__ == "__main__":
    test_api()