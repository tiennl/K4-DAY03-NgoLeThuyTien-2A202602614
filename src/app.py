"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).

Đề tài: TRỢ LÝ TUYỂN DỤNG & SÀNG LỌC CV
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPRecruitmentServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import get_llm_provider

load_dotenv()

# Nhãn tiếng Việt phục vụ hiển thị kết quả Observation ra câu trả lời cuối cùng
FIELD_LABELS = {
    "job_title": "Vị trí",
    "department": "Bộ phận",
    "level": "Cấp bậc",
    "required_skills": "Kỹ năng yêu cầu",
    "min_experience_years": "Số năm kinh nghiệm tối thiểu",
    "education": "Bằng cấp",
    "salary_range": "Mức lương",
    "headcount": "Số lượng cần tuyển",
    "status": "Trạng thái",
    "hiring_manager": "Hiring Manager",
}


def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def summarize_observation(obs_data: dict) -> str:
    """
    Tổng hợp câu trả lời dự phòng từ Observation của MCP Server.
    Chỉ dùng khi Agent chạm trần MAX_ITERATIONS mà LLM chưa kịp tự kết luận.
    Hàm render động theo dữ liệu trả về nên không phụ thuộc vào một đề tài cụ thể nào.
    """
    if not obs_data:
        return "Chưa nhận được dữ liệu từ MCP Server để tổng hợp câu trả lời."

    status = obs_data.get("status")
    if status == "NOT_FOUND":
        return obs_data.get("message", "Không tìm thấy thông tin được yêu cầu.")
    if status not in ("SUCCESS", None):
        return f"Phản hồi từ công cụ: {json.dumps(obs_data, ensure_ascii=False)}"

    data = obs_data.get("data")
    if isinstance(data, dict) and data:
        parts = []
        for key, value in data.items():
            label = FIELD_LABELS.get(key, key)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            parts.append(f"{label}: {value}")
        return "Kết quả tra cứu — " + "; ".join(parts) + "."
    if "message" in obs_data:
        return obs_data["message"]
    return f"Đã hoàn tất xử lý qua MCP Server: {json.dumps(obs_data, ensure_ascii=False)}"


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def run_react_agent(user_query: str, provider, mcp_server: MCPRecruitmentServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server.

    Vòng lặp chạy thật sự đa bước: mỗi Observation nhận từ MCP Server được nạp ngược
    vào lịch sử hội thoại cho lượt suy luận kế tiếp, cho tới khi LLM tự đưa ra Final Answer
    hoặc chạm trần MAX_ITERATIONS.

    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    step = 0
    trace_logs = []
    history = []            # Lịch sử chuẩn hóa nạp ngược cho LLM ở lượt kế tiếp
    last_obs_data = {}      # Observation gần nhất, dùng cho phương án dự phòng
    finished = False
    tools_list = mcp_server.list_tools()

    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        # Gọi LLM với Native Tool Calling Specs + toàn bộ Observation đã thu được
        llm_response = provider.generate_with_tools(
            user_query,
            tools_list,
            system_prompt=REACT_AGENT_SYSTEM_PROMPT,
            history=history
        )
        latency_ms = round((time.time() - step_start_time) * 1000, 2)

        thought = llm_response.get("thought", "Đang suy luận...")
        llm_source = llm_response.get("source", "unknown")
        print(f"🧠 [Thought]: {thought}")

        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp -> kết thúc
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms,
                "llm_source": llm_source
            })
            finished = True
            break

        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {}) or {}
            tool_call_id = llm_response.get("tool_call_id", f"call_{step}")

            print(f"🛠️ [Action Proposed]: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")

            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})

            if not obs_data:
                print("👁️ [Observation từ MCP Server]: {}")
                print(f"⚠️ [CHÚ Ý]: MCP Server không trả về 'result'. Phản hồi thô: {json.dumps(mcp_result, ensure_ascii=False)}")
                trace_logs.append({
                    "step": step,
                    "query": user_query,
                    "action_type": "TOOL_ERROR",
                    "thought": thought,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "observation": mcp_result,
                    "latency_ms": latency_ms,
                    "llm_source": llm_source
                })
                break

            obs_str = json.dumps(obs_data, ensure_ascii=False)
            print(f"👁️ [Observation từ MCP Server]: {obs_str}")
            last_obs_data = obs_data

            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "thought": thought,
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms,
                "llm_source": llm_source
            })

            # Nạp Action + Observation ngược vào lịch sử cho lượt suy luận kế tiếp
            history.append({
                "role": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                # Bản gốc phản hồi của SDK (nếu có) để Provider phát lại nguyên vẹn ở lượt sau.
                # Chỉ nằm trong history, không ghi vào trace log.
                "raw_content": llm_response.get("raw_content")
            })
            history.append({
                "role": "tool_result",
                "tool_name": tool_name,
                "content": obs_str,
                "tool_call_id": tool_call_id
            })
            continue

        # Trường hợp 3: Phản hồi không đúng định dạng -> dừng an toàn
        else:
            print(f"⚠️ [CHÚ Ý]: Phản hồi LLM không hợp lệ: {json.dumps(llm_response, ensure_ascii=False)}")
            break

    # Dự phòng: chạm trần MAX_ITERATIONS mà LLM chưa tự kết luận
    if not finished and last_obs_data:
        fallback_answer = summarize_observation(last_obs_data)
        print(f"\n🧠 [Thought]: Đã chạm giới hạn {MAX_ITERATIONS} vòng lặp. Tổng hợp kết quả từ Observation cuối cùng.")
        print(f"🏁 [Final Answer]: {fallback_answer}")
        trace_logs.append({
            "step": step + 1,
            "query": user_query,
            "action_type": "FINAL_ANSWER",
            "thought": f"Chạm giới hạn MAX_ITERATIONS={MAX_ITERATIONS}. Tổng hợp từ Observation cuối cùng.",
            "output": fallback_answer,
            "latency_ms": 0.0,
            "llm_source": "fallback-summarizer"
        })

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏢 VINGROUP AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("🎯 Đề tài: TRỢ LÝ TUYỂN DỤNG & SÀNG LỌC CV")
    print("==========================================================")

    provider = get_llm_provider()
    mcp_server = MCPRecruitmentServer()

    print(f"🔌 LLM Provider: {provider.__class__.__name__} (model: {getattr(provider, 'model_name', 'n/a')})")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")

    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Quy trình tuyển dụng tại VinGroup gồm những vòng nào?'")
        print("   - Tra cứu vị trí: 'Cho tôi xem tiêu chí tuyển dụng của vị trí JD-AI-001'")
        print("   - Gửi thư mời:   'Gửi thư mời phỏng vấn cho ứng viên UV2026003 lúc 14:00 22/09/2026'")
        print("   - Suy luận đa bước: 'Tra tiêu chí vị trí JD-DS-002 rồi mời ứng viên UV2026002 phỏng vấn lúc 10:00 21/09/2026 với đúng Hiring Manager'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Ứng viên / HR hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        tool_call_count = 0
        all_traces = []

        for tc in tests:
            print("\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

            if tc["question"].strip().startswith("TODO"):
                print("⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print("   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                tool_call_count += sum(1 for lg in logs if lg["action_type"] == "TOOL_EXECUTION")
                completed_count += 1

        print("\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        print(f"🛠️ [MCP TOOL CALLS]: Tổng {tool_call_count} lượt gọi Tool thành công qua MCP Server.")
        if all_traces:
            save_waterfall_trace(all_traces)
        print("💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all\n")

        sample_query = tests[1]["question"]
        print("--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu tiêu chí tuyển dụng) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
