"""GUIDE Phần 1 - Định nghĩa subagent (tác tử con).   >>> SINH VIÊN CÀI ĐẶT <<<

Pseudo-code: guides/pseudocode/02_subagents.md
Kiểm tra:    pytest tests/test_02_agent.py
"""


def get_subagents() -> list[dict]:
    """Trả về danh sách subagent (ít nhất 2, tên khác nhau).

    Mỗi phần tử là một dict có các khóa bắt buộc:
      "name":          tên duy nhất (chữ thường, có thể có dấu gạch ngang)
      "description":   khi nào tác tử chính nên giao việc cho subagent này (viết như một hướng dẫn hành động)
      "system_prompt": chỉ dẫn cho subagent
    Gợi ý vai trò: explorer (đọc và báo cáo), implementer (thực hiện), reviewer (kiểm tra độc lập).
    """
    return [
        {"name": "explorer", "description": "Delegate investigation of files and requirements before implementation.",
         "system_prompt": "Inspect relevant files, identify constraints, and report evidence and paths. Do not modify files."},
        {"name": "implementer", "description": "Delegate focused code changes and execution of their checks.",
         "system_prompt": "Implement the assigned changes, run checks, and report actual modifications and results."},
        {"name": "reviewer", "description": "Delegate independent verification of code and generated artifacts.",
         "system_prompt": "Verify requirements against actual files and test output. Report concrete defects with evidence."},
    ]
