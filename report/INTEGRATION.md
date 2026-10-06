# Phần 5.1: Test cases và hiệu suất

Tài liệu này giữ lịch sử các lần chạy; các dòng nói về TODO/lỗi ở giai đoạn đầu không phải trạng thái hiện tại. Báo cáo nộp bài và số liệu mới nhất nằm trong `REPORT.md`.

Đã tạo `tests/test_05_integration.py` với đúng 5 test trong đề: `test_coordinator_parse_request`, `test_coordinator_with_workers`, `test_full_pipeline`, `test_latency`, `test_concurrent_requests`. Dùng `asyncio.run` để chạy coroutine, không cần thêm pytest-asyncio. Routing model giả, còn workers, message queue, CSV tools, matplotlib subprocess và evaluator chạy thật cục bộ.

Đã bổ sung `src/system.py`: `MultiAgentSystem.process` chạy Coordinator rồi giao kết quả cho Evaluator, có deadline cho toàn pipeline. `Coordinator.handle_request` cung cấp API async. Task ID được tạo riêng theo UUID cho mỗi request để 10 request đồng thời không trùng ID.

Fixture Q3 có doanh thu tháng 7/8/9 bằng 100/150/250, tổng 500. Integration xác nhận tổng đúng, biểu đồ PNG được tạo và log có task/result. CodeAgent đọc cùng CSV để vẽ biểu đồ. Evaluator kiểm tra sự hiện diện đầu ra của các workers đã được gọi; điểm này không xác nhận tính đúng đắn của mọi nội dung. Test đối chiếu tổng 500 và định dạng PNG riêng.

Các lỗi đã sửa khi chạy test:

- ID `task-1` dùng lại giữa các request: thay bằng UUID theo request.
- Envelope evaluator chứa `request` như tham số tool: tách ngữ cảnh request khỏi dict `parameters`.

## Kết quả local

`tests/test_05_integration.py`: **5 passed**.

| Phép đo | Kết quả một lần chạy |
|---|---|
| Latency request phân tích CSV + evaluation | 0,0040 giây |
| 10 request đồng thời | 10/10 thành công |
| Thời gian batch 10 request | 0,0140 giây |
| Throughput batch | 713,19 request/giây |
| Full pipeline có tạo biểu đồ (pytest call duration) | 3,57 giây |

Số đo trên dùng model giả, dữ liệu rất nhỏ và chưa đo lặp/phân vị, không đại diện throughput/latency LLM thật. Luồng tạo biểu đồ chậm hơn luồng CSV; số đo bao gồm khởi động Python và import thư viện, chưa đủ để quy toàn bộ thời gian cho một thành phần.

Chạy toàn bộ tests với `--durations=10 --tb=line`: **50 passed, 16 failed**. 16 lỗi đều là `NotImplementedError` trong harness gốc: 9 test agent/subagents, 5 test runner, 2 test curator. Các hàm `make_backend`, `build_agent`, `get_subagents`, `run_task`, `curate_skills` chưa triển khai; đây là phạm vi lab Deep Agents gốc, không phải các component Coordinator/workers đã thêm theo đề đang làm. Không đánh dấu skip hay sửa test gốc để che lỗi.

## Kiểm tra mô hình thật

Đã thử `Coordinator.parse_request` với `lab.model.make_model()` dùng cấu hình `.env`. Provider trả HTTP 400: `invalid model ID`. Lần đo đầu thất bại sau 2,701 giây; đó là thời gian request lỗi, không phải latency thành công. Chưa có token usage hoặc kết quả pipeline LLM thật để báo cáo. Cần model ID hợp lệ trên endpoint đang cấu hình. Không ghi khóa API vào báo cáo.

Lệnh đã chạy: test riêng mục 5.1 với `-v -s --durations=10`; toàn bộ `tests/` với `--durations=10 --tb=line`; kiểm tra parse với model thật. Dùng Python của `.venv` trên Windows; pytest cần quyền truy cập thư mục tạm.

Chạy lại sau khi người dùng sửa model: provider đã trả phản hồi nhưng có khối Markdown JSON kèm lời giải thích. Đã sửa `parse_request` đọc một khối JSON duy nhất rồi tiếp tục kiểm tra schema. Lần kiểm tra thành công trả `task_type=data_analysis`, thời gian 3,193 giây, 71 input + 47 output = 118 token; metadata model là `gpt-4o-mini-2024-07-18`. Bộ test Coordinator vẫn đạt 14/14. Đây là kiểm tra parse_request thật, chưa phải toàn pipeline dùng LLM. Token nêu ở đây chỉ thuộc lần kiểm tra thành công, không phải tổng tất cả lần thử.

## Phần 5.2: Debug system

Đã thêm `src/logging_config.py`, `scripts/debug_agent.py`, `scripts/debug_system.py`. Cấu hình DEBUG tạo file UTF-8 `logs/coordinator.log`, `logs/communication.log`, `logs/data_agent.log`, `logs/code_agent.log`, `logs/evaluator_agent.log`, cùng log system/tools. Communication log là JSON Lines: mỗi dòng là một object event=send/receive/timeout, chứa metadata task/result. Log che các khóa nhạy cảm đã biết trong environment và trường secret/API key. Coordinator ghi parse/routing/start/end; workers ghi tên tools, trạng thái/lỗi và thời gian; system ghi kết quả và deadline.

Đã chạy debug_system với fixture local: CSV Q3 tổng 500, tạo `outputs/debug/report.txt`, evaluator kiểm tra sự hiện diện hai đầu ra. Đã chạy debug_agent cho data_agent với `SELECT * FROM sales --demo`: database demo có 3 dòng năm 2026/Q3. Cờ --demo chỉ tạo DB nếu chưa tồn tại. CodeAgent standalone chạy `print(2 + 3)` trả 5. Đã đọc log Coordinator/workers và parse tất cả dòng communication JSON. Đã chạy lại 5 test integration: 5/5 đạt.

`debug_system.py` mặc định chạy fixture local, không phân tích câu request tự do bằng model. Cờ `--live` dùng model đã cấu hình cho Coordinator/workers và tiêu tốn token; chưa chạy chế độ này ở bước 5.2. `debug_agent.py` chạy tools ngoại tuyến: SQL cho DataAgent, code cho CodeAgent, heuristic scoring cho Evaluator. Các script trả exit code khác 0 khi lỗi, và đóng DB/REPL sau khi chạy. `MultiAgentSystem.process(..., debug=True)` bật các ghi chú debug khi logger được cấu hình.

Để xử lý lỗi: đối chiếu task_id và in_reply_to trong communication với Coordinator; chạy agent riêng để phân biệt lỗi tool/DB và điều phối. Queue hiện không đặt maxsize, nên không có tình huống Queue.full; task limit ở Coordinator giới hạn task đồng thời. Có deadline và worker retry từ các bước trước; chưa thêm cơ chế retry LLM theo exponential backoff trong mục này. Phần 5.3 mới có tiêu đề, chưa triển khai profiling bổ sung.

## Phần 5.3: Performance profiling

Đã triển khai `scripts/profile_system.py`: mặc định 5 request tuần tự, `cProfile`, top 20 cumulative functions, P50/P99 bằng nội suy tuyến tính, throughput, thời gian xử lý workers, error rate và token metadata. Dùng `--live` để chạy LLM thật. Mỗi lần chạy lưu `metrics.json`, `profile.prof`, `top20.txt`, logs và fixture riêng trong `results/profiling/<UUID>/`.

| Metric | Mục tiêu | Local | LLM thật |
|---|---|---|---|
| P50 latency | < 5 giây | 0,086 giây | 11,866 giây |
| P99 latency | < 15 giây | 0,090 giây | 15,116 giây |
| Throughput attempts | > 10/phút | 703,23/phút | 5,61/phút |
| Worker utilization Data/Code/Evaluator | mỗi worker 70–90% | 4,83% / 16,65% / 2,54% | 84,40% / 0% / 0% |
| Error rate | < 1% | 0% | 100% (5/5 lỗi) |
| Tokens thực dùng trong 5 requests | theo dõi | 0 | 37.451 (35.881 input + 1.570 output) |
| Tokens/100 requests dự phóng | <= 150.000 | không áp dụng LLM | 749.020 |

Local artifacts: `results/profiling/d33398a6-937f-4603-89ca-976d78f04083/`. Live artifacts: `results/profiling/b2bdbe9a-50a6-4012-9b0e-377d0e760654/`.

Live không đạt các mục tiêu tổng thể. Coordinator phân loại 5 yêu cầu có phân tích và tạo báo cáo thành data_analysis, nên không gọi Code/Evaluator. DataAgent gặp lỗi chọn SQL cho CSV (`file is not a database`) hoặc lặp tool calls đến giới hạn agentic loop. Các lỗi nằm trong records và logs, không bị loại khỏi metrics. Throughput thành công của live là 0/phút; latency trên gồm cả requests lỗi, không phải latency thành công. Utilization Data 84,40% không có nghĩa chất lượng tốt vì mọi request đều lỗi.

Trong local profile, logging/format/redact chiếm khoảng 0,39 giây cumulative ở workload 0,43 giây; hàm redact khoảng 0,36 giây do duyệt environment cho nhiều trường JSON. Đây là bottleneck local có thể tối ưu sau. Live profile chủ yếu chờ event-loop/I/O; cProfile chỉ đo main thread, không đo trực tiếp CPU của worker threads hoặc subprocess. Số mẫu 5 quá ít để suy ra P99 hay error rate dài hạn; metrics là một lần chạy có profiling/logging overhead. Dự phóng token/100 không phải đo 100 requests.

## Sửa pipeline sau profiling

Đã sửa Coordinator nhận diện yêu cầu vừa phân tích vừa tạo artifact thành complex và chạy DataAgent trước CodeAgent, truyền kết quả thật qua upstream_data. DataAgent không được cấp SQL tools khi task ghi nguồn CSV. Prompt chọn phép tổng hợp CSV rõ ràng. Worker dừng trực tiếp khi tool phân tích/tạo báo cáo/scoring đơn bước đã trả kết quả hợp lệ; kết quả có cấu trúc được giữ, tránh vòng gọi LLM để diễn giải lại. Lời gọi tool giống hệt đã thực hiện bị chặn để tránh side effects/lặp vô hạn. Task có operation và tham số tool tường minh chạy trực tiếp, đặc biệt evaluator kiểm tra deterministic không cần LLM. Việc che secret trong logging dùng cache được refresh khi configure_logging để tránh duyệt environment cho mọi trường JSON.

Lần đo live đầu sau sửa: 5/5 success, P50 5,58 giây, P99 5,79 giây, 11,27 request/phút, 10.610 token. Sau bỏ LLM ở thao tác tường minh, artifacts cuối ở `results/profiling/60ee6948-526b-4377-8f93-465e341b31c2/`:

| Metric | Trước sửa live | Sau sửa live | Mục tiêu |
|---|---|---|---|
| P50 | 11,866s | 4,127s | <5s: đạt trong mẫu |
| P99 | 15,116s | 6,611s | <15s: đạt trong mẫu |
| Successful throughput | 0/phút | 13,154/phút | >10/phút: đạt trong mẫu |
| Error rate | 100% | 0% (5/5 success) | <1%: đạt trong mẫu |
| Tokens/5 requests | 37.451 | 5.879 | giảm 84,3% |
| Tokens/100 dự phóng | 749.020 | 117.580 | <=150.000: đạt dự phóng |
| Utilization Data/Code/Evaluator | 84,40% / 0% / 0% | 32,38% / 38,29% / 0,022% | chưa đạt 70–90% |

Đã đối chiếu log kết quả DataAgent (sum=500) và CodeAgent tạo báo cáo từ upstream_data. Các workers đều được gọi, evaluator kiểm tra trực tiếp sự hiện diện đầu ra. Chưa chạy 100 request; không khẳng định tỷ lệ lỗi <1% hay P99 dài hạn. Utilization theo thời gian awaited xử lý ở workload tuần tự có dependency không thể xem như CPU usage. Evaluator nhanh và các worker chờ upstream làm tỷ lệ thấp; không tạo công việc thừa để nâng tỷ lệ. Muốn đánh giá mức sử dụng tài nguyên cần workload đồng thời đại diện và định nghĩa capacity/CPU utilization riêng.

## Xác nhận cuối sau tối ưu (06/10/2026)

Các số liệu ở trên là lịch sử các lần đo. Kết quả mới nhất được cập nhật ở REPORT.md mục 5–6: toàn bộ 69/69 tests pass, coverage src 81,18%. Benchmark cuối 9/9 thành công, P50 3,429s, P99 6,769s, throughput 15,159/phút, 4.147 tokens (dự phóng 46.078/100 requests). Artifacts: results/benchmark/ba372709-4f7d-483e-8ef2-140ec36541ef/.

Profile thêm tùy chọn --concurrency và đo hợp các khoảng thời gian hoạt động worker. Workload báo cáo 10 requests, concurrency=3: 10/10 success, P50 2,550s, P99 2,917s, 58,968/phút, 6.561 tokens. Utilization Data/Code/Evaluator 47,031% / 62,345% / 0,102%; mục tiêu 70–90% cho mọi worker chưa đạt và không được giả lập bằng sleep/công việc thừa. Artifacts: results/profiling/d0bfca29-926b-4f8d-b991-4b4dc80549d0/.
