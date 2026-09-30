# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của các event `response_sent`; SLO yêu cầu request thành công không quá 3000 ms.
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: phần lớn request chậm vẫn có thể thành công, nhưng nhóm người dùng ở tail phải chờ quá ngưỡng SLO.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Latency, xác nhận P95/P99, TTFT và khoảng thời gian vượt ngưỡng.
  2. Logs: lọc `response_sent` trong khoảng đó, chọn một record có `latency_ms > 3000` và lấy `correlation_id`.
  3. Traces: mở trace cùng `correlation_id`, so sánh thời gian của `retrieval` và `generation` để khoanh vùng span chậm.
- Mitigation tạm thời: tắt incident practice nếu còn bật; nếu generation/prompt gây chậm thì rollback label `production`, còn retrieval chậm thì chuyển sang context dự phòng hoặc giảm tải truy vấn.
- Owner: `student-2A202602807`

## Alert 2

- Tên: `HighRequestErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ `request_failed / request_received`; guardrail tối đa 2%.
- Điều kiện và thời gian duy trì: error rate lớn hơn 2% liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: request trả lỗi thay vì câu trả lời, trực tiếp tiêu thụ error budget.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Errors, xác nhận error rate và nhóm `error_type` tăng trong cửa sổ cảnh báo.
  2. Logs: lọc `request_failed`, chọn error type phổ biến và lấy một `correlation_id` đại diện.
  3. Traces: mở trace cùng `correlation_id`, tìm span có trạng thái lỗi và đọc metadata đã scrub để xác nhận bước thất bại.
- Mitigation tạm thời: tắt scenario lỗi, rollback thay đổi gần nhất; nếu retrieval không khả dụng thì bật fallback an toàn và giảm concurrency trong khi khôi phục dependency.
- Owner: `student-2A202602807`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ thành công trên mọi event có field `tool_success`; guardrail tối thiểu 90%.
- Điều kiện và thời gian duy trì: retrieval success dưới 90% liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời có thể thiếu context, giảm chất lượng hoặc request thất bại hoàn toàn.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Errors, xác nhận retrieval success giảm và đối chiếu error rate/quality cùng khoảng thời gian.
  2. Logs: lọc mọi record có `tool_success=false`, lấy `correlation_id`, `error_type` và thời điểm đại diện.
  3. Traces: mở trace cùng `correlation_id`, kiểm tra trạng thái và duration của span `retrieval`, rồi so sánh với `generation`.
- Mitigation tạm thời: tắt incident, dùng tài liệu fallback đã kiểm soát hoặc tạm từ chối câu hỏi cần RAG thay vì sinh câu trả lời không có căn cứ.
- Owner: `student-2A202602807`
