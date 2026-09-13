# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Ngô Lê Thùy Tiên
> **Mã Sinh Viên / Mã Học viên:** 2A202602614
> **Chủ đề Lựa chọn:** Gợi ý 4.1 — Trợ lý Tuyển dụng & Sàng lọc CV (Tra cứu tiêu chí tuyển dụng vị trí & gửi thông báo lịch phỏng vấn)

---

## 0. TÓM TẮT KIẾN TRÚC & TOOL SPECS

| Thành phần | Giá trị |
| :--- | :--- |
| MCP Server | `vingroup-recruitment-mcp-server` (v2026.1.0) |
| Số Tool công bố qua MCP | 2 |
| Vòng lặp ReAct | `MAX_ITERATIONS = 5`, nạp ngược Observation vào lịch sử hội thoại mỗi lượt |

| Tool | Vai trò | Tham số (JSON Schema) | Bắt buộc |
| :--- | :--- | :--- | :--- |
| `job_requirements_query` | Tra cứu (read-only) | `job_code: string` | `job_code` |
| `send_interview_invite` | Hành động (ghi/gửi) | `candidate_id: string`, `datetime_str: string`, `interviewer_name: string` | `candidate_id`, `datetime_str` |

> 🔗 **Mắt xích suy luận đa bước:** trường `hiring_manager` nằm trong kết quả của `job_requirements_query`
> chính là giá trị Agent phải nạp vào tham số `interviewer_name` của `send_interview_invite`.
> Đây là lý do TC04 bắt buộc phải chạy qua 2 lượt gọi Tool nối tiếp nhau.

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | **5** / 5 | Nghiệp vụ mời phỏng vấn không thể hoàn tất trong một bước. Agent bắt buộc phải tra cứu tin tuyển dụng để biết Hiring Manager, rồi mới gửi được thư mời đúng người. Bước sau phụ thuộc trực tiếp vào đầu ra của bước trước. |
| **2. Tool Interaction** | **5** / 5 | Toàn bộ dữ liệu tiêu chí tuyển dụng nằm trong hệ thống ATS ngoài LLM, và việc gửi thư mời là hành động ghi dữ liệu ra thế giới thực. Không có Tool thì LLM chỉ có thể bịa. Cả 2 Tool đều được phục vụ độc lập qua MCP Server. |
| **3. Dynamic Decision** | **4** / 5 | Agent phải tự quyết định gọi Tool nào dựa trên câu hỏi (TC02 chỉ tra cứu, TC03 chỉ gửi thư mời, TC04 gọi cả hai), và phải đổi hướng khi Observation trả về `NOT_FOUND` (TC05). Chưa đạt 5 vì bộ Tool còn nhỏ và cố định, chưa có nhánh quyết định phân tầng sâu. |
| **4. Long Horizon Goal** | **3** / 5 | Mục tiêu "mời ứng viên phỏng vấn đúng Hiring Manager" được giữ xuyên suốt 3 lượt suy luận trong cùng một phiên. Tuy nhiên hệ thống chưa có Memory bền vững giữa các phiên, nên chân trời mục tiêu vẫn ngắn. |
| **TỔNG ĐIỂM AGENTIC FIT** | **17 / 20** | *Tổng điểm 17/20 > 12/20 → Bài toán rất phù hợp triển khai Agentic System thay vì Chatbot thuần.* |

**Kết luận Agentic Fit:** bài toán vượt xa ngưỡng 12/20. Điểm yếu duy nhất là Long Horizon Goal — nếu
nâng cấp lên Cấp 4 (Autonomous Agent) thì hướng mở rộng tự nhiên là thêm Memory lưu trạng thái pipeline
tuyển dụng của từng ứng viên qua nhiều phiên làm việc.

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

> ✅ **ĐÃ NGHIỆM THU TRÊN API THẬT.** Provider: `GeminiProvider`, model `gemini-3.1-flash-lite`
> (đổi từ `gemini-2.5-flash` do model này đã bị Google ngừng cấp cho tài khoản mới — lỗi `404 NOT_FOUND`
> khi gọi lần đầu). Toàn bộ 10/10 sự kiện trong `docs/trace_waterfall.json` đều có
> `"llm_source": "gemini:gemini-3.1-flash-lite"`, không có sự kiện nào rơi về `mock`.

Trích xuất TC04 — test case suy luận ReAct đa bước, thể hiện đầy đủ chuỗi
`Thought → Action → Observation → Thought → Action → Observation → Final Answer`,
**nguyên văn từ `docs/trace_waterfall.json` sinh ra bởi Gemini API thật**:

```json
[
  {
    "step": 1,
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'job_requirements_query' với tham số: {\"job_code\": \"JD-DS-002\"}",
    "tool_name": "job_requirements_query",
    "arguments": { "job_code": "JD-DS-002" },
    "observation": {
      "status": "SUCCESS",
      "job_code": "JD-DS-002",
      "data": {
        "job_title": "Chuyên viên Phân tích Dữ liệu (Data Analyst)",
        "min_experience_years": 1,
        "hiring_manager": "Ms. Nguyễn Thu Hà"
      }
    },
    "latency_ms": 8199.02,
    "llm_source": "gemini:gemini-3.1-flash-lite"
  },
  {
    "step": 2,
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'send_interview_invite' với tham số: {\"datetime_str\": \"10:00 21/09/2026\", \"candidate_id\": \"UV2026002\", \"interviewer_name\": \"Ms. Nguyễn Thu Hà\"}",
    "tool_name": "send_interview_invite",
    "arguments": {
      "datetime_str": "10:00 21/09/2026",
      "candidate_id": "UV2026002",
      "interviewer_name": "Ms. Nguyễn Thu Hà"
    },
    "observation": {
      "status": "SUCCESS",
      "invite_id": "INV-UV2026002-2026",
      "interviewer": "Ms. Nguyễn Thu Hà"
    },
    "latency_ms": 1190.24,
    "llm_source": "gemini:gemini-3.1-flash-lite"
  },
  {
    "step": 3,
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
    "output": "Tiêu chí tuyển dụng cho vị trí Chuyên viên Phân tích Dữ liệu (Data Analyst) (Mã: JD-DS-002)... Hiring Manager: Ms. Nguyễn Thu Hà. Tôi đã gửi thư mời phỏng vấn thành công cho ứng viên UV2026002 với... Người phỏng vấn: Ms. Nguyễn Thu Hà. Mã thư mời: INV-UV2026002-2026",
    "latency_ms": 5165.43,
    "llm_source": "gemini:gemini-3.1-flash-lite"
  }
]
```

👉 Điểm mấu chốt cần chú ý: giá trị `Ms. Nguyễn Thu Hà` **không có trong câu hỏi của người dùng**.
Chính Gemini đọc Observation ở Step 1 để lấy `hiring_manager`, rồi tự nạp giá trị đó vào tham số
`interviewer_name` khi gọi `send_interview_invite` ở Step 2. Đây là bằng chứng vòng lặp ReAct
hoạt động thật trên LLM thật, không phải một lần gọi Tool rời rạc và không phải suy luận giả lập.

### 🐛 Sự cố kỹ thuật đã gặp và cách xử lý khi nghiệm thu trên API thật

| Sự cố | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `404 NOT_FOUND: models/gemini-2.5-flash is no longer available` | Model mẫu trong `.env.example` đã bị Google ngừng cấp cho tài khoản mới | Đổi `LLM_MODEL` sang `gemini-3.1-flash-lite` (model hiện hành, đủ khả năng tool-calling cho bài lab) |
| `400 INVALID_ARGUMENT: Function call is missing a thought_signature` | Gemini 3.x yêu cầu giữ nguyên trường `thought_signature` khi phát lại lượt gọi Tool trước đó cho lượt suy luận kế tiếp | Sửa `src/providers.py`: lưu và phát lại nguyên vẹn `Content` object do SDK trả về, thay vì dựng lại bằng dict tay |
| `429 RESOURCE_EXHAUSTED: quota... limit 5, model gemini-3.6-flash` | Free tier chỉ cho 5 request/phút, trong khi 5 Test Cases cần ~10 lượt gọi LLM | Thêm cơ chế giãn cách (`LLM_MIN_INTERVAL_SECONDS`) + tự thử lại khi gặp 429 trong `src/providers.py`; đổi sang `gemini-3.1-flash-lite` có hạn mức cao hơn |

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini `gemini-3.1-flash-lite`).
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases *(chạy trên Gemini API thật, không rơi về Mock — xem cột `llm_source` trong `docs/trace_waterfall.json`)*
- **Số lượt gọi Tool qua MCP Server chính xác:** 5 lượt *(TC02: 1, TC03: 1, TC04: 2, TC05: 1; TC01 không gọi Tool — đúng kỳ vọng)*
- **Tổng số sự kiện ghi trong `docs/trace_waterfall.json`:** 10 sự kiện (5 `TOOL_EXECUTION` + 5 `FINAL_ANSWER`)
- **Kết quả đẩy Repo nộp bài:** [ ] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

### Bảng đối chiếu kỳ vọng từng Test Case

| ID | Loại | Tool được gọi | Số bước ReAct | Đạt kỳ vọng |
| :--- | :--- | :--- | :---: | :---: |
| TC01 | `direct_query` | *(không gọi Tool)* | 1 | ✅ |
| TC02 | `single_tool_query` | `job_requirements_query` | 2 | ✅ |
| TC03 | `action_tool_query` | `send_interview_invite` | 2 | ✅ |
| TC04 | `multi_step_reasoning` | `job_requirements_query` → `send_interview_invite` | 3 | ✅ |
| TC05 | `edge_case_handling` | `job_requirements_query` (trả `NOT_FOUND`) | 2 | ✅ |

**Nhận xét Anti-Hallucination (TC05):** khi tra mã `JD-XX-999` không tồn tại, Agent trả lại nguyên văn
thông báo `NOT_FOUND` kèm danh sách mã hợp lệ, không tự bịa ra tiêu chí tuyển dụng cho một vị trí không có thật.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
