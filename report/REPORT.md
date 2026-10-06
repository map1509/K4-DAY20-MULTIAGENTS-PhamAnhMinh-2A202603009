# Báo cáo Lab: Self evolving Agentic

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Phạm Anh Minh | 2A202603009 | Cài harness Deep Agents, coordinator/workers/tools, tests, benchmark và báo cáo |

- Nhà cung cấp và mô hình (`LAB_MODEL`, không ghi khóa API), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`: mô hình gpt-4o-mini qua cấu hình endpoint trong .env; temperature 0; runner mặc định recursion_limit=60. Tests có thể dùng model giả và giới hạn riêng.
- Phiên bản Deep Agents (`pip show deepagents`), hệ điều hành, chạy trực tiếp hay trong Docker: Deep Agents 0.7.21; Windows; Python 3.11.9 trong .venv; chạy trực tiếp.
- Số lần chạy tác vụ đã dùng / ngân sách: chưa có run chính thức được lưu cho ba điều kiện baseline/subagents/skills-auto; chưa tổng hợp ngân sách toàn phiên. Benchmark hệ thống multi-agent riêng có 9 requests/lần; không coi đây là các tác vụ Deep Agents của template.
- Commit của tag `freeze`: chưa có tag freeze. Không tạo tag hồi tố để coi giả thuyết là đã đăng ký trước.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

Các giả thuyết dưới đây chưa được kiểm chứng bằng thí nghiệm ba điều kiện. Chưa có freeze nên chưa đáp ứng bước đóng băng/đánh giá trong GUIDE; không suy luận kết quả từ unit tests. Căn cứ thiết kế: guides/pseudocode/01_agent.md, 02_subagents.md và 04_curator.md.

- H1 (subagents so với baseline): subagents có thể cải thiện kiểm tra kỹ thuật ở tác vụ nhiều bước nhờ chia việc khảo sát, thực hiện và review; dự kiến tăng token và thời gian do giao tiếp/kiểm tra kết quả.
- H2 (skills-auto so với baseline): skills-auto có thể giảm lỗi lặp lại khi skill mô tả quy trình tổng quát từ learning feedback; hiệu quả phụ thuộc skill được đọc và áp dụng, không chỉ được tạo.
- H3 (tác vụ học so với tác vụ đánh giá): cải thiện có thể lớn hơn trên learning tasks; chênh lệch nhỏ trên evaluation tasks sẽ cho thấy khả năng chuyển giao hạn chế hoặc skill quá riêng cho dữ liệu học.

## 3. Làm quen Deep Agents (Phần 0.3)

1. Đã đọc README.md, GUIDE.md và pseudo-code; repo không có LAB_GUIDE.md. Tour ngoại tuyến xác nhận 9 tools mặc định: ls, read_file, write_file, edit_file, delete, glob, grep, execute, task. File tools và shell dùng đường dẫn tương đối workspace/...; execute chạy từ sandbox root.
2. Subagent mặc định general-purpose nhận prompt giao việc và trả báo cáo cuối; không tự nhận toàn bộ lịch sử của agent chính. Harness đã thêm explorer để khảo sát, implementer để sửa/chạy checks và reviewer để kiểm tra; mỗi prompt được nối PATHS_NOTE.
3. Tour xác nhận system prompt mặc định rỗng, nhưng tool descriptions vẫn hướng dẫn hành vi. Harness dùng BASE_PROMPT được cung cấp, thêm SUBAGENTS_NOTE khi bật subagents, thêm SKILLS_NOTE và skills=["/skills/"] khi bật skills. Backend Windows dùng Git Bash với environment được lọc, không chuyển API keys vào shell.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| Chưa chạy baseline learning chính thức | Chưa có dữ liệu | Chưa phân loại | Không có results/baseline/<task>/run.json và trace.md |

Chưa xác định nhóm lỗi chiếm đa số hoặc kiểm chứng skill phòng ngừa nhóm đó. Lỗi routing/SQL-for-CSV/PNG overwrite của hệ thống multi-agent riêng được ghi ở MULTIAGENTS.md và INTEGRATION.md; không gán chúng thành failed checks của các learning tasks trong template.

## 5. Điều kiện `subagents` (Phần 2.3)

- Các subagent đã định nghĩa (tên, vai trò, lý do thiết kế): explorer đọc và báo cáo constraints; implementer triển khai và chạy checks; reviewer kiểm tra độc lập. Định nghĩa tại src/lab/subagents.py; vai trò tách biệt giúp prompt giao việc rõ ràng.
- `subagent_calls` ở từng tác vụ và nhận xét (kể cả trường hợp bằng 0): chưa có số liệu chính thức theo task. Unit test xác nhận runner đếm tool calls tên task; không thay thế run thật.
- Thông tin thiếu hoặc thừa khi giao việc (nếu có giao việc): chưa phân tích trace thật. SUBAGENTS_NOTE yêu cầu gửi đủ rules và paths; PATHS_NOTE được thêm cho mỗi subagent để thống nhất đường dẫn.
- Ảnh hưởng đến token và thời gian: chưa đo baseline vs subagents. Runner cộng usage metadata cho cả subagents, trong khi trace/tool-call counts chỉ gồm luồng chính.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator, số skill bị xóa và lý do: chưa chạy curator bằng LLM trên learning results chính thức; chưa có bộ skills/auto để đóng băng. Curator đã được unit test với model giả: chỉ đọc learning failures, bỏ skill sai tên/path traversal và skill chứa evaluation markers.

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| Chưa có skill sinh từ learning runs chính thức | Chưa đánh giá | Chưa đánh giá | Chưa có measurements |

Skill synthetic trong tests không được đưa vào bảng như một skill chính thức. Chưa đo việc đọc skill hoặc khả năng chuyển giao sang evaluation tasks.

## 7. Kết quả so sánh (Phần 4.3, 4.4)

Chạy lab.compare trên dữ liệu hiện có không có cột điều kiện hoặc hàng tác vụ vì chưa có run.json chính thức. Nội dung report/table.md do công cụ sinh:

```text
| Task |  |
|---|
| **Mean score - learning tasks** |  |
| **Mean score - evaluation tasks** |  |
| **Mean tokens per run** |  |
| **Runs that read a skill** |  |
```

Kết quả scripts/check_breakdown.py:

```text
condition     role    technical  house rules  mean tokens  read a skill
(evaluation rows are hidden until the git tag `freeze` exists)
```

Không có run chính thức để thống kê error hoặc skills_modified=true; điều này không có nghĩa đã chạy và không lỗi. Chưa chạy evaluation vì chưa có tag freeze. Kết quả benchmark của Coordinator/Data/Code/Evaluator không được dùng thay bảng so sánh này.

## 8. Phân tích

1. **Baseline vs subagents/skills-auto trên learning/evaluation:** chưa có dữ liệu mục 7 nên chưa kết luận điều kiện nào cải thiện; chưa đánh giá dấu hiệu chỉ tốt trên learning.
2. **Checks kỹ thuật và rule_:** chưa có breakdown theo điều kiện; chưa xác định skill hỗ trợ nhóm nào hoặc rule mới trên evaluation. Công cụ check_breakdown.py phân nhóm bằng prefix rule_.
3. **Skill giúp/không giúp:** chưa có trace và skills_read từ runs chính thức để chọn ví dụ. Cần kiểm tra read_file của SKILL.md rồi đối chiếu hành động và failed checks.
4. **Chi phí:** chưa có token trung bình/điểm theo ba điều kiện nên chưa tính hiệu quả điểm/token hoặc kết luận lợi ích đa tác tử. Benchmark riêng dùng 4.147 tokens/9 requests, không phải phép so sánh baseline/subagents/skills-auto.
5. **Rò rỉ/quá khớp:** curator lọc role=learn và validate_skill chặn evaluation markers; tests kiểm tra các guardrails này. Chưa có bộ skill sinh thật để đánh giá nội dung hoặc overfitting.
6. **Nhiễu trước/sau freeze:** chưa có snapshot skills, tag freeze hoặc paired runs nên chưa tính chênh lệch. Cần cùng bộ skill, cấu hình và tác vụ rồi lưu hai lần chạy để đối chiếu.

## 9. Hạn chế và tính hợp lệ

1. Thí nghiệm đúng protocol của template chưa được chạy; unit tests pass không chứng minh giả thuyết hoặc điểm evaluation.
2. Không có freeze và bảng so sánh ba điều kiện; không thể kết luận chuyển giao, overfitting hoặc hiệu quả điểm/token.
3. Benchmark multi-agent riêng chỉ có 9 mẫu/lần và profile 10 requests, không đủ xác nhận P99/error rate dài hạn. Utilization 70–90% cho mỗi worker vẫn chưa đạt trong workload đã đo.
4. REPL/LocalShellBackend không phải isolation OS cho code đối kháng. Coverage không instrument REPL subprocess; statement coverage không thay kiểm tra mọi nhánh.
5. Evaluator của hệ thống riêng mặc định kiểm tra output presence; validator benchmark chưa chấm toàn bộ nội dung artifacts.

## 10. Kết luận

Đã cài harness và hệ thống multi-agent riêng, kiểm chứng 74/74 tests cùng statement coverage 82,40%. Báo cáo này tuân theo template gốc và ghi rõ dữ liệu thí nghiệm còn thiếu. Chưa thể kết luận baseline, subagents hay skills-auto tốt hơn khi chưa có các runs đúng protocol. Bước tiếp theo là chạy learning tasks, sinh/kiểm tra skills, đăng ký giả thuyết trước freeze rồi mới chạy evaluation và so sánh.

## Phụ lục

- Lệnh đã chạy (theo thứ tự của lần rà soát template): git tag --list; kiểm tra files results/skills; python -m lab.compare; python scripts/check_breakdown.py. Các lần kiểm chứng trước gồm pytest tests/, standalone coordinator, communication và tool integration; chi tiết ở MULTIAGENTS.md.
- Thử thách mở rộng (nếu có): bonus 6c Result Caching cho hệ thống Coordinator riêng; TTL/LRU, SHA-256 invalidation, không cache writes/errors. Benchmark local 20 requests đạt 19 hit/1 miss, task messages giảm 20→1, thời gian trung bình giảm 15,479ms→1,634ms; không suy ra LLM throughput hoặc token savings từ số này.
- Ghi chú khác: báo cáo multi-agent đủ 10 mục theo yêu cầu đã gửi trước đây được giữ nguyên tại report/MULTIAGENTS.md, gồm architecture, protocol, tests, live benchmark và checklist. report/REPORT.md hiện theo đúng REPORT_TEMPLATE.md. Không ghi API key, không tạo số liệu hoặc freeze hồi tố. Submit vẫn do sinh viên tự thực hiện.
