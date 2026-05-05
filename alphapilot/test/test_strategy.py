from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv
from agents.strategy_agent import strategy_agent
from agents.strategy_agent import run_strategy_analysis

load_dotenv()

if __name__ == "__main__":
    # 模拟三个 Agent 的输出
    test_input = """
    Market Data: RSI 68.1（接近超买），MACD 金叉，看涨趋势。
    Fundamental: 营收增长 1%，EPS 下降 53%，毛利率 17.9%，但能源业务强劲。
    News Sentiment: Positive（0.8 分），Robotaxi 和 Semi 进展顺利。
    """
    
    # result = strategy_agent.invoke({
    #     "messages": [{
    #         "role": "user", 
    #         "content": f"请基于以下信息给出最终投资策略：\n{test_input}"
    #     }]
    # })
    result = run_strategy_analysis(f"请基于以下信息给出最终投资策略：\n{test_input}")

    print("=== Strategy Agent 测试结果 ===")
    print(result.model_dump_json(indent=2, ensure_ascii=False))
    # print(result["messages"][-1].content)