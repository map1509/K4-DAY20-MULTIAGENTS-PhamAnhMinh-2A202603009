# Báo cáo Lab: Self evolving Agentic

> Sao chép tệp này thành `report/REPORT.md` (đã làm ở Phần 0) và điền dần qua các Phần của lab. Xóa các dòng hướng dẫn dạng trích dẫn (bắt đầu bằng `>`). Văn phong kỹ thuật, ngắn gọn, mọi nhận định đi kèm số liệu hoặc bằng chứng. Trong buổi học: điền mục 1 đến 7 (bản nháp). Sau buổi học: hoàn thiện mục 8 đến 10.

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| | | |

- Nhà cung cấp và mô hình (`LAB_MODEL`, không ghi khóa API), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`:
- Phiên bản Deep Agents (`pip show deepagents`), hệ điều hành, chạy trực tiếp hay trong Docker:
- Số lần chạy tác vụ đã dùng / ngân sách:
- Commit của tag `freeze`:

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

> Dự đoán điều kiện nào đạt điểm cao nhất trên **tác vụ đánh giá** và vì sao. Nêu căn cứ từ phân loại lỗi (mục 4) và từ tài liệu tham khảo. Điền cả ba dòng; `verify_freeze.py` kiểm tra điều này.

- H1 (subagents so với baseline):
- H2 (skills-auto so với baseline):
- H3 (tác vụ học so với tác vụ đánh giá):

## 3. Làm quen Deep Agents (Phần 0.3)

Đã đọc `README.md`, `GUIDE.md`, cấu hình trong `pyproject.toml`, các module `src/lab/` và pseudo-code định nghĩa subagent. Repo dùng `GUIDE.md`, không có `LAB_GUIDE.md`. Đã chạy `.venv\Scripts\python.exe scripts/tour.py` bằng mô hình giả, không gọi API mô hình.

**Trả lời theo mục 0.3 của GUIDE trong repo:**

1. Tác tử mặc định có 9 công cụ: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `execute`, `task`. `execute` cho phép chạy lệnh shell trong sandbox, trả về stdout/stderr và mã thoát.
2. Subagent `general-purpose` nghiên cứu câu hỏi phức tạp, tìm tệp/nội dung và thực hiện tác vụ nhiều bước; có quyền truy cập tất cả công cụ như tác tử chính. Mỗi lần gọi mặc định là một phiên độc lập: subagent chỉ thấy prompt được gửi, không tự nhận toàn bộ lịch sử hội thoại của tác tử chính, và trả về một báo cáo cuối.
3. Tour xác nhận system prompt mặc định là chuỗi rỗng (`''`). Câu hướng dẫn từ `task`: “The agent's report is not shown to the user; relay a summary yourself.” Câu hướng dẫn từ `execute`: “Use read_file rather than cat/head/tail.” Các mô tả công cụ vẫn hướng dẫn hành vi dù system prompt mặc định rỗng. Khi triển khai harness của lab, `build_agent` sẽ dùng `BASE_PROMPT` có sẵn thay cho prompt rỗng.

**Trả lời 3 câu trong yêu cầu Phần 0 được cung cấp:**

1. **Có bao nhiêu agent, mỗi agent làm gì?** Cấu hình mặc định có 2 loại tác tử: tác tử chính (đóng vai trò điều phối và trực tiếp xử lý công việc) và subagent `general-purpose` có sẵn. Điều kiện `subagents` yêu cầu định nghĩa thêm ít nhất 2 subagent tên khác nhau; pseudo-code gợi ý `explorer` đọc và khảo sát, `implementer` sửa/tạo tệp và chạy kiểm tra, `reviewer` kiểm tra độc lập. Đây mới là vai trò gợi ý: `get_subagents()` hiện còn TODO, nên chưa thể khẳng định số hoặc tên subagent chuyên biệt thực tế. Curator là thành phần gọi mô hình để sinh skill từ phản hồi/vết của tác vụ học, chạy ở giai đoạn riêng; runner và grader là mã điều hành/chấm điểm, không phải worker agent. Ba điều kiện `baseline`, `subagents`, `skills-auto` là cấu hình thí nghiệm, không phải 3 agent.
2. **Coordinator giao tiếp với worker bằng cách nào?** Tác tử chính gọi công cụ `task`, chọn `subagent_type` và gửi prompt mô tả công việc. Prompt cần chứa đủ yêu cầu, quy tắc và đường dẫn vì ngữ cảnh mặc định được cô lập. Subagent thực hiện công việc rồi trả một báo cáo cuối qua kết quả công cụ; tác tử chính kiểm tra báo cáo trước khi sử dụng. `SUBAGENTS_NOTE` trong `agent.py` quy định cách giao việc này; repo không định nghĩa cơ chế message queue riêng.
3. **Tools nào được chia sẻ?** Tour xác nhận `general-purpose` truy cập tất cả tools như tác tử chính: 7 tools thao tác/tìm kiếm tệp (`ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`), shell `execute`, và giao việc `task`. Backend sandbox cung cấp môi trường tệp/shell. Cấu hình tools riêng cho subagent chuyên biệt chưa được triển khai. Skill là ngữ cảnh hướng dẫn, không phải tool: `general-purpose` mặc định thừa kế skill của tác tử chính, còn subagent tự định nghĩa cần cấu hình `skills` riêng. Runner dự kiến ghi `run.json` và `trace.md` để đo đạc/quan sát; đây không phải tools logging mà agent gọi. Repo không khai báo tool knowledge-base retrieval riêng.

Kiểm tra cấu hình: `deepagents==0.7.21` trong `pyproject.toml`; `runner.py` định nghĩa ba điều kiện thí nghiệm; `agent.py` có sẵn `PATHS_NOTE`, `BASE_PROMPT`, `SKILLS_NOTE`, `SUBAGENTS_NOTE`. Các hàm triển khai harness vẫn còn TODO và thuộc Phần 1 trở đi. `.gitignore` có dòng `.env`; `git check-ignore .env` trả về `.env`.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

> Chỉ dùng tác vụ học. Mỗi dòng là một check thất bại.

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| | | | |

Nhận xét: nhóm lỗi nào chiếm đa số? Skill có thể phòng ngừa nhóm đó không?

## 5. Test Results

Kiểm tra ngày 06/10/2026 trên Windows, Python trong `.venv`.

| Nhóm test theo đề bài Coordinator/Workers/Tools | Kết quả |
|---|---|
| Coordinator (`test_02_coordinator.py`) | 14/14 passed |
| Workers (`test_03_workers.py`) | 4/4 passed |
| Tools (`test_04_tools.py`) | 4/4 passed |
| Integration/E2E/performance (`test_05_integration.py`) | 5/5 passed |
| Tổng các nhóm trên | 27/27 passed |

Integration kiểm tra coordinator với workers, toàn bộ pipeline, latency và 10 yêu cầu đồng thời. Test sử dụng mock hoặc thao tác local, không dùng kết quả benchmark LLM thay cho unit test.

Chạy toàn bộ: `.venv\Scripts\python.exe -m pytest tests/ -o addopts='-p no:cacheprovider' -q --tb=line` → **50 passed, 16 failed trong 31,41 giây**. Các lỗi còn lại thuộc lab Deep Agents gốc: 9 ở `test_02_agent.py`, 5 ở `test_03_runner.py`, 2 ở `test_04_curator.py`; nguyên nhân là các hàm TODO trong `src/lab/agent.py`, `subagents.py`, `runner.py`, `curator.py` ném `NotImplementedError`. Chưa đạt yêu cầu toàn bộ repo xanh; không bỏ qua hoặc sửa assertion để che lỗi. Chưa đo coverage nên chưa khẳng định đạt >80%.

Debug scripts: `scripts/debug_agent.py`, `scripts/debug_system.py`; profiling: `scripts/profile_system.py`. Communication được ghi JSONL, log riêng từng component. Chi tiết các lần debug/profiling ở `report/INTEGRATION.md`.

## 6. Performance Analysis

### Benchmark Results

Chạy `.venv\Scripts\python.exe scripts/benchmark.py`, gọi mô hình thật theo `.env`, 3 loại yêu cầu × 3 lần, tuần tự. CSV mẫu có doanh thu 100 + 150 + 250 = 500. Kết quả cuối ở `benchmark_results.json`; metrics và logs ở `results/benchmark/5781f06a-3f79-4f4c-a7e6-ee1093bdbea9/`.

| Test Case | Min | Max | Avg | Median | Thành công |
|---|---|---|---|---|---|
| Simple data query | 2,058s | 2,648s | 2,275s | 2,119s | 3/3 |
| Code generation | 7,369s | 9,316s | 8,419s | 8,571s | 3/3 |
| Complex workflow | 5,862s | 10,381s | 7,643s | 6,688s | 3/3 |

### Performance Metrics

| Metric | Đo được | Target | Đánh giá trong mẫu |
|---|---|---|---|
| Latency P50 | 6,688s | <5s | Chưa đạt |
| Latency P99 (nội suy) | 10,295s | <15s | Đạt |
| Successful throughput | 9,816 req/min | >10 req/min | Chưa đạt |
| Error rate | 0% (9/9) | <1% | Không lỗi trong mẫu |
| Token usage | 17.021 (15.003 input + 2.018 output) | Theo dõi | Usage metadata API |
| Token/100 requests dự phóng | 189.122 | ≤150.000 | Chưa đạt |
| Worker utilization | Chưa đo trong benchmark này | 70–90% | Chưa kết luận |

P50/P99 gộp 9 latencies. Throughput tính theo thời gian thực chạy cả suite tuần tự. Chín mẫu không đủ xác nhận P99/error rate dài hạn; token/100 chỉ là dự phóng, chưa chạy 100 requests. Profiling trước đó với workload tạo báo cáo khác đạt P50 4,127s, 13,154 req/min và dự phóng 117.580 token/100, nhưng không thay thế kết quả suite có tạo biểu đồ này. Utilization đo ở profile đó là Data 32,38%, Code 38,29%, Evaluator 0,022%; chưa đạt 70–90%, cần workload đồng thời đại diện và định nghĩa capacity rõ ràng.

### Findings

1. Lần benchmark đầu đạt 6/9, workflow phức hợp thất bại kiểm tra PNG dù pipeline báo success. Log cho thấy Code Agent gọi `create_file` sau `python_repl`, ghi đè biểu đồ bằng nội dung rỗng. Đã sửa prompt yêu cầu đọc CSV, lưu PNG bằng matplotlib và kết thúc sau `savefig`. Lần chạy lại đủ 9 yêu cầu đạt 9/9. Bằng chứng lần đầu: `results/benchmark/fad603a5-7c47-44fe-b238-51a6d32fc86a/` (33,33% lỗi, 16.093 tokens).
2. Code generation chậm nhất, trung bình 8,419s, gồm tạo script và thực thi kiểm tra với nhiều lượt model/tool. Lần đầu của workflow biểu đồ mất 10,381s, các lần sau 6,688s và 5,862s, phù hợp chi phí khởi động/import và biến động API; chưa tách timing để quy toàn bộ chênh lệch cho REPL.
3. Validator kiểm tra sum=500, script tồn tại và parse được bằng AST, PNG có chữ ký hợp lệ và có evaluation. Chưa chấm nội dung biểu đồ hoặc tính đúng của mọi script; evaluator mặc định chỉ kiểm tra sự hiện diện kết quả, không đủ thay cho validation artifact.
4. Hướng tối ưu tiếp theo: giảm lượt LLM không cần thiết sau tool thành công, cache quyết định routing cho yêu cầu tương đương, đo warm/cold riêng và workload đồng thời. Giữ timeout, kiểm tra output và log lỗi; không tăng utilization bằng tác vụ thừa.

## 7. Kết quả so sánh (Phần 4.3, 4.4)

> Dán nội dung `report/table.md` và kết quả `python scripts/check_breakdown.py`. Nêu các lần chạy có `error` hoặc `skills_modified = true` (nếu có) và cách xử lý.

```text
(dán bảng ở đây)
```

## 8. Phân tích

> Trả lời từng câu bằng số liệu từ mục 7 và bằng chứng từ vết. Kết quả âm hoặc không có khác biệt vẫn hợp lệ nếu được phân tích tốt.

1. So với `baseline`, điều kiện nào cải thiện điểm tác vụ **học**? Điều kiện nào cải thiện điểm tác vụ **đánh giá**? Có điều kiện nào cải thiện tác vụ học nhưng không cải thiện tác vụ đánh giá? Nếu có, đó là dấu hiệu gì?
2. Tách điểm thành check kỹ thuật và check quy ước (`rule_`). Skill do curator sinh giúp nhóm check nào? Check quy ước **mới** của tác vụ đánh giá có được skill giúp không, và vì sao?
3. Dựa vào vết và `skills_read`, giải thích một check mà skill giúp đạt và một check mà skill không giúp (skill chưa được đọc, đọc nhưng không làm theo, skill thiếu hoặc sai).
4. Chi phí: so sánh số token trung bình giữa các điều kiện. Điều kiện nào có hiệu quả tốt nhất theo điểm trên mỗi token? Đa tác tử có đáng chi phí trong thí nghiệm này không?
5. Có dấu hiệu rò rỉ dữ liệu hoặc quá khớp nào trong skill sinh ra không? Nhóm đã phòng tránh như thế nào?
6. Nhiễu: so sánh điểm tác vụ học của cùng bộ skill ở Phần 3.4 (đã sao lưu) và sau đóng băng. Chênh lệch bao nhiêu? Nó cho biết điều gì về độ tin cậy của các chênh lệch trong bảng ở mục 7?

## 9. Hạn chế và tính hợp lệ

> Nêu ít nhất 3 hạn chế và ảnh hưởng của từng hạn chế đến kết luận (ví dụ: chỉ 3 tác vụ mỗi vai trò, mỗi cấu hình chạy một lần, nhiễu của mô hình, tác vụ do giảng viên thiết kế sẵn quy ước, chỉ một mô hình).

1.
2.
3.

## 10. Kết luận

> Tối đa 5 câu. Chỉ khẳng định điều số liệu hỗ trợ. Nêu một đề xuất cải tiến tiếp theo.

## Phụ lục

- Lệnh đã chạy (theo thứ tự):
- Thử thách mở rộng (nếu có): hướng chọn, kết quả, nhận xét.
- Ghi chú khác:
