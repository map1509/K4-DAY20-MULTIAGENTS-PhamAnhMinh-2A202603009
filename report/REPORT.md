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

X?c nh?n sau s?a ng?y 06/10/2026 tr?n Windows, Python 3.11.9: **69/69 passed**, kh?ng skip test.

| Nh?m | K?t qu? |
|---|---|
| Coordinator | 14/14 |
| Workers | 4/4 |
| Tools | 4/4 |
| Integration/E2E/performance v? regression | 8/8 |
| BaseWorker | 7/7 |
| Test repo g?c: provided/agent/runner/curator | 32/32 |
| T?ng | 69/69 |

?? c?i c?c TODO make_backend, build_agent, get_subagents, run_task v? curate_skills theo pseudo-code c?a repo. Backend Windows d?ng Git Bash c? s?n, m?i tr??ng ???c l?c v? Python t? venv; file tools v? shell d?ng chung sandbox root. Runner d?ng th? m?c t?m ngo?i repo, ghi trace/usage/?i?m, ph?t hi?n s?a skills v? d?n sandbox. Curator ch? ??c learning failures, lo?i skill kh?ng h?p l? ho?c ch?a evaluation markers. Kh?ng s?a h?ng prompt ho?c c?c module PROVIDED.

Regression ki?m tra t?o v? th?c thi script v?i m?t l??t model, ph?n lo?i nhanh v?n gi? tham s? cho workers offline, che secret trong JSON l?ng nhau v? thay handler khi c?u h?nh log l?i. Debug scripts: scripts/debug_agent.py, scripts/debug_system.py. L?nh x?c nh?n:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -o addopts='-p no:cacheprovider' -q --tb=short --cov=src --cov-report=term-missing --cov-report=json:results/coverage.json
```

Coverage statement to?n b? src: **81.18%**, 1234/1520 statements (m?c ti?u >80%: ??t). Kh?ng lo?i module kh?i s? ?o; ti?n tr?nh REPL con hi?n ch?a ???c instrument, n?n _repl_worker.py v?n 0% trong b?o c?o n?y. ??y l? coverage d?ng, kh?ng ph?i b?ng ch?ng ki?m tra h?t m?i nh?nh. Th?i gian suite c? coverage: 54,66 gi?y.

## 6. Performance Analysis

### Benchmark Results

Suite gi? 3 lo?i t?c v? ? 3 l?n tu?n t?, m? h?nh th?t t? .env, c?ng d? li?u doanh thu 100 + 150 + 250 = 500. Kh?ng ??a API key v?o b?o c?o. K?t qu?: benchmark_results.json; metrics/logs/artifacts: results/benchmark/ba372709-4f7d-483e-8ef2-140ec36541ef/.

| Test Case | Min | Max | Avg | Median | Th?nh c?ng |
|---|---|---|---|---|---|
| Simple data query | 0.901s | 2.061s | 1.327s | 1.019s | 3/3 |
| Code generation | 5.875s | 6.483s | 6.095s | 5.928s | 3/3 |
| Complex workflow | 3.129s | 6.794s | 4.450s | 3.429s | 3/3 |

### Performance Metrics

| Metric | Tr??c t?i ?u | Sau t?i ?u | Target | K?t qu? trong m?u |
|---|---|---|---|---|
| P50 | 6,688s | 3.429s | <5s | ??t |
| P99 n?i suy | 10,295s | 6.769s | <15s | ??t |
| Successful throughput | 9,816/ph?t | 15.159/ph?t | >10/ph?t | ??t |
| Error rate | 0% (9/9) | 0% (9/9) | <1% | Kh?ng l?i trong m?u |
| Token usage | 17.021 | 4,147 | Theo d?i | Gi?m kho?ng 75,6% |
| Token/100 requests d? ph?ng | 189.122 | 46,078 | ?150.000 | ??t d? ph?ng |

Usage sau s?a: 3156 input + 991 output. P50/P99 g?p 9 m?u, g?m cold start; throughput d?ng th?i gian th?c suite. Ch?a ch?y 100 y?u c?u, kh?ng kh?ng ??nh P99/error rate d?i h?n. Validator ki?m tra sum=500, script t?n t?i v? parse ???c, ?nh c? ch? k? PNG v? c? evaluation; ch?a ch?m ??y ?? n?i dung h?nh ho?c m?i t?nh ch?t script.

### ?o t?i ??ng th?i v? utilization

?? b? sung --concurrency v?o profile_system.py. Utilization l? ph?n th?i gian c? ?t nh?t m?t l?i g?i worker ?ang ho?t ??ng (h?p c?c kho?ng th?i gian), tr?nh c?ng ch?ng l?m t? l? v??t 100%; g?m ch? I/O/model, kh?ng ph?i CPU usage ho?c capacity utilization.

```powershell
.venv\Scripts\python.exe scripts/profile_system.py --live --requests 10 --concurrency 3
```

Workload t?o b?o c?o, kh?c workload benchmark bi?u ??: **10/10 success**, P50 2.550s, P99 2.917s, throughput 58.968/ph?t, 6561 tokens/10 requests, d? ph?ng 65,610/100. Artifacts: results/profiling/d0bfca29-926b-4f8d-b991-4b4dc80549d0/.

| Worker | Utilization |
|---|---|
| data_agent | 47.031% |
| code_agent | 62.345% |
| evaluator_agent | 0.102% |

**M?c ti?u 70?90% cho m?i worker v?n ch?a ??t.** Evaluator l?m ki?m tra deterministic r?t ng?n; Data ch?y nhanh h?n Code v? Code ch? d? li?u upstream. T?ng concurrency ri?ng kh?ng c?n b?ng th?i l??ng c?c giai ?o?n. Sau t?i ?u, throughput t?t h?n nh?ng utilization c? th? gi?m v? b?t c?ng vi?c th?a. Kh?ng th?m sleep, g?i LLM kh?ng c?n thi?t hay s?a c?ng th?c ?? l?m ??p s?. Mu?n ?p d?ng m?c ti?u n?y c?n ??nh ngh?a n?ng l?c ph?c v? t?ng worker v? workload ??i di?n cho t?ng chuy?n m?n; kh?ng th? ??m b?o b?ng m?t c?u h?nh t?i chung c?a pipeline hi?n t?i.

### Findings v? thay ??i

1. Gi?m l??t LLM: coordinator ph?n lo?i b?ng quy t?c ch? cho y?u c?u t??ng minh v? workers c? model; tr??ng h?p m? h?/offline v?n l?y k? ho?ch model. Kh?ng b? validation input.
2. Ch? c?p tools ph? h?p task: CSV t??ng minh d?ng analyze_csv, y?u c?u script d?ng write_and_run_script, chart d?ng python_repl, b?o c?o v?n b?n d?ng create_file. Gi?m k?ch th??c schema/prompt.
3. G?p t?o v? ch?y script trong m?t tool, tr? stdout v? ???ng d?n th?t. Worker k?t th?c sau tool th?nh c?ng; v?i chart ch? k?t th?c khi PNG y?u c?u th?c s? t?n t?i v? c? ch? k? h?p l?.
4. S?a 16 l?i TODO c?a repo g?c v? regression c?a worker offline; to?n b? test xanh. C?c m?c hi?u su?t ??t trong m?u cu?i, utilization v?n l? gi?i h?n ???c ghi r?.
5. L?n l?i ban ??u 6/9 ???c gi? ? results/benchmark/fad603a5-7c47-44fe-b238-51a6d32fc86a/: Code Agent ghi ?? PNG b?ng file v?n b?n r?ng. ?? s?a prompt v? ch?n tool kh?ng ph? h?p cho y?u c?u chart. L?n tr??c t?i ?u 9/9 c? P50 6,688s ? results/benchmark/5781f06a-3f79-4f4c-a7e6-ee1093bdbea9/. C?c l?n th? trung gian v?n gi? local, kh?ng lo?i m?u l?i kh?i th?ng k? c?a t?ng l?n ch?y.

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
