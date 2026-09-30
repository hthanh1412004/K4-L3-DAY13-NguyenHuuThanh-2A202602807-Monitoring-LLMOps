# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Hữu Thành
- **MSSV:** 2A202602807
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/hthanh1412004/K4-L3-DAY13-NguyenHuuThanh-2A202602807-Monitoring-LLMOps.git
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602807`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

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

- **Dashboard và sáu panel:** Dashboard local `scripts/dashboard.py` (http://127.0.0.1:8501) đọc `data/logs.jsonl` theo `config/dashboard.yaml`, time range 60 phút, auto-refresh 30 giây, mỗi panel có đơn vị và đường threshold (`evidence/05-dashboard-incident.png`). Kết quả trên 40 request: Latency P50/P95/P99 = 151/153/1354 ms, TTFT P95 50 ms (threshold P95 ≤ 3000 ms); Traffic 40 request, đỉnh khoảng 10 request/phút (threshold ≥ 1/phút); Errors 0% và retrieval success 100% (threshold error ≤ 2%, retrieval ≥ 90%); Cost $0.0829 (threshold ≤ $2.5); Tokens 1,352 input + 5,257 output = 6,609 (threshold ≤ 50,000); Quality trung bình 0.88 (threshold ≥ 0.75).
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

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
