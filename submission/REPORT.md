# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Hữu Thành
- **MSSV:** 2A202602807
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/hthanh1412004/K4-L3B-DAY13-NguyenHuuThanh-2A202602807-Monitoring-LLMOps.git
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602807`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline  | Kết quả cuối | Nhận xét |
| ----------------------- | --------- | ------------ | -------- |
| `validate_logs.py`      | 30/100    | 100/100      | Đạt CP1: schema, correlation, enrichment và PII đều pass |
| `validate_dashboard.py` | 6/6       | 6/6          | Contract đủ 6 panel; dashboard local `scripts/dashboard.py` render đủ 6 panel có dữ liệu |
| `pytest`                | 22 passed | 25 passed    | Bổ sung test CCCD, thẻ thanh toán và test trace prompt |
| Số traces hợp lệ        |           | 63           | 63/85 trace có đủ cây root → retrieval + generation (22 trace đầu được tạo trước khi thêm child observation); các trace sau khi tạo prompt liên kết `day13-chat` từ Langfuse |
| Số PII leak             | 0         | 0            | `validate_logs.py` 100/100 trên 81 log records của cửa sổ dashboard |
| Latency P95 / TTFT P95  | 2165 ms / 50 ms | 153 ms / 50 ms | 40 request; P50 151 ms, P99 1354 ms (request đầu sau khi khởi động API); dưới SLO 3000 ms |
| Retrieval success rate  |           | 100%         | 40/40 event có `tool_success=true`; error rate 0% |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ ở đầu mỗi request, ưu tiên nhận header `x-request-id`; nếu không có thì sinh ID dạng `req-<8 ký tự hex>`. ID được bind vào structlog context, lưu trong `request.state`, trả trong response body và header `x-request-id`. Header `x-response-time-ms` ghi thời gian xử lý request.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model` và `env`; user ID chỉ được lưu dưới dạng SHA-256 rút gọn 12 ký tự.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` chạy trước `JsonlFileProcessor` và `JSONRenderer`, thay email, số điện thoại Việt Nam, CCCD và thẻ thanh toán bằng marker `[REDACTED_*]`.
- **Cách kiểm chứng kết quả:** Chạy load test và request PII mẫu, sau đó chạy `python scripts/validate_logs.py`. Kết quả trên 25 records: không thiếu schema/context, có 12 correlation ID duy nhất, 0 PII leak và đạt 100/100. Request dùng `x-request-id: req-cafebabe` nhận lại đúng ID cùng `x-response-time-ms` trong response header; pytest đạt 24 passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** API dùng key của project `day13-k4-l3b-2A202602807` (region US); request gửi với `x-request-id` do tôi đặt (`req-a0000000`, `req-b0000000`, `req-c0000000`…) và tìm lại đúng ID đó trong metadata `correlation_id` của trace qua Observations API v2.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` → `lab-agent-run` (agent) → `retrieval` (retriever) + `generation` (generation). Generation có model `claude-sonnet-4-5`, usage input/output/total, cost và liên kết prompt `day13-chat`; input/output thô không được capture (giá trị `None`).
- **Cách nối trace với log:** `correlation_id` trong log (`data/logs.jsonl`) được đưa vào metadata của trace qua `propagate_attributes`; lọc log theo `correlation_id` rồi tìm trace có cùng metadata.
- **Prompt name:** `day13-chat` (loại text, biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** v1 — labels `baseline`, `production`; template gốc. Request với `LANGFUSE_PROMPT_LABEL=baseline` có `tokens_in=27`.
- **Version/label candidate:** v2 — labels `candidate`, `latest`; thêm dòng "Answer concisely using only the provided context.". Request với `LANGFUSE_PROMPT_LABEL=candidate` có `tokens_in=40`.
- **Trace ID của mỗi version:** v1 (baseline): `571242beca455b2696b37c0a5efe5226` (`req-a0000000`); v2 (candidate): `3bf56d551155a9bf1375a009005276a2` (`req-b0000000`); v2 sau promote (production): `f756a1f280b911130d19f348e04bc4f8` (`req-c0000000`); v1 sau rollback (production): `9adc9beb5a8b23eba4ae4087beb76ecf` (`req-d0000000`, `tokens_in=27`).
- **Cách promote và rollback `production`:** Promote: dời label `production` sang v2 (v1 chỉ còn `baseline`), restart API, gửi request và thấy `prompt_label=production`, `prompt_version=2`. Rollback: dời `production` về v1, restart API, gửi request và kiểm tra `prompt_version=1`. App không cần sửa code vì chỉ lấy prompt theo label.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard local `scripts/dashboard.py` (http://127.0.0.1:8501) đọc `data/logs.jsonl` theo `config/dashboard.yaml`, time range 60 phút, auto-refresh 30 giây, mỗi panel có đơn vị và đường threshold (`evidence/11-dashboard-overview.png`). Kết quả trên 40 request: Latency P50/P95/P99 = 151/153/1354 ms, TTFT P95 50 ms (threshold P95 ≤ 3000 ms); Traffic 40 request, đỉnh khoảng 10 request/phút (threshold ≥ 1/phút); Errors 0% và retrieval success 100% (threshold error ≤ 2%, retrieval ≥ 90%); Cost $0.0829 (threshold ≤ $2.5); Tokens 1,352 input + 5,257 output = 6,609 (threshold ≤ 50,000); Quality trung bình 0.88 (threshold ≥ 0.75).
- **SLO và lý do chọn:** `fast_successful_requests`: 99.5% request phải trả `response_sent` với `latency_ms ≤ 3000` trong cửa sổ 28 ngày. Baseline CP1 có P95 khoảng 2165 ms và TTFT P95 50 ms; lần đo cho dashboard CP2 có P95 153 ms, nên ngưỡng 3000 ms chừa khoảng đệm cho request đầu khi khởi động nhưng vẫn bắt được incident `rag_slow` (retrieval chậm thêm 2.5 s). Guardrail phụ: error rate ≤ 2%, cost ≤ $2.5/ngày, quality ≥ 0.75, retrieval success ≥ 90%.
- **Cách tính error budget:** Error budget = 100% − 99.5% = 0.5%. Với 10,000 request trong 28 ngày thì được phép tối đa 10,000 × 0.005 = 50 request lỗi hoặc chậm hơn 3000 ms. Trong cửa sổ dashboard hiện tại (40 request) chưa tiêu tốn budget: 0 lỗi, 0 request vượt 3000 ms.
- **Ba alert và runbook tương ứng:** (1) `HighLatencyP95` — warning khi P95 `latency_ms` > 3000 ms trong 5 phút → `docs/alerts.md#alert-1`; (2) `HighRequestErrorRate` — critical khi `request_failed / request_received` > 2% trong 5 phút → `docs/alerts.md#alert-2`; (3) `LowRetrievalSuccessRate` — warning khi tỉ lệ `tool_success == true` < 90% trong 5 phút → `docs/alerts.md#alert-3`. Cả ba là alert symptom-based, owner `student-2A202602807`, channel `#k4-l3b-alerts`; runbook đi theo thứ tự Metrics → Logs → Traces rồi mitigation.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-30 05:44:56–05:46:08 UTC. Baseline 05:44:56–05:44:57 (10 request), incident 05:45:06–05:45:20 (5 request feature `monitoring`, concurrency 5), hồi phục từ 05:46:07 (10 request).
- **Triệu chứng từ metrics:** Panel Latency: `latency_ms` P50 tăng từ 152 ms (baseline) lên 2653 ms, 5/5 request vượt `latency_threshold_ms` 2000 của challenge. TTFT P95 giữ nguyên 50 ms; panel Errors 0% và retrieval success 5/5; tokens, cost, quality không đổi (tokens_out TB 126 → 128, quality 0.88 → 0.84). Vì vậy độ trễ nằm ngoài bước sinh token của LLM. (Thời gian phía client 8–13 s do request xếp hàng khi `--concurrency 5`, không dùng để đo.)
- **Log line và correlation ID liên quan:** `{"event": "response_sent", "correlation_id": "req-3fd90fa8", "feature": "monitoring", "latency_ms": 2653, "ttft_ms": 50, "tool_name": "retrieval", "tool_success": true, "ts": "2026-09-30T05:45:09.570392Z"}`; `request_received` cùng ID lúc 05:45:06.914Z. Log control cho thấy `incident_enabled` lúc 05:45:06.49Z, ngay trước request đầu tiên chậm.
- **Trace ID và span gây ảnh hưởng:** Trace `cf95dbef7cc8b5dcf2fc71b45a9ae7c1` (metadata `correlation_id=req-3fd90fa8`): `lab-agent-run` 2656 ms = `retrieval` **2504 ms** + `generation` 152 ms; không span nào lỗi. So với trace baseline `cd4b1f2eedd1aa2df80b489c5ff81577` (`req-2817f540`): `retrieval` 0 ms, `generation` 152 ms, tổng 152 ms. Span gây ảnh hưởng là `retrieval` (~94% thời gian request).
- **Root cause:** Bước retrieval (RAG/vector store) bị chậm khoảng 2.5 s mỗi request — sự cố `rag_slow` được bật lúc 05:45:06. Ba bằng chứng cùng chỉ về một chỗ: metric latency tăng nhưng TTFT/token/error không đổi → log `req-3fd90fa8` có `latency_ms=2653`, `ttft_ms=50`, `tool_name=retrieval` → trace cùng ID có span `retrieval` 2504 ms trong khi `generation` giữ 152 ms.
- **Fix action:** Tắt sự cố retrieval chậm (`python scripts/inject_incident.py --scenario rag_slow --disable`), xác nhận `/health` mọi incident `false`, chạy lại load test: 10/10 request về 155–180 ms, `retrieval` trở lại ~0 ms. Trong hệ thống thật tương ứng với khôi phục/scale vector store hoặc chuyển sang index dự phòng.
- **Preventive measure:** (1) Alert `HighLatencyP95` (P95 > 3000 ms trong 5 phút, runbook `docs/alerts.md#alert-1`) và nên thêm ngưỡng thấp hơn cho feature `monitoring` theo challenge (2000 ms); (2) ghi `retrieval_latency_ms` riêng vào log và thêm panel/alert cho latency retrieval để phân biệt với latency LLM mà không cần mở trace; (3) đặt timeout cho retriever (ví dụ 1 s) kèm fallback context an toàn để request không vượt SLO khi vector store chậm; (4) request đang được xử lý tuần tự nên một dependency chậm làm cả hàng đợi chậm theo — cân nhắc chạy agent trong threadpool/worker để cô lập.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng `correlation_id` (`x-request-id`) làm khoá chung cho cả log và trace: middleware bind ID vào structlog context, còn agent đưa cùng ID vào metadata trace qua `propagate_attributes`. Nhờ vậy khi điều tra CP3 tôi đi thẳng từ log `req-3fd90fa8` sang đúng trace `cf95dbef…` thay vì mở trace ngẫu nhiên. Tôi cũng chọn không capture input/output thô trên Langfuse (`capture_input=False`, `capture_output=False`) và chỉ ghi `message_preview` đã scrub, vì câu hỏi có thể chứa PII.
- **Một lỗi/blocker đã gặp:** Trong project Langfuse có 85 trace `lab-agent-run` nhưng chỉ 63 trace có span `retrieval`/`generation`, và nhiều trace sớm có `prompt_source=local-fallback`, `prompt_version=local-v1` thay vì version từ Langfuse.
- **Cách tìm nguyên nhân và xử lý:** Lọc theo tên observation trên Langfuse thì thấy 22 trace thiếu con đều được tạo trước khi tôi thêm `@observe` cho `retrieve` và `FakeLLM.generate`; các trace `local-fallback` được tạo trước khi prompt text `day13-chat` tồn tại, nên `get_prompt` trả fallback. Sau khi thêm decorator, tạo prompt v1/v2 và restart API, các trace mới đều đủ cây và có `prompt_source=langfuse`. Tôi chỉ tính 63 trace đủ cây là trace hợp lệ. Ngoài ra, API trace cũ (`/api/public/traces`) trả 410 với organization mới nên tôi chuyển sang Observations API v2 để tra trace theo `correlation_id`.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics trả lời "có vấn đề không, ở đâu, từ lúc nào" trên toàn bộ traffic (CP3: P50 latency 152 → 2653 ms trong khi TTFT, error, token không đổi). Logs thu hẹp xuống từng request cụ thể trong khoảng thời gian đó và cho `correlation_id` (`req-3fd90fa8`, `latency_ms=2653`, `ttft_ms=50`). Traces tách request đó thành từng bước để chỉ ra span gây chậm (`retrieval` 2504 ms, `generation` 152 ms). Mỗi tầng loại bớt giả thuyết cho tầng sau; bỏ qua metrics mà mở trace ngay thì dễ kết luận từ một request không đại diện.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version + label cho phép đổi hành vi mô hình mà không deploy code: tôi promote `production` sang v2 rồi rollback về v1 chỉ bằng cách dời label, và `prompt_version` trong trace cho biết chính xác request nào chạy version nào (v2 làm `tokens_in` tăng 27 → 40). Token/cost là tín hiệu riêng của LLM mà latency/error không bắt được (ví dụ output dài bất thường làm tăng chi phí). SLO 99.5% với ngưỡng 3000 ms biến "chậm" thành con số có error budget (50 request / 10,000), giúp quyết định khi nào cần alert và rollback thay vì phản ứng theo cảm tính.
- **Điều quan trọng nhất đã học:** Observability chỉ hữu ích khi các tín hiệu nối được với nhau. Một metric latency cao đơn lẻ không nói nguyên nhân; nhưng khi metric, log và trace cùng mang `correlation_id` và cùng chỉ về một span, root cause có bằng chứng thay vì phỏng đoán. Việc so sánh với baseline (retrieval 0 ms lúc bình thường) cũng quan trọng không kém việc thấy con số bất thường.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Dashboard là script local tự viết, chưa có alert tự động gửi Slack — `config/alert_rules.yaml` mới dừng ở định nghĩa rule và runbook. Log chưa có trường `retrieval_latency_ms` riêng nên panel latency chỉ phát hiện được "chậm" còn phải mở trace mới biết chậm ở retrieval. `/chat` gọi `agent.run()` đồng bộ trong handler async nên request bị xử lý tuần tự; tôi mới ghi nhận vấn đề này (thời gian phía client 8–13 s khi concurrency 5), chưa sửa. Cửa sổ challenge chỉ có 5 request nên P95 bằng chính giá trị lớn nhất.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
