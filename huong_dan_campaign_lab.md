# campaign-lab — luyện quy trình dự án cho *Applying Data Analytics in Marketing*

Cùng triết lý với `gl-audit-lab`: **dữ liệu là thứ tẻ nhạt nhất trong repo**. Một bảng CSV, ~4.000 dòng, tự sinh bằng script có seed, và bạn biết trước mọi đáp án. Toàn bộ sự chú ý dồn vào `pyproject.toml`, `pre-commit`, `pytest`, GitHub Actions.

## Vì sao không dùng Hillstrom hay Olist cho việc này?

Ba thứ phải học cùng lúc khi dùng dữ liệu thật: (1) tooling, (2) schema/định dạng của dataset, (3) *tính ngẫu nhiên của thống kê* — với Hillstrom bạn không bao giờ biết uplift "đúng" là bao nhiêu, nên test chỉ có thể viết kiểu `assert 0.00 < uplift < 0.05`. Test như vậy dạy bạn rất ít về việc test *nên* làm gì.

**Thủ thuật cốt lõi của lab này: gán kết quả theo hạn ngạch (quota), không tung xúc xắc.** Trong mỗi ô `(segment, treatment)` có `n` khách, đúng `round(n × rate)` người được chọn (ngẫu nhiên) để convert. Kết quả: tỷ lệ chuyển đổi quan sát được **bằng đúng** tỷ lệ đã gieo, và test khẳng định `ate == 0.032`, không phải "khoảng 0.03".

Số liệu gieo sẵn:

| Ô | n / arm | control | treatment | uplift |
|---|---|---|---|---|
| New | 800 | 5 % (40) | 8 % (64) | +3 pp |
| Regular | 800 | 10 % (80) | 15 % (120) | +5 pp |
| VIP | 400 | 20 % (80) | 20 % (80) | **0** |
| **Tổng** | 2 000 | **10.0 %** (200) | **13.2 %** (264) | **+3.2 pp** |

VIP cố ý không có hiệu ứng → bài học về *heterogeneous treatment effect*: ATE toàn cục dương nhưng chi tiền gửi mail cho VIP là lãng phí.

Lỗi gieo sẵn: 20 dòng trùng lặp toàn phần, 15 dòng `converted == 0` nhưng `revenue > 0` (lỗi tracking), 30 feedback chứa chữ "refund".

Phủ module: M1 (A/B test, z-test, CATE, kiểm tra randomization), M3 (đếm keyword trong feedback — bước sơ khai của NLP), M4 (RFM score). M2 (churn/forecast) không ép vào — không cần, mục tiêu là quy trình.

---

## Thứ tự dựng — mỗi bước một commit

### Bước 1 — Khởi tạo và *đọc* `pyproject.toml`

```bash
cd ~/luyen_tap
uv init --package campaign-lab
cd campaign-lab
cat pyproject.toml
```

`--package` tạo **src layout** (`src/campaign_lab/`) thay vì file `.py` nằm ngoài. Lý do: khi `pytest` chạy, nó import `campaign_lab` từ package đã cài vào `.venv`, không phải từ thư mục hiện tại — đây chính là cách code của bạn sẽ được người khác (và CI) dùng. Không có src layout, test đôi lúc pass ở máy bạn nhưng fail trên CI vì `sys.path` khác nhau.

Ba khối trong file sinh ra:

- `[project]` — dự án *là gì*: tên, phiên bản, `requires-python`, `dependencies`. Mọi tool khác đọc từ đây.
- `[project.scripts]` — tạo lệnh terminal trỏ vào một hàm Python. Đổi thành `campaign-generate = "campaign_lab.generate:main"` → sau `uv sync`, gõ `uv run campaign-generate` là chạy `main()`.
- `[build-system]` — cách đóng gói; giữ nguyên.

```bash
git add -A && git commit -m "chore: scaffold with uv init --package"
```

### Bước 2 — Cấu hình tool tập trung trong `pyproject.toml`

Chép nội dung `pyproject.toml` trong repo mẫu. Điểm cần hiểu:

- `[dependency-groups] dev = [...]` — pytest/ruff/pre-commit là thứ *người phát triển* cần, không phải thứ package cần khi chạy. `uv sync` cài cả hai; `uv sync --no-dev` chỉ cài `dependencies`.
- `[tool.ruff]` / `[tool.ruff.lint] select = ["E","F","I","B","UP"]` — E/F là lỗi cú pháp & pyflakes, **I** sắp thứ tự import, **B** bắt bug phổ biến, **UP** hiện đại hoá cú pháp (`Optional[str]` → `str | None`). Không có `.ruffrc`, không có `setup.cfg`.
- `[tool.pytest.ini_options] testpaths = ["tests"]` — pytest không phải lần mò cả repo.

```bash
uv add pandas numpy
uv add --dev pytest ruff pre-commit
```

`uv add` làm 3 việc: sửa `pyproject.toml`, cập nhật `uv.lock`, cài vào `.venv`. **Commit cả `uv.lock`** — đó là thứ đảm bảo CI cài đúng phiên bản bạn đang dùng.

```bash
git add -A && git commit -m "build: pin deps, centralize ruff+pytest config"
```

### Bước 3 — `generate.py`, `analysis.py`, tests

Chép 3 file từ repo mẫu: `src/campaign_lab/generate.py`, `src/campaign_lab/analysis.py`, `tests/conftest.py`, `tests/test_data_quality.py`, `tests/test_analysis.py`.

Đọc kỹ 3 chỗ trong `generate.py`:

1. Mọi con số gieo sẵn là **hằng số module** (`N_DUPLICATES = 20`, `CONV_RATE = {...}`). Test import chính hằng số đó (`assert len(dups) == g.N_DUPLICATES`), nên đổi số ở một chỗ thì test tự theo — không có "magic number" rải trong test.
2. `_exact_split` và `plant_outcomes` dùng `rng.choice(..., replace=False)` với `size = round(n × rate)` — đây là chỗ biến "xác suất" thành "hạn ngạch".
3. `plant_anomalies` chạy **sau cùng**, và duplicate được `concat` thêm vào — nên dữ liệu thô có 4.020 dòng, và nếu bạn chạy `ate()` trên dữ liệu thô thì kết quả sai lệch. Đây là lý do `analysis.clean()` tồn tại và `conftest.py` có hai fixture `raw` và `df`.

Về `analysis.py`: mọi hàm nhận DataFrame, trả DataFrame hoặc số, **không đọc file**. Nhờ vậy test không cần đĩa, không cần `data/campaign.csv` tồn tại. `two_proportion_ztest` dùng `statistics.NormalDist` của stdlib thay vì kéo `scipy` vào — dependency ít thì CI nhanh và ít vỡ.

```bash
uv run pytest
# 12 passed
```

Rồi nhìn kết quả bằng mắt:

```bash
uv run python -c "
from campaign_lab.generate import generate
from campaign_lab.analysis import clean, conversion_by_arm, uplift_by_segment, two_proportion_ztest
df = clean(generate())
print(conversion_by_arm(df)); print(uplift_by_segment(df)); print(two_proportion_ztest(df))"
```

Bạn sẽ thấy `0.100 / 0.132`, uplift `0.03 / 0.05 / 0.00`, z ≈ 3.16, p ≈ 0.0016.

```bash
git add -A && git commit -m "feat: seeded campaign generator, analysis checks, 12 tests"
```

### Bước 4 — Ruff: lint và format là hai việc khác nhau

```bash
uv run ruff check .            # tìm lỗi logic/style; có thể sửa 1 phần bằng --fix
uv run ruff format --check .   # chỉ kiểm tra bố cục code (dấu cách, xuống dòng)
uv run ruff format .           # thực sự sửa
```

Thử tự gây lỗi: thêm `import os` thừa vào `analysis.py` → `ruff check` báo F401 → `ruff check --fix .` xoá nó. Thêm một dòng dài 130 ký tự → `ruff format` bẻ dòng.

### Bước 5 — pre-commit: CI chạy trước trên máy bạn

Chép `.pre-commit-config.yaml`. Mỗi `repo` là một nguồn hook, `rev` là tag cố định (không dùng `main` — để tuần sau kết quả vẫn y hệt).

```bash
uv run pre-commit install          # ghi vào .git/hooks/pre-commit
uv run pre-commit run --all-files  # chạy tay lần đầu để hook tải về
```

Hành vi quan trọng cần trải nghiệm một lần: khi hook **sửa** file (ruff-format, trailing-whitespace), commit bị **chặn**, file đã sửa nằm ở working tree chưa staged. Bạn phải `git add` lại rồi commit lần hai. Đây không phải lỗi — hook không bao giờ tự ý commit code mà bạn chưa xem.

```bash
echo "x=1" >> src/campaign_lab/__init__.py   # cố ý sai format
git add -A && git commit -m "test hook"       # bị chặn, ruff-format sửa thành "x = 1"
git diff                                      # xem hook đã đổi gì
git checkout -- src/campaign_lab/__init__.py  # hoàn lại thí nghiệm
git add -A && git commit -m "ci: add pre-commit hooks"
```

`check-added-large-files --maxkb=500` + dòng `data/*.csv` trong `.gitignore`: hai lớp bảo hiểm để CSV sinh ra không bao giờ lọt vào Git.

### Bước 6 — GitHub Actions

Chép `.github/workflows/ci.yml`. Đối chiếu từng bước với thứ bạn vừa gõ tay:

| Local | CI |
|---|---|
| `uv sync` | `uv sync --locked` (fail nếu `uv.lock` lệch với `pyproject.toml`) |
| `uv run ruff check .` | step *Lint* |
| `uv run ruff format --check .` | step *Format check* |
| `uv run campaign-generate` | step *Generate data* (data không có trong repo, CI tự sinh) |
| `uv run pytest` | step *Test* |

Tạo repo trên GitHub rồi push:

```bash
gh repo create Kimlong42/campaign-lab --public --source=. --remote=origin
git push -u origin main
gh run watch
```

**Bài tập bắt buộc — làm CI đỏ có chủ ý.** Trong `generate.py`, đổi `"VIP": {0: 0.20, 1: 0.20}` thành `{0: 0.20, 1: 0.25}`. Commit, push. `test_conversion_rates_match_planted` và `test_ate_is_exact` fail vì treatment giờ là 284/2000 = 0.142. Đọc log trên GitHub, xác nhận bạn hiểu *vì sao* fail, rồi revert:

```bash
git revert HEAD && git push
```

Bài tập thứ hai, tinh tế hơn: xoá `.clean(...)` trong fixture `df` của `conftest.py` để test chạy trên dữ liệu thô. Quan sát: `test_arms_are_balanced` fail (20 dòng trùng làm hai arm lệch), `test_ate_is_exact` fail. Đây chính là lỗi bạn sẽ gặp với dữ liệu thật khi quên bước làm sạch — và test là thứ bắt được nó.

### Bước 7 — Makefile, README, badge

Chép `Makefile` và `README.md`. Makefile chỉ là *bí danh* cho các lệnh đã gõ ở trên — bạn học nó **sau cùng** để không che mất lệnh thật. Thêm badge vào đầu README:

```markdown
![CI](https://github.com/Kimlong42/campaign-lab/actions/workflows/ci.yml/badge.svg)
```

---

## Đường di cư sang dữ liệu thật (Hillstrom / Olist)

| campaign-lab | Dữ liệu thật |
|---|---|
| `generate.py` | `extract.py` (đọc CSV/Parquet đã tải, hoặc `kagglehub`) |
| `assert ate == approx(0.032)` | `assert 0 < ate < 0.10` hoặc `assert p < 0.05` — khẳng định **khoảng có ý nghĩa**, không phải điểm |
| `assert len(dups) == 20` | `assert find_duplicates(df).empty` **sau** `clean()` — khẳng định *bất biến* (invariant) |
| `check_randomization` chênh `< 1e-9` | chênh `< 0.02` + chi-square test |
| CI step *Generate data* | CI dùng một **sample nhỏ** commit kèm repo (`data/sample.csv`, < 500 KB) để test; dữ liệu đầy đủ chỉ chạy local |

`analysis.py` **giữ nguyên** — vì nó không biết dữ liệu đến từ đâu. Đó là phần thưởng của việc tách "lấy dữ liệu" khỏi "phân tích dữ liệu" ngay từ đầu.
