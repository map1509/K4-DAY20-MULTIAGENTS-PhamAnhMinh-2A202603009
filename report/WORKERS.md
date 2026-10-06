# Phần 3.1: Worker Agent Pattern

Repo chưa có các file worker được nêu trong đề. Đã bổ sung `src/agents/base_worker.py`, `data_agent.py`, `code_agent.py`, `evaluator_agent.py`. `BaseWorker` kế thừa `BaseAgent`, cung cấp kiểm tra input, gọi tool, logging và chuyển lỗi tool thành `WorkerError` để Coordinator xử lý. Cancellation không bị nuốt.

| Worker | Tools riêng | System prompt và trách nhiệm |
|---|---|---|
| `data_agent` | `analyze_csv`, `query_sql`, `query_database`, `csv_parser`, `pandas_analysis`, `data_validation` | CSV, SQL chỉ đọc, pandas aggregation/group-by và kiểm tra dữ liệu thiếu |
| `code_agent` | `validate_python`, `write_file`, `edit_file`, `execute_python`, `run_script` | Kiểm tra cú pháp, tạo/sửa Python, thực thi code/script và báo kết quả; prompt yêu cầu luôn kiểm thử code |
| `evaluator_agent` | `score`, `validate`, `quality_check`, `feedback_generator` | Check theo expected, schema, trọng số accuracy/completeness/clarity/performance và định dạng feedback |

Mỗi worker có `name`, `model`, `system_prompt`, `tools` (dict theo tên) và `tool_map` cho xử lý ngoại tuyến. Không có model: `process_async(content)` nhận dict có `operation` và tham số tool, hoặc envelope `parameters` từ Coordinator; trả `{type: data/code/evaluation, content: ...}`. Task complex dùng `parameters.data_agent` và `parameters.code_agent` để giao thao tác riêng. Ví dụ ngoại tuyến:

```python
from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator

workers = [DataAgent(workspace="workspace"), CodeAgent(workspace="workspace"), EvaluatorAgent(workspace="workspace")]
coordinator = Coordinator(worker_agents=workers)
result = coordinator.process({
    "task_type": "data_analysis",
    "parameters": {"operation": "analyze_csv", "path": "sales.csv", "column": "amount"},
})
```

## Phần 3.2 và 3.3

`BaseWorker(name, model, tools)` nhận tool có `.name` và `.invoke(input)`. `process(task_content, parameters=None)` xây prompt qua `_build_prompt`, bind tools nếu model hỗ trợ, gọi model và thực thi tất cả tool calls qua `_execute_tool`. Hội thoại giữ đầy đủ AIMessage/ToolMessage theo ID. Hỗ trợ `args` của LangChain và `input` trong ví dụ đề. Vòng lặp mặc định tối đa 10 lượt có tool calls; sau đó chỉ chấp nhận câu trả lời cuối. Bộ đếm tool được cô lập theo task để không nhiễm giữa các lần chạy.

Thành công trả `status`, `result`, `metadata.tools_used`/`tool_names`; lỗi trả `status=error`, `error`, `result=None`. Có thêm `type`/`content` để tương thích Coordinator. Coordinator chuyển record worker lỗi thành task lỗi, không báo success. `process_async(task_content, parameters=None)` chạy `process` qua `asyncio.to_thread` khi có model, đúng mục đích thread pool trong đề. Hủy coroutine chờ không cưỡng chế dừng thread/model đang chạy; giới hạn vòng lặp không thay thế timeout mạng của provider.

Các subclass nhận model ở vị trí đầu tiên: `DataAgent(model, db_connection=None, workspace=".")`, `CodeAgent(model, workspace=".")`, `EvaluatorAgent(model, workspace=".")` (workspace là keyword-only). `DataAgent.db_connection` hiện nhận đường dẫn tương đối đến SQLite; không nhận connection sống của DB khác. Tool pandas đã được triển khai và khai báo dependency trong `pyproject.toml`. CodeAgent thực thi Python trong subprocess với timeout; không có phiên REPL giữ state giữa các lần gọi. Quality tool nhận bốn điểm tiêu chí 0-100, trọng số 30%/30%/20%/20%; tool không tự suy ra độ chính xác khi thiếu bằng chứng.

```python
worker = DataAgent(model=fake_or_real_model, workspace="workspace")
result = worker.process("Analyze sales in sales.csv", {"column": "amount"})
# Với ứng dụng async: await worker.process_async(...)
```

Test dùng model giả, không gọi API. Nếu truyền model thật và gọi worker thì sẽ sử dụng token của provider.

Tools tệp chặn đường dẫn ra ngoài workspace. Subprocess Python chỉ dùng cho code đáng tin cậy: thư mục làm việc và môi trường lọc khóa không tạo thành sandbox bảo mật, code vẫn có quyền hệ điều hành của process. Stdout/stderr được cắt khi trả kết quả nhưng được giữ trong bộ nhớ trong lúc thực thi. Tools đồng bộ chạy qua thread để không chặn event loop; cancellation không cưỡng chế dừng được thread đang chạy.

## Phần 3.4 và 3.5: Message Queue và giao tiếp

`src/communication/message_queue.py` có `MessageQueue`, `register_agent`, `send_message`, `receive_message`, `get_message_log`. Mỗi agent có mailbox `asyncio.Queue`; message có from/to/timestamp/id. Message log chứa dữ liệu JSON-compatible, lọc được theo agent; không sửa dict đầu vào hoặc trả tham chiếu có thể sửa log.

Coordinator mặc định tạo MessageQueue và đăng ký coordinator cùng workers. Khi chạy task, Coordinator gửi message type=task chứa task_id/content/parameters; consumer gọi worker và gửi message type=result về coordinator. `in_reply_to` liên kết phản hồi với UUID của task message, tránh nhầm kết quả khi nhiều workers trả khác thứ tự. Worker lỗi được chuyển thành phản hồi lỗi; deadline hủy consumer và listener còn chờ. Queue dùng trong bộ nhớ trên một event loop tại một thời điểm, không phải broker liên process.

API đồng bộ `execute_tasks(tasks, timeout=60, message_queue=None)` được giữ cho các bước trước. API async là `await aexecute_tasks(tasks, timeout=60, message_queue=queue)`; không gọi wrapper đồng bộ trong event loop. `asyncio.gather` dùng để chờ/dọn các coroutine bị hủy. Trong luồng có model chạy qua thread, việc hủy consumer không thể cưỡng chế dừng thread đã chạy.

```powershell
.\.venv\Scripts\python.exe scripts/test_communication.py
.\.venv\Scripts\python.exe -m pytest tests/test_03_workers.py -v
```

Kết quả mục 3.4/3.5: communication script đạt; workers giữ đúng 4 test theo đề, 4/4 đạt; bộ Coordinator hiện có vẫn đạt 14/14; standalone Coordinator đạt 3/3. Tất cả dùng mock, không gọi API mô hình.

## Phần 4: Tools integration

Đã bổ sung `src/tools/base_tool.py`, `database_tools.py`, `code_tools.py`, `evaluation_tools.py`. BaseTool quy định `name`, `description`, `validate_input`, `invoke`. QueryDatabaseTool dùng kết nối SQLite cache, chỉ đọc/SELECT, validation và giới hạn tối đa 1000 dòng; response có status/rows/columns/data, data tối đa 100 dòng. DataAgent dùng tool này cho `query_database`.

PythonREPLTool chạy trong subprocess giữ trạng thái giữa các lần gọi, giới hạn output 10000 ký tự, timeout mặc định 30 giây, bộ nhớ mặc định 1024 MiB. Trên Windows dùng Job Object giới hạn bộ nhớ process; lỗi thiết lập giới hạn làm process dừng. Timeout hủy process và reset state. `_repl_worker.py` là thành phần nội bộ để thực thi yêu cầu và trả JSON. API keys không được chuyển qua environment. Kiểm tra AST chặn imports nguy hiểm và truy cập không được phép; đây là môi trường cục bộ có hạn chế, không phải ranh giới bảo mật cho mã độc (thư viện được cho phép vẫn có khả năng truy cập hệ điều hành).

CreateFileTool tạo file UTF-8 trong base_path, chặn đường dẫn tuyệt đối, traversal và đường dẫn resolve ra ngoài thư mục. ScoringTool trả scores/weighted_score/grade; có thể nhận điểm tiêu chí tường minh hoặc dùng heuristic văn bản minh họa của đề. Heuristic không xác minh độ chính xác thực tế, trường method nêu cách chấm. ValidationTool kiểm tra các field bắt buộc. CodeAgent và EvaluatorAgent đã tích hợp các tool này.

Kết quả: đúng 4 test trong `tests/test_04_tools.py` đạt, 4 test workers vẫn đạt. `scripts/test_tool_integration.py` đạt 3/3: DataAgent lấy 50 dòng sales năm 2026, CodeAgent dùng số liệu đó tạo `outputs/sales_chart.png`, Evaluator tính điểm 85/B từ điểm rubric đầu vào rồi kiểm tra format. Script dùng SQLite tạm và matplotlib cục bộ; không gọi mô hình. Đã thêm matplotlib vào dependencies.

Test `tests/test_03_workers.py` kiểm tra CSV, SQL chỉ đọc, dữ liệu lỗi, tool fail, code tạo/sửa/thực thi/timeout, khóa không được chuyển qua env, validation/scoring, đường dẫn và luồng Coordinator với workers thật. Không gọi API mô hình.

Kết quả: `python -m pytest tests/test_03_workers.py tests/test_02_coordinator.py -v` đạt **21 passed** (7 test workers và 14 test Coordinator). Lần chạy trong sandbox bị chặn quyền thư mục tạm của pytest; chạy lại với quyền được cấp đã đạt.

Sau mục 3.2/3.3: chạy thêm `tests/test_03_base_worker.py`, tổng **28 passed**. Test bao gồm nhiều tools trong một lượt, lịch sử nhiều lượt, reset metadata, `input`/`args`, sync/async, lỗi model/tool, giới hạn vòng lặp, bind tools, pandas group-by, scoring có trọng số, chạy script và luồng Coordinator với model giả.
