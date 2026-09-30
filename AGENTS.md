CP0 — Cài đặt môi trường và chạy baseline
Cần có: Python 3.11–3.13 (khuyên dùng 3.12; không dùng 3.14, vì cài requirements.txt sẽ treo hoặc lỗi khi build pydantic-core), Git, và tài khoản Langfuse Cloud của riêng bạn.

(Mọi lệnh trong lab đều chạy ở thư mục gốc repo, nơi có requirements.txt.)

4.1. Tạo môi trường Python
Cách A: dùng uv (nhanh, tự tải đúng Python 3.12, giống nhau trên mọi hệ điều hành)

# Windows PowerShell: cài uv (một lần)

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
Chép

# macOS / Linux: cài uv (một lần)

curl -LsSf https://astral.sh/uv/install.sh | sh
Chép
Mở terminal mới rồi chạy:

uv venv -p 3.12 .venv
uv pip install -r requirements.txt
Chép
Sau đó activate venv và tạo .env như dòng cuối của Cách B.

Cách B: dùng Python có sẵn trên máy (giống README.md, chỉ khác lệnh gọi Python)

Hệ điều hành Tạo venv Activate Tạo .env
Windows (PowerShell) py -3.12 -m venv .venv Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass rồi .\.venv\Scripts\Activate.ps1 Copy-Item .env.example .env
macOS brew install python@3.12 rồi python3.12 -m venv .venv source .venv/bin/activate cp .env.example .env
Ubuntu/Debian sudo apt install python3-venv rồi python3 -m venv .venv source .venv/bin/activate cp .env.example .env
Sau khi activate: python -m pip install --upgrade pip và pip install -r requirements.txt. Kiểm tra python --version in ra 3.11, 3.12 hoặc 3.13.

Lưu ý theo hệ điều hành:

Windows: dùng cmd thì activate bằng .venv\Scripts\activate.bat; dùng Git Bash thì source .venv/Scripts/activate.
macOS: python3 có sẵn của máy là 3.9, còn brew install python (không kèm version) sẽ cài 3.14, đều không dùng được.
Ubuntu 22.04: chỉ có sẵn Python 3.10, hãy dùng Cách A.
4.2. Tạo project Langfuse cá nhân

1. Đăng ký hoặc đăng nhập Langfuse Cloud. Ghi nhớ region bạn chọn (EU hoặc US).
2. Tạo một Organization, rồi tạo project tên day13-k4-l3b-<MSSV> (vd day13-k4-l3b-123456).
3. Vào Project Settings → API Keys, tạo key pair. Copy secret key ngay, vì nó chỉ hiện một lần.
4. Mở .env, chỉ sửa 3 dòng dưới đây và giữ nguyên các dòng khác (LANGFUSE_PROMPT_NAME=day13-chat, LANGFUSE_PROMPT_LABEL=production đã có sẵn):
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=https://cloud.langfuse.com
   Chép
   Chọn region US thì đổi thành https://us.cloud.langfuse.com. Không để dấu cách quanh dấu =. Nếu chưa tạo được Langfuse (vd đang chờ xác thực email), app vẫn chạy được: cứ làm CP1 trước, điền key sau rồi khởi động lại API.

4.3. Chạy baseline
Mở 2 terminal, cả hai đều ở thư mục gốc repo và đều phải activate venv.

Terminal 1 (API):

uvicorn app.main:app --reload --env-file .env
Chép
Terminal 2:

python scripts/load_test.py
python scripts/validate_logs.py
python scripts/validate_dashboard.py
python -m pytest -q
Chép
CP0 hoàn thành khi http://127.0.0.1:8000/health trả ok: true và tracing_enabled: true, có file data/logs.jsonl, và thấy trace mới trong project Langfuse của bạn. Ở bước này validator log chỉ khoảng 30/100 là bình thường; ghi số baseline vào submission/REPORT.md trước khi sửa code.

4.4. Lỗi thường gặp
Triệu chứng Cách xử lý
pip install treo lâu, hoặc báo lỗi maturin, Rust, Microsoft Visual C++ 14.0 is required Đang dùng Python 3.14. Xoá .venv, tạo lại bằng 3.12
PowerShell chặn Activate.ps1 Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass rồi activate lại
Python was not found (Windows) Dùng py -3.12, hoặc cài Python 3.12 từ python.org (tick "Add python.exe to PATH")
ensurepip is not available (Linux) sudo apt install python3-venv
ModuleNotFoundError: No module named 'httpx' / 'fastapi' Terminal đó chưa activate venv
ModuleNotFoundError: No module named 'app' khi test Chạy python -m pytest -q ở thư mục gốc
address already in use / WinError 10048 Port 8000 đang bị chiếm. Tìm tiến trình: Windows `netstat -ano \	findstr :8000, macOS/Linux lsof -i :8000`; tắt nó rồi chạy lại. Các script của lab luôn gọi port 8000
Đã sửa code và restart mà response vẫn như cũ API cũ có thể chưa tắt hẳn (bị treo khi đang gửi trace lúc mạng chậm) và vẫn giữ port 8000. Dùng lệnh ở dòng trên để tìm và tắt tiến trình cũ
/health trả tracing_enabled: false .env thiếu key, hoặc chưa chạy uvicorn với --env-file .env
Không thấy trace Kiểm tra key và LANGFUSE_BASE_URL đúng region, restart API, mở đúng project, chọn khoảng thời gian gần nhất
Terminal API in Failed to export spans … timed out Mạng chậm nên trace của batch đó bị mất. Chạy lại load test
Langfuse có trace lạ session-01, correlation_id=MISSING Do chạy pytest trong terminal đã nạp key Langfuse. Không tính vào 10 trace của bạn

CP1 — Structured logging và bảo vệ PII
Mục tiêu: mỗi request có một mã theo dõi duy nhất đi cùng nó từ lúc nhận vào, ghi log, tạo trace đến lúc trả response; log phải an toàn (không có PII thô).

File Việc cần làm
app/middleware.py Xoá context cũ (clear_contextvars()); nhận header x-request-id hoặc sinh ID dạng req- + 8 ký tự hex; bind ID; trả x-request-id và x-response-time-ms trong response header
app/main.py Bind user_id_hash, session_id, feature, model, env trước dòng log request_received
app/logging_config.py Bật PII scrubber (scrub_event) trước bước ghi file/render JSON
app/pii.py, tests/test_pii.py Pattern email, điện thoại VN, CCCD, thẻ đã có sẵn (README ghi "hoàn thiện pattern"); việc cần làm là viết thêm test cho CCCD và thẻ, có thể bổ sung pattern khác
Kiểm tra:

1. Chuyển log cũ ra ngoài repo (không chỉ đổi tên trong data/, vì .gitignore chỉ bỏ qua đúng data/logs.jsonl, file đã đổi tên sẽ bị commit):
   macOS/Linux: mv data/logs.jsonl ../logs-cp0-baseline.jsonl
   Windows: Move-Item data\logs.jsonl ..\logs-cp0-baseline.jsonl
1. Restart API.
1. python scripts/load_test.py
1. python scripts/validate_logs.py
   CP1 hoàn thành khi điểm ≥ 80/100, response header có x-request-id đúng format, và log không còn PII thô. Chụp 04, 05 ngay (xem 8.2).

CP2 — Traces, prompt, dashboard và alert
6.1. Trace trên Langfuse
Starter mới có root observation lab-agent-run. Bạn cần thêm child observation để trace đọc được như cây sau (giống README):

day13-agent-request
└── lab-agent-run
├── retrieval: tìm tài liệu/context liên quan (loại retriever hoặc span)
└── generation: gọi LLM để sinh câu trả lời (loại generation)
Chép
Generation cần có:

model;
usage (token input/output);
cost;
liên kết tới prompt version: truyền đối tượng prompt lấy từ Langfuse qua tham số prompt=, không gửi nội dung prompt đã điền câu hỏi.
Không capture raw input/output (câu hỏi có thể chứa PII). correlation_id phải có trong metadata của trace để nối với log.

Mục tiêu: ≥ 10 trace đủ cây trong project của bạn.

Public test tests/test_agent_prompt_trace.py được viết theo cách tạo child observation bằng decorator @observe(...) trên retrieve và FakeLLM.generate. Nếu bạn dùng cách khác mà test này fail, hãy chuyển sang @observe.
Trace được gửi lên Langfuse ở chế độ nền: sau request cuối, chờ vài giây rồi mới dừng hoặc restart API, nếu không trace sẽ mất. Đối chiếu số trace trên Langfuse với số request trong log.
6.2. Quản lý phiên bản prompt
Ý tưởng (xem thêm README, phần "Hiểu nhanh về prompt versioning"): label là con trỏ tới một version. App lấy prompt theo LANGFUSE_PROMPT_LABEL, nên đổi prompt đang dùng không cần sửa code, chỉ cần dời label.

production -> day13-chat v1 →(promote)→ production -> day13-chat v2 →(rollback)→ production -> day13-chat v1
Chép
Làm theo docs/PROMPT_VERSIONING.md:

1. Tạo text prompt (không phải chat) tên day13-chat, giữ đúng 3 biến {{feature}}, {{docs}}, {{message}}. Gắn labels baseline và production cho version 1.
2. Tạo version 2 với một thay đổi nhỏ (vd thêm dòng "trả lời ngắn gọn"), gắn label candidate.
3. Đặt LANGFUSE_PROMPT_LABEL=baseline trong .env, restart API, gửi request. Đổi thành candidate, restart, gửi request. Xong thì đặt lại production.
4. Mở 2 trace, bấm vào dòng lab-agent-run, xem tab Metadata: prompt_name, prompt_label, prompt_version phải đúng. Ghi lại 2 trace ID (một của v1, một của v2).
5. Promote: dời label production sang v2, restart API, gửi 1 request để kiểm tra.
6. Rollback: dời production về v1, restart, gửi 1 request để kiểm tra. Chụp trạng thái label sau bước 5 và sau bước 6.
   Những điều hay làm học viên bối rối:

Làm cả promote lẫn rollback (bước 5 và 6).
Langfuse tự gắn label latest vào version mới nhất; đây là bình thường.
Mỗi label chỉ nằm trên một version: gắn production cho v2 thì v1 tự mất label đó.
App cache prompt khoảng 60 giây, nên sau mỗi lần đổi label thì restart API rồi mới kiểm tra.
Fake LLM luôn trả cùng một câu trả lời, nên v1 và v2 chỉ khác prompt_version và tokens_in. Đây là bình thường.
Metadata hiện local-v1: prompt_source=local nghĩa là chưa bật Langfuse; local-fallback nghĩa là tải prompt lỗi. Kiểm tra key/region, tên và label, prompt có phải loại Text không, rồi restart API.
6.3. Dashboard
Dựng đúng 6 panel từ data/logs.jsonl theo config/dashboard.yaml. Công cụ tuỳ chọn: Streamlit, notebook, Grafana, script vẽ biểu đồ…

Panel Câu hỏi cần trả lời
Latency Request có chậm không? P50/P95/P99 và TTFT đang ở mức nào?
Traffic Hệ thống đang nhận bao nhiêu request theo thời gian?
Errors Error rate có tăng không, retrieval có đang fail không?
Cost Chi phí có tăng bất thường không?
Tokens Input/output token có dài bất thường không?
Quality Quality proxy có giảm dưới mức chấp nhận được không?
Mỗi panel cần: tên, đơn vị, time range 60 phút, refresh 30 giây (nếu công cụ hỗ trợ), và đường threshold.

Gợi ý:

Retrieval success = tỉ lệ tool_success == true trên mọi event có field tool_success, gồm cả response_sent lẫn request_failed. Nếu chỉ lấy request_failed (như danh sách events trong YAML) thì kết quả luôn là 0 %.
Công cụ vẽ không có sẵn trong requirements.txt, hãy cài vào venv riêng. Streamlit cài chung sẽ hạ phiên bản thư viện mà API đang dùng.
st.line_chart không vẽ được threshold; dùng altair mark_rule, plotly add_hline hoặc matplotlib axhline.
Trường ts trong log là giờ UTC. Chạy load_test.py rải rác 10–15 phút để biểu đồ theo phút có đủ điểm.
Đã chạy practice thì trước khi chụp dashboard, chuyển log cũ ra ngoài repo (như CP1) rồi chạy lại load test; nếu không, request lỗi của practice sẽ làm lệch error rate.
Kiểm tra contract: python scripts/validate_dashboard.py (chỉ kiểm tra cấu trúc YAML; ảnh dashboard có dữ liệu vẫn bắt buộc).

6.4. SLO và alerts
config/slo.yaml: giải thích hoặc điều chỉnh SLO dựa trên baseline của bạn, và tính error budget ra số request. Ví dụ: SLO 99,5 % với 10.000 request thì tối đa 50 request được phép chậm hoặc lỗi.
config/alert_rules.yaml: thay hết TODO bằng 3 alert symptom-based, mỗi alert có condition, duration, severity, owner, Slack channel, runbook.
docs/alerts.md: viết runbook cho từng alert (ba bước kiểm tra Metrics → Logs → Traces, mitigation). Đầu file có alert mẫu để tham khảo. Giữ nguyên heading ## Alert 1/2/3, vì link #alert-1 trong YAML trỏ vào đó.

CP3 — Điều tra challenge
Starter không chứa file đề. Khi mở CP3, Lab Coach đưa file đề lên starter và gửi một đường link. Ở thư mục gốc repo, tải file về đúng vị trí:

# macOS / Linux / Git Bash

curl -fsSL -o config/challenge.json "<LINK_LAB_COACH_GỬI>"
Chép

# Windows PowerShell (gõ đúng curl.exe)

curl.exe -fsSL -o config/challenge.json "<LINK_LAB_COACH_GỬI>"
Chép
Mở file, xác nhận challenge_id là day13-k4-l3b-monitoring-llmops-v1.
Không bấm Sync fork để lấy đề; file chỉ cần có trên máy bạn.
config/challenge.json đã nằm trong .gitignore: không force-add, commit, push hoặc chia sẻ.
Chuẩn bị (làm theo thứ tự):

1. Chuyển log hiện tại ra ngoài repo (như CP1), để dashboard CP3 chỉ còn dữ liệu mới.
2. Tắt incident practice nếu còn bật: python scripts/inject_incident.py --scenario <tên> --disable. Mở /health, kiểm tra mọi incidents đều false.
3. Chạy API không có --reload: uvicorn app.main:app --env-file .env. Với --reload, chỉ cần lưu file là server khởi động lại và incident tự tắt.
4. Chạy python scripts/load_test.py một lần (chưa bật incident) để có baseline trong cửa sổ CP3.
   Chạy challenge (chỉ khi Lab Coach thông báo mở):

python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
Chép
Chưa có file đề thì script in lỗi, dòng cuối là FileNotFoundError: config/challenge.json chưa được Lab Coach release…. Khi đó cứ tiếp tục practice bằng --scenario (xem danh sách bằng python scripts/inject_incident.py --help).

Điều tra theo đúng thứ tự (không đoán root cause, không mở trace ngẫu nhiên):

1. Metrics: panel nào bất thường, giá trị bao nhiêu so với baseline, lúc mấy giờ. Latency lấy từ latency_ms trong log/dashboard. Không dùng thời gian mà load_test.py in ra: với --concurrency 5 các request xếp hàng, nên số phía client lớn hơn nhiều so với thực tế.
2. Logs: lọc data/logs.jsonl trong khoảng đó, chọn một request bất thường, ghi correlation_id.
3. Traces: mở trace có cùng correlation_id, so sánh thời gian và trạng thái các span.
4. Kết luận: root cause, fix action, preventive measure vào submission/REPORT.md, kèm challenge ID, metric, log line/correlation_id, trace ID. Ba bằng chứng phải cùng chỉ về một nguyên nhân.
   Chỉ dùng file Lab Coach gửi cho K4-L3B; không sửa nội dung, không tự tạo, không lấy file của lớp khác (0 điểm phần incident).
   Nếu hoàn thành sớm, Lab Coach có thể gửi thêm link một challenge phụ (challenge_id khác). Tắt incident vừa điều tra (--scenario <tên> --disable), tải file mới đè lên config/challenge.json, chuyển log ra ngoài repo, rồi làm lại các bước trên. Cách ghi vào report theo hướng dẫn của Lab Coach.
