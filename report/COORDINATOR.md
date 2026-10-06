# Coordinator theo yêu cầu bổ sung

Repo gốc dùng Deep Agents và chưa có coordinator/base-agent riêng. Đã bổ sung mã triển khai ở `src/coordinator.py` và lớp cơ sở ở `src/base_agent.py` đúng đường dẫn trong đề. Import Coordinator bằng `from coordinator import Coordinator`. Module này độc lập với harness Deep Agents và chưa được nối vào `lab.runner`. Không thay thế Phần 2 về thí nghiệm trong `GUIDE.md`.

Worker kế thừa `BaseAgent`, được khởi tạo với `name`, `model`, `system_prompt`, `tools` và logger riêng. Worker triển khai phương thức abstract async `process_async(content)`. Kết quả worker là dict chứa `type` (`data`, `code`, `evaluation`) và `content`. Coordinator cũng chấp nhận worker tương thích cùng giao diện.

```python
from coordinator import Coordinator
from base_agent import BaseAgent

# workers là các đối tượng đáp ứng giao diện trên.
coordinator = Coordinator(worker_agents=workers)
result = coordinator.process({
    "task_type": "complex",
    "parameters": {"quarter": 3},
    "priority": "normal",
}, timeout=60)
```

- `parse_request`: nhận dict hoặc chuỗi JSON, kiểm tra task type, parameters và priority. Văn bản tự do cần truyền `model` hỗ trợ `.invoke()`; chỉ nhánh đó mới gọi mô hình. Không tự đoán bằng từ khóa khi yêu cầu mơ hồ.
- `route_task`: định tuyến data/code/evaluation/complex theo bảng cố định; báo lỗi nếu loại task hoặc worker không hợp lệ.
- `execute_tasks` / `aexecute_tasks`: nhận danh sách dict `id`, `worker`, `content`; chạy đồng thời, trả dict theo task ID. Mỗi record có status và result/error. Deadline áp dụng chung cho batch.
- `aggregate_results`: giữ tất cả record, phân nhóm nội dung, trả status success/partial/error. Nhiều kết quả cùng loại được giữ thành danh sách, không ghi đè.
- `execute_tasks_with_retry` / `aexecute_tasks_with_retry`: mặc định tối đa 2 lần chạy lại ngoài lần đầu; chỉ chạy lại task lỗi/timeout. Khi hết retry, ném `CoordinatorException` với `.results` giữ kết quả. Chỉ bật retry khi worker chịu được việc thực hiện lại.
- `process` / `aprocess`: nối toàn bộ luồng, gửi cả yêu cầu gốc và cấu trúc đã parse đến worker. Dùng API async khi ứng dụng đang có event loop.

Guardrail gồm giới hạn 32 task đang hoạt động mặc định, ID duy nhất, kiểm tra batch trước khi chạy, deadline, kiểm tra schema đầu ra và dọn coroutine khi caller hủy. Timeout cần worker hợp tác với asyncio cancellation; không thể cưỡng chế dừng subprocess hoặc coroutine nuốt cancellation. Deadline worker không bao gồm thời gian gọi mô hình để parse. Các priority được truyền đến worker, chưa dùng để lập lịch. `task_queue` được khởi tạo/lưu cho khả năng mở rộng; hiện việc giao task dùng gọi coroutine trực tiếp.

Logging dùng logger `coordinator`, ghi task ID, worker, start/end, thời gian và trạng thái/lỗi. Ứng dụng có thể cấu hình `logging.basicConfig(level=logging.INFO)`. Test dùng mock, không đọc khóa API và không gọi API mô hình.

Kiểm tra:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_02_coordinator.py tests/test_01_provided.py -q
.\.venv\Scripts\python.exe scripts/test_coordinator_standalone.py
```

Bộ test coordinator kiểm tra 14 trường hợp, gồm chạy đồng thời thực sự bằng barrier, partial result, timeout/cancellation, retry không lặp task thành công, input không hợp lệ, giới hạn task và luồng end-to-end. Standalone kiểm tra 3 trường hợp: một worker, nhiều worker, timeout/dọn task.

Kết quả Phần 2.4: pytest đạt `14 passed`; standalone đạt `3/3`. Script dùng model giả với các câu input mẫu, in parse/routing/kết quả/thời gian, bật logging start/end/status. Trường hợp timeout dùng 0,02 giây để kiểm tra nhanh; fallback được thực hiện rõ ràng trong script bằng coordinator có worker giả nhanh, không phải cơ chế fallback tự động của Coordinator.

Checklist Phần 2: đã đọc và triển khai `coordinator.py`, bổ sung `base_agent.py`, hoàn thành 5 hàm, timeout/exception/input validation/task limit/retry, test pytest và standalone. Routing dùng bảng tra cố định, không gọi mô hình. Input dict/JSON bỏ qua mô hình; văn bản tự do dùng model được truyền vào. Chưa triển khai cache phân loại văn bản tự do.
