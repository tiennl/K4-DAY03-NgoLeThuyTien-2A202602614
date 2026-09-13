"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.

Đề tài: TRỢ LÝ TUYỂN DỤNG & SÀNG LỌC CV (Gợi ý 4.1 - DANH_SACH_DE_TAI.md)
  - Tool tra cứu : job_requirements_query  (lấy tiêu chí tuyển dụng + Hiring Manager của vị trí)
  - Tool hành động: send_interview_invite  (gửi thông báo lịch phỏng vấn cho ứng viên)
"""

import json
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Công cụ TRA CỨU thông tin (read-only)
    {
        "name": "job_requirements_query",
        "description": (
            "Tra cứu tiêu chí tuyển dụng chi tiết của một vị trí đang mở tại VinGroup bằng mã tin tuyển dụng "
            "(job_code). Trả về kỹ năng yêu cầu, số năm kinh nghiệm tối thiểu, bằng cấp, dải lương, số lượng "
            "cần tuyển và tên Hiring Manager phụ trách phỏng vấn vị trí đó."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "job_code": {
                    "type": "string",
                    "description": "Mã tin tuyển dụng cần tra cứu (ví dụ: 'JD-AI-001')"
                }
            },
            "required": ["job_code"]
        }
    },

    # Tool 2: Công cụ HÀNH ĐỘNG (ghi dữ liệu / gửi thông báo)
    {
        "name": "send_interview_invite",
        "description": (
            "Gửi thư mời phỏng vấn tới ứng viên và đăng ký lịch phỏng vấn vào hệ thống tuyển dụng. "
            "Chỉ gọi công cụ này khi đã xác định được người phỏng vấn phụ trách vị trí ứng tuyển."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidate_id": {
                    "type": "string",
                    "description": "Mã hồ sơ ứng viên nhận thư mời (ví dụ: 'UV2026001')"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian diễn ra buổi phỏng vấn (ví dụ: '09:00 20/09/2026')"
                },
                "interviewer_name": {
                    "type": "string",
                    "description": (
                        "Tên người phỏng vấn / Hiring Manager phụ trách vị trí. "
                        "Lấy từ trường 'hiring_manager' trong kết quả của công cụ job_requirements_query."
                    )
                }
            },
            "required": ["candidate_id", "datetime_str"]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

JOB_DATABASE = {
    "JD-AI-001": {
        "job_title": "Kỹ sư Trí tuệ Nhân tạo (AI Engineer)",
        "department": "Khối Công nghệ AI - VinAI",
        "level": "Middle",
        "required_skills": ["Python", "PyTorch", "Computer Vision", "MLOps cơ bản"],
        "min_experience_years": 2,
        "education": "Tốt nghiệp Đại học chuyên ngành CNTT / Khoa học Máy tính trở lên",
        "salary_range": "25.000.000 - 40.000.000 VNĐ",
        "headcount": 3,
        "status": "Đang tuyển",
        "hiring_manager": "TS. Trần Minh Quang"
    },
    "JD-DS-002": {
        "job_title": "Chuyên viên Phân tích Dữ liệu (Data Analyst)",
        "department": "Khối Dữ liệu & Phân tích - VinFast",
        "level": "Junior",
        "required_skills": ["SQL", "Python (Pandas)", "Power BI", "Thống kê ứng dụng"],
        "min_experience_years": 1,
        "education": "Tốt nghiệp Đại học chuyên ngành Toán tin / Kinh tế / CNTT",
        "salary_range": "15.000.000 - 25.000.000 VNĐ",
        "headcount": 2,
        "status": "Đang tuyển",
        "hiring_manager": "Ms. Nguyễn Thu Hà"
    },
    "JD-HR-003": {
        "job_title": "Chuyên viên Tuyển dụng (Talent Acquisition Specialist)",
        "department": "Khối Nhân sự - VinGroup",
        "level": "Senior",
        "required_skills": ["Sàng lọc CV", "Phỏng vấn hành vi", "Employer Branding", "HRIS"],
        "min_experience_years": 4,
        "education": "Tốt nghiệp Đại học chuyên ngành Quản trị Nhân lực / Kinh tế",
        "salary_range": "20.000.000 - 30.000.000 VNĐ",
        "headcount": 1,
        "status": "Tạm dừng tuyển",
        "hiring_manager": "Mr. Phạm Đức Long"
    }
}


def execute_job_requirements_query(job_code: str) -> str:
    """Thực thi tra cứu tiêu chí tuyển dụng theo mã tin tuyển dụng"""
    job = JOB_DATABASE.get(job_code.strip().upper())
    if job:
        return json.dumps({
            "status": "SUCCESS",
            "job_code": job_code.strip().upper(),
            "data": job
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": (
                f"Không tìm thấy tin tuyển dụng có mã '{job_code}' trong hệ thống. "
                f"Các mã đang mở: {', '.join(JOB_DATABASE.keys())}."
            )
        }, ensure_ascii=False)


def execute_send_interview_invite(
    candidate_id: str,
    datetime_str: str,
    interviewer_name: str = "Hội đồng Tuyển dụng VinGroup"
) -> str:
    """Thực thi gửi thư mời phỏng vấn và đăng ký lịch cho ứng viên"""
    return json.dumps({
        "status": "SUCCESS",
        "invite_id": f"INV-{candidate_id.strip().upper()}-2026",
        "candidate_id": candidate_id.strip().upper(),
        "interview_datetime": datetime_str,
        "interviewer": interviewer_name,
        "channel": "Email + SMS",
        "message": (
            f"Đã gửi thư mời phỏng vấn thành công tới ứng viên {candidate_id.strip().upper()} "
            f"vào lúc {datetime_str}, người phỏng vấn: {interviewer_name}."
        )
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "job_requirements_query": execute_job_requirements_query,
    "send_interview_invite": execute_send_interview_invite
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
