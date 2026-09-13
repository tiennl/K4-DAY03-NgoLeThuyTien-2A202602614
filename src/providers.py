"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.

📌 ĐỊNH DẠNG LỊCH SỬ HỘI THOẠI CHUẨN HÓA (provider-agnostic)
Tham số `history` là danh sách các lượt đã diễn ra SAU câu hỏi gốc của người dùng.
Mỗi phần tử có 1 trong 2 dạng:
  {"role": "tool_call",   "tool_name": str, "arguments": dict, "tool_call_id": str}
  {"role": "tool_result", "tool_name": str, "content": str(JSON), "tool_call_id": str}
Mỗi Provider tự dịch định dạng này sang khung Native Tool Calling của riêng mình,
nhờ đó vòng lặp ReAct trong app.py không phụ thuộc vào SDK cụ thể nào.
"""

import os
import sys
import re
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()


def _placeholder(key: Optional[str], placeholder_value: str) -> bool:
    """Kiểm tra API key có bị bỏ trống hoặc còn là chuỗi mẫu trong .env.example hay không"""
    return not key or key.strip() == "" or key.strip() == placeholder_value


# ==============================================================================
# ĐIỀU TIẾT NHỊP GỌI API & TỰ THỬ LẠI KHI BỊ GIỚI HẠN TỐC ĐỘ (RATE LIMIT)
# Gemini free tier chỉ cho 5 request/phút, trong khi chạy đủ 5 Test Cases cần ~10 request.
# ==============================================================================

RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s|'retryDelay': '(\d+)s'")
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
MIN_INTERVAL = float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "0"))

_last_call_ts = 0.0


def _throttle() -> None:
    """Giãn cách tối thiểu giữa 2 lần gọi API thật, tránh đụng trần request/phút"""
    global _last_call_ts
    if MIN_INTERVAL <= 0:
        return
    wait = MIN_INTERVAL - (time.time() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.time()


def _is_rate_limit(err: Exception) -> bool:
    text = str(err)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def _retry_delay(err: Exception, default: float = 60.0) -> float:
    """Đọc khoảng chờ do API đề nghị; nếu không có thì dùng mặc định"""
    match = RETRY_DELAY_RE.search(str(err))
    if match:
        seconds = match.group(1) or match.group(2)
        return min(float(seconds) + 2, 90.0)
    return default


def _call_with_retry(fn, label: str = "LLM API"):
    """Gọi API, tự chờ và thử lại khi bị rate limit. Lỗi khác thì ném ra ngay."""
    for attempt in range(MAX_RETRIES + 1):
        _throttle()
        try:
            return fn()
        except Exception as e:
            if _is_rate_limit(e) and attempt < MAX_RETRIES:
                delay = _retry_delay(e)
                print(f"⏳ [RATE LIMIT] {label} chạm trần request/phút. Chờ {delay:.0f}s rồi thử lại "
                      f"(lần {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(delay)
                continue
            raise


class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError


# ==============================================================================
# MOCK OFFLINE PROVIDER (chạy thử miễn phí, mô phỏng cả suy luận ĐA BƯỚC)
# ==============================================================================

JOB_CODE_RE = re.compile(r"\bJD-[A-Z]{2,4}-\d{3}\b", re.IGNORECASE)
CANDIDATE_RE = re.compile(r"\bUV\d{4,}\b", re.IGNORECASE)
DATETIME_RE = re.compile(r"\b\d{1,2}[:h]\d{2}\s*(?:ngày\s*)?\d{1,2}/\d{1,2}/\d{4}\b")

INVITE_KEYWORDS = ["mời phỏng vấn", "thư mời", "lịch phỏng vấn", "gửi thông báo", "phỏng vấn"]
JOB_KEYWORDS = ["tiêu chí", "yêu cầu tuyển dụng", "mô tả công việc", "tin tuyển dụng", "jd-"]


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. "
            f"(Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."
        )

    @staticmethod
    def _last_observation(history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Lấy Observation gần nhất mà MCP Server trả về"""
        for entry in reversed(history):
            if entry.get("role") == "tool_result":
                try:
                    return json.loads(entry.get("content", "{}"))
                except json.JSONDecodeError:
                    return {}
        return {}

    @staticmethod
    def _final_text(last_obs: Dict[str, Any]) -> str:
        """Tổng hợp câu trả lời cuối cùng từ Observation (mô phỏng bước kết luận của LLM)"""
        if not last_obs:
            return "[Mock Agent Response]: Chưa có dữ liệu từ công cụ để tổng hợp câu trả lời."
        if last_obs.get("status") == "NOT_FOUND":
            return f"[Mock Agent Response]: {last_obs.get('message', 'Không tìm thấy dữ liệu yêu cầu.')}"
        if "message" in last_obs:
            return f"[Mock Agent Response]: {last_obs['message']}"
        data = last_obs.get("data", {})
        if data:
            skills = ", ".join(data.get("required_skills", []))
            return (
                f"[Mock Agent Response]: Vị trí {data.get('job_title', '')} "
                f"({data.get('department', '')}) yêu cầu {data.get('min_experience_years', '')} năm kinh nghiệm, "
                f"kỹ năng: {skills}. Mức lương {data.get('salary_range', '')}. "
                f"Hiring Manager phụ trách: {data.get('hiring_manager', '')}."
            )
        return f"[Mock Agent Response]: {json.dumps(last_obs, ensure_ascii=False)}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        history = history or []
        called_tools = [h.get("tool_name") for h in history if h.get("role") == "tool_call"]
        last_obs = self._last_observation(history)

        q = prompt.lower()
        job_match = JOB_CODE_RE.search(prompt)
        cand_match = CANDIDATE_RE.search(prompt)
        dt_match = DATETIME_RE.search(prompt)

        wants_invite = any(k in q for k in INVITE_KEYWORDS)
        wants_job_info = bool(job_match) or any(k in q for k in JOB_KEYWORDS)

        # (1) Đã gửi thư mời xong -> kết luận
        if "send_interview_invite" in called_tools:
            return {
                "type": "text",
                "content": self._final_text(last_obs),
                "thought": "Đã hoàn tất gửi thư mời phỏng vấn. Tổng hợp kết quả trả lời người dùng.",
                "source": "mock"
            }

        # (2) Yêu cầu mời phỏng vấn cho một ứng viên cụ thể
        if wants_invite and cand_match:
            # (2a) Có mã vị trí nhưng chưa tra cứu -> phải tra cứu trước để biết Hiring Manager
            if job_match and "job_requirements_query" not in called_tools:
                return {
                    "type": "tool_call",
                    "tool_name": "job_requirements_query",
                    "arguments": {"job_code": job_match.group(0).upper()},
                    "thought": (
                        f"Người dùng muốn mời ứng viên phỏng vấn vị trí {job_match.group(0).upper()}. "
                        f"Tôi cần tra cứu tiêu chí tuyển dụng trước để biết Hiring Manager phụ trách."
                    ),
                    "source": "mock"
                }
            # (2b) Đã có thông tin vị trí (hoặc không cần) -> gửi thư mời
            interviewer = last_obs.get("data", {}).get("hiring_manager")
            arguments = {
                "candidate_id": cand_match.group(0).upper(),
                "datetime_str": dt_match.group(0) if dt_match else "09:00 20/09/2026"
            }
            if interviewer:
                arguments["interviewer_name"] = interviewer
            return {
                "type": "tool_call",
                "tool_name": "send_interview_invite",
                "arguments": arguments,
                "thought": (
                    f"Đã xác định người phỏng vấn là '{interviewer}'. Tiến hành gửi thư mời."
                    if interviewer else
                    "Người dùng yêu cầu gửi thư mời phỏng vấn cho ứng viên. Tiến hành gọi công cụ."
                ),
                "source": "mock"
            }

        # (3) Chỉ tra cứu tiêu chí tuyển dụng
        if wants_job_info and "job_requirements_query" not in called_tools:
            return {
                "type": "tool_call",
                "tool_name": "job_requirements_query",
                "arguments": {"job_code": job_match.group(0).upper() if job_match else "JD-AI-001"},
                "thought": "Người dùng muốn tra cứu tiêu chí tuyển dụng. Tôi sẽ gọi tool job_requirements_query.",
                "source": "mock"
            }

        # (4) Đã tra cứu xong, không cần hành động thêm -> kết luận
        if "job_requirements_query" in called_tools:
            return {
                "type": "text",
                "content": self._final_text(last_obs),
                "thought": "Đã nhận đủ dữ liệu từ MCP Server. Tổng hợp câu trả lời cuối cùng.",
                "source": "mock"
            }

        # (5) Câu hỏi chung -> trả lời trực tiếp không cần Tool
        return {
            "type": "text",
            "content": (
                "[Mock Agent Response]: Quy trình tuyển dụng tại VinGroup gồm 4 vòng: sàng lọc CV, "
                "phỏng vấn chuyên môn với Hiring Manager, phỏng vấn văn hóa với HR và gửi thư mời nhận việc."
            ),
            "thought": "Câu hỏi chung về quy trình tuyển dụng, trả lời trực tiếp không cần gọi Tool.",
            "source": "mock"
        }


# ==============================================================================
# GOOGLE GEMINI PROVIDER
# ==============================================================================

class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if _placeholder(self.api_key, "your_gemini_api_key_here"):
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    @staticmethod
    def _build_contents(prompt: str, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dịch lịch sử chuẩn hóa sang khung Content/Part native của Gemini"""
        contents: List[Any] = [{"role": "user", "parts": [{"text": prompt}]}]
        for entry in history:
            if entry.get("role") == "tool_call":
                # Gemini 3.x yêu cầu phần functionCall phải giữ nguyên 'thought_signature'.
                # Vì vậy ưu tiên phát lại đúng Content object mà SDK đã trả về;
                # chỉ dựng lại bằng dict khi không có bản gốc (ví dụ lượt do Mock sinh ra).
                raw_content = entry.get("raw_content")
                if raw_content is not None:
                    contents.append(raw_content)
                else:
                    contents.append({
                        "role": "model",
                        "parts": [{"function_call": {
                            "name": entry["tool_name"],
                            "args": entry.get("arguments", {})
                        }}]
                    })
            elif entry.get("role") == "tool_result":
                try:
                    payload = json.loads(entry.get("content", "{}"))
                except json.JSONDecodeError:
                    payload = {"raw": entry.get("content", "")}
                if not isinstance(payload, dict):
                    payload = {"result": payload}
                contents.append({
                    "role": "user",
                    "parts": [{"function_response": {
                        "name": entry["tool_name"],
                        "response": payload
                    }}]
                })
        return contents

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        history = history or []
        if _placeholder(self.api_key, "your_gemini_api_key_here"):
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            contents = self._build_contents(prompt, history)
            response = _call_with_retry(
                lambda: client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config
                ),
                label=f"Gemini ({self.model_name})"
            )

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                    "source": f"gemini:{self.model_name}",
                    "raw_content": response.candidates[0].content if response.candidates else None
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
                    "source": f"gemini:{self.model_name}"
                }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)


# ==============================================================================
# OPENAI PROVIDER
# ==============================================================================

class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if _placeholder(self.api_key, "your_openai_api_key_here"):
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dịch lịch sử chuẩn hóa sang khung messages native của OpenAI"""
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        for entry in history:
            if entry.get("role") == "tool_call":
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": entry.get("tool_call_id", "call_0"),
                        "type": "function",
                        "function": {
                            "name": entry["tool_name"],
                            "arguments": json.dumps(entry.get("arguments", {}), ensure_ascii=False)
                        }
                    }]
                })
            elif entry.get("role") == "tool_result":
                messages.append({
                    "role": "tool",
                    "tool_call_id": entry.get("tool_call_id", "call_0"),
                    "content": entry.get("content", "")
                })
        return messages

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        history = history or []
        if _placeholder(self.api_key, "your_openai_api_key_here"):
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = self._build_messages(prompt, system_prompt, history)
            response = _call_with_retry(
                lambda: client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None
                ),
                label=f"OpenAI ({self.model_name})"
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "tool_call_id": call.id,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                    "source": f"openai:{self.model_name}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
                    "source": f"openai:{self.model_name}"
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider_type == "gemini":
        if not _placeholder(os.getenv("GEMINI_API_KEY"), "your_gemini_api_key_here"):
            return GeminiProvider()
        print("⚠️ [PROVIDER]: LLM_PROVIDER=gemini nhưng GEMINI_API_KEY chưa hợp lệ -> dùng Mock Offline.")
        return MockOfflineProvider()
    elif provider_type == "openai":
        if not _placeholder(os.getenv("OPENAI_API_KEY"), "your_openai_api_key_here"):
            return OpenAIProvider()
        print("⚠️ [PROVIDER]: LLM_PROVIDER=openai nhưng OPENAI_API_KEY chưa hợp lệ -> dùng Mock Offline.")
        return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
