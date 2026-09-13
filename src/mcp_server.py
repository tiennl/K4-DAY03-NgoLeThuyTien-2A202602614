"""
🔌 MODEL CONTEXT PROTOCOL (MCP) SERVER MODULE
Mô phỏng kiến trúc MCP Server (Client-Server Architecture) cung cấp công cụ chuẩn hóa.

Đề tài: TRỢ LÝ TUYỂN DỤNG & SÀNG LỌC CV
"""

import json
import sys
from typing import Dict, Any, List
from tools import TOOLS_SCHEMA, dispatch_tool_call

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class MCPRecruitmentServer:
    """
    Giả lập MCP Server tuân thủ chuẩn giao thức Model Context Protocol
    """
    def __init__(self, server_name: str = "vingroup-recruitment-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các Tools chuẩn giao thức MCP"""
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        [TASK 2.1] Thực thi request gọi Tool theo chuẩn MCP JSON-RPC 2.0

        Luồng xử lý:
        1. Chuyển yêu cầu xuống Tool Router qua dispatch_tool_call() -> nhận chuỗi JSON.
        2. Parse chuỗi JSON đó thành Python Dictionary.
        3. Đóng gói phản hồi theo đúng khung JSON-RPC 2.0 của giao thức MCP.
        """
        raw_result = dispatch_tool_call(tool_name, arguments or {})

        try:
            content = json.loads(raw_result)
        except json.JSONDecodeError as e:
            # Tool trả về chuỗi không phải JSON hợp lệ -> báo lỗi theo chuẩn JSON-RPC
            return {
                "jsonrpc": "2.0",
                "server": self.server_name,
                "tool": tool_name,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: kết quả Tool không phải JSON hợp lệ ({e})"
                }
            }

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content
        }



if __name__ == "__main__":
    print("==========================================================")
    print("🔌 KIỂM THỬ ĐỘC LẬP MCP SERVER (vingroup-recruitment-mcp-server)")
    print("==========================================================")

    server = MCPRecruitmentServer()
    tools = server.list_tools()
    print(f"✅ Khởi tạo thành công MCP Server: {server.server_name} (Version: {server.version})")
    print(f"📦 Số lượng Tools công bố: {len(tools)}")
    for t in tools:
        params = t.get("parameters", {})
        print(f"   - {t['name']}(" + ", ".join(params.get("properties", {}).keys()) + ")"
              f" | required={params.get('required', [])}")

    # Kiểm tra trạng thái TODO 1.2 (Tool Schema)
    invite_tool = next((t for t in tools if t.get("name") == "send_interview_invite"), None)
    if invite_tool and not invite_tool.get("parameters", {}).get("properties"):
        print("⏳ [TODO 1.2]: Tool 'send_interview_invite' chưa được định nghĩa properties trong 'src/tools.py'.")
    else:
        print("✅ [TODO 1.2]: Tool 'send_interview_invite' đã có schema đầy đủ.")

    # Kiểm tra trạng thái TODO 2.1 (call_tool)
    test_result = server.call_tool("job_requirements_query", {"job_code": "JD-AI-001"})
    if not test_result:
        print("⏳ [TODO 2.1]: Hàm call_tool() đang trả về rỗng. Hãy hoàn thiện TODO 2.1 trong 'src/mcp_server.py'!")
    else:
        print("✅ [TODO 2.1]: Test dispatch tool 'job_requirements_query' thành công:")
        print(f"   Phản hồi JSON-RPC: {json.dumps(test_result, ensure_ascii=False)}")

    # Kiểm tra thêm Tool hành động và nhánh lỗi NOT_FOUND
    invite_result = server.call_tool("send_interview_invite", {
        "candidate_id": "UV2026001",
        "datetime_str": "09:00 20/09/2026",
        "interviewer_name": "TS. Trần Minh Quang"
    })
    print(f"✅ [TEST] send_interview_invite: {json.dumps(invite_result['result'], ensure_ascii=False)}")

    notfound_result = server.call_tool("job_requirements_query", {"job_code": "JD-XX-999"})
    print(f"✅ [TEST] Nhánh NOT_FOUND: {json.dumps(notfound_result['result'], ensure_ascii=False)}")
