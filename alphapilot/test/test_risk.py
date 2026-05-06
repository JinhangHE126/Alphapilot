from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from agents.risk_agent import run_risk_assessment

load_dotenv()

if __name__ == "__main__":
    # 模拟前面 Agent 的输出
    test_input = """
    Market Data: RSI 68.1（接近超买），MACD 金叉，20日波动率 2.55%。
    Fundamental: 营收增长1%，EPS下降53%，但能源业务强劲。
    News Sentiment: Positive (0.8分)，Robotaxi 和 Semi 进展顺利。
    Strategy: Hold，信心55分。
    """
    
    result = run_risk_assessment(f"请基于以下信息进行全面风险评估：\n{test_input}")
    
    print("=== Risk Agent 测试结果 ===")
    print(result.model_dump_json(indent=2, ensure_ascii=False))