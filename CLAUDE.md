# CLAUDE.md — Custom component `nchmf`

Tài liệu ngữ cảnh cho việc sửa lỗi / nâng cấp về sau. Đưa nguyên file này vào đầu
phiên làm việc là đủ context, không cần giải thích lại từ đầu.

---

## 1. Mục đích & nguồn dữ liệu

Custom component lấy dữ liệu thời tiết từ **Trung tâm Dự báo KTTV quốc gia (nchmf)**
bằng cách **scrape HTML** (site không có API JSON; RSS `homerss.html` trả 404).

- URL nguồn: `https://www.nchmf.gov.vn/kttv/vi-VN/1/da-nang-w55.html` (Hải Châu, Đà Nẵng).
- `iot_class: cloud_polling` — dữ liệu ở server nchmf, KHÔNG local-only.
- **Quan trọng:** site .gov.vn lỗi chuỗi chứng chỉ SSL → **bắt buộc fetch với `ssl=False`**.
  Đây là nguyên nhân gốc từng làm mọi sensor về None khi còn dùng multiscrape.

Thay thế cho giải pháp cũ (multiscrape + template weather YAML) — khi bản này chạy
ổn thì đã xoá 2 block đó khỏi `configuration.yaml`.

---

## 2. Cài đặt & nạp

- Thư mục: `/config/custom_components/nchmf/`
- Nạp qua YAML: thêm dòng `nchmf:` vào `configuration.yaml` → Restart.
- **Không có config flow / UI.** Địa điểm cố định trong code (`const.py`).
- Nạp platform bằng cơ chế discovery cũ: `async_setup` → `discovery.async_load_platform`
  cho `weather` và `sensor`. Vì vậy `async_setup_platform` nhận `discovery_info={}` (không None).

Đổi địa điểm: sửa `URL` trong `const.py` (lấy URL tỉnh khác trên nchmf, đổi mã `w..`),
rồi Restart. Selector/parser giữ nguyên vì mọi trang tỉnh dùng chung template HTML.

---

## 3. Sơ đồ file

| File | Trách nhiệm |
|------|-------------|
| `__init__.py` | `async_setup` + `NchmfCoordinator` (fetch async + gọi parse trong executor). Update mỗi 30'. |
| `parser.py` | `parse_html(raw)` → dict có cấu trúc. **Toàn bộ logic scrape nằm ở đây.** |
| `weather.py` | `weather.nchmf_da_nang` — condition + current + `async_forecast_daily` (9 ngày). |
| `sensor.py` | 4 sensor: nhiệt độ, độ ẩm, gió (hiện tại) + mảng nhiệt độ 10 ngày qua. |
| `const.py` | `DOMAIN`, `URL`, `SCAN_INTERVAL_MINUTES`, `USER_AGENT`. |
| `manifest.json` | `requirements: ["beautifulsoup4"]` (đã có sẵn trong HA core). |

Kiến trúc: 1 `DataUpdateCoordinator` fetch/parse 1 lần, mọi entity là `CoordinatorEntity`
đọc chung `coordinator.data`. Parse chạy trong executor (`hass.async_add_executor_job`)
vì BeautifulSoup là sync.

---

## 4. Cấu trúc HTML mà parser phụ thuộc (PHẦN DỄ VỠ NHẤT)

Nếu nchmf đổi giao diện → sensor về None/unavailable → **90% là do các selector dưới đây
đổi**. Kiểm tra bằng cách so với HTML thật (xem mục 6).

```
.tt-news                         -> tên địa điểm  ("Thời tiết Hải Châu (Tp Đà Nẵng)")
.content-news                    -> container chính (nếu None -> parser raise ValueError)
  .text-weather-location  (x3)   -> 3 khối: [0] hiện tại, [1] hôm nay, [2] đêm nay
    .time-update                 -> "Cập nhật: 10h 01/07/2026"
    ul.list-info-wt li           -> mỗi dòng thông tin
      .uk-width-1-4              -> nhãn: "Nhiệt độ" / "Thời tiết" / "Độ ẩm" / "Hướng gió"
      .uk-width-3-4              -> giá trị, dạng ": 34°C" (đã lstrip ":")
  .item-days-wt          (x~9)   -> mỗi ngày forecast
    .date-wt > span              -> ngày "02/07/2026"; weekday = text trừ đi ngày
    .large-temp                  -> nhiệt độ CAO "34°C"
    .small-temp  (phần tử ĐẦU)   -> nhiệt độ THẤP "26°C"  (mỗi ngày có 4 .small-temp:
                                     thấp / bullet rỗng / °% / gió — select_one lấy cái đầu)
    .text-temp                   -> mô tả "Có mây, có mưa rào"
  <script> ... series data:[...] -> mảng nhiệt độ 10 ngày qua (Highcharts)
  <script> ... categories:[...]  -> mốc thời gian "22/6(1h)" ...
```

Điểm tinh:
- Khối "hôm nay"/"đêm nay" KHÔNG có dòng "Thời tiết" → chỉ khối hiện tại có `condition_text`.
- "Hướng gió" khối hiện tại: `"Gió đông - tốc độ: 1 m/s"` (có hướng). Khối hôm nay/đêm nay
  hướng nằm trong `<img>` (mất khi get_text) → chỉ còn `"tốc độ: 4m/s"`, wind_dir = "".
- Tốc độ gió: regex `(\d+)\s*m/s` khớp cả "1 m/s" lẫn "4m/s".

---

## 5. Schema `coordinator.data` (output của `parse_html`)

```python
{
  "location": str,
  "update_time": str,                 # của khối hiện tại
  "current": {temp:int, humidity:int, wind_speed:float, wind_dir:str,
              condition_text:str, condition:str|None, update_time:str},
  "today":   {...cùng key, condition_text="" , condition=None},
  "night":   {...},
  "forecast": [ {datetime:isostr, weekday:str, date:str,
                 temperature:int, templow:int, condition:str, condition_text:str}, ... ],
  "past_temps": [int, ...],           # ~76 điểm, mỗi 3h
  "past_times": [str, ...],           # "22/6(1h)" ...
}
```

Mọi property của entity đều guard `(self.coordinator.data or {})` → data None (fetch fail)
không crash, entity chỉ `unavailable` (nhờ `CoordinatorEntity.available`).

---

## 6. Map điều kiện tiếng Việt -> mã HA  (`parser.map_condition`)

Thứ tự ưu tiên (khớp keyword đầu tiên thắng):

| Keyword trong mô tả | Mã HA |
|---|---|
| `dông` | `lightning-rainy` |
| `mưa` | `rainy` |
| `sương mù` / `mù` | `fog` |
| `nhiều mây` | `cloudy` |
| `ít mây` | `sunny` |
| `nắng` | `sunny` |
| `mây` (còn lại) | `partlycloudy` |
| mặc định | `partlycloudy` |

Gặp mô tả lạ ra icon sai → thêm nhánh vào `map_condition`. Mã HA hợp lệ:
`clear-night, cloudy, fog, hail, lightning, lightning-rainy, partlycloudy, pouring,
rainy, snowy, snowy-rainy, sunny, windy, windy-variant, exceptional`.

---

## 7. Entity tạo ra

- `weather.nchmf_da_nang` — state = mã điều kiện; forecast daily 9 ngày.
  Card: `type: weather-forecast`, `entity: weather.nchmf_da_nang`, `forecast_type: daily`.
  Attributes phụ: `condition_text` (chữ Việt gốc), `wind_dir`, `location`, `update_time`.
- `sensor.nchmf_da_nang_nhiet_do` (°C, device_class temperature)
- `sensor.nchmf_da_nang_do_am` (%, humidity)
- `sensor.nchmf_da_nang_gio` (m/s, wind_speed; attr `wind_dir`)
- `sensor.nchmf_da_nang_nhiet_do_10_ngay_qua` (attr `temperatures`, `times` cho apexcharts)

---

## 8. Quyết định thiết kế & lý do (đừng "sửa" lại kẻo hỏng)

- **`ssl=False`** khi fetch: bắt buộc, site lỗi cert. Bỏ đi = fail toàn bộ.
- **KHÔNG `device_info`**: setup YAML không có config entry → device registry cần
  config_entry_id, thêm device_info sẽ bị bỏ qua + ghi warning. Cố tình bỏ.
- **`_handle_coordinator_update`** gọi `super()` (ghi state hiện tại) + `self.async_update_listeners()`
  (đẩy forecast tới card đang subscribe). LƯU Ý: `async_update_listeners` trên WeatherEntity
  là một `@callback` ĐỒNG BỘ → gọi trực tiếp, KHÔNG bọc trong `async_create_task`
  (bọc vào sẽ truyền `None` cho `async_create_task` và raise mỗi lần update). Cũng khác
  với `coordinator.async_update_listeners` — đừng nhầm.
- **Parse trong executor**: BeautifulSoup sync, không chạy trong event loop.
- **`asyncio.timeout(30)`**: cần Python 3.11+ (HA hiện đại có). Nếu HA quá cũ báo lỗi
  dòng này -> đổi sang `import async_timeout` + `async with async_timeout.timeout(30)`.
- **Lưu list dạng bytes->utf-8 decode "replace"**: tránh lỗi charset.

---

## 9. Cách test parser NGOÀI Home Assistant (không cần HA chạy)

`parser.py` chỉ phụ thuộc `bs4` + `homeassistant.util.dt`. Stub `dt_util` rồi chạy:

```python
import sys, types
from datetime import timezone
dtm = types.ModuleType("homeassistant.util.dt")
dtm.start_of_local_day = lambda d: d.replace(tzinfo=timezone.utc)
sys.modules["homeassistant"] = types.ModuleType("homeassistant")
sys.modules["homeassistant.util"] = types.ModuleType("homeassistant.util")
sys.modules["homeassistant.util.dt"] = dtm

import importlib.util
spec = importlib.util.spec_from_file_location("parser", "parser.py")
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
print(p.parse_html(open("trang_that.html", encoding="utf-8").read()))
```

Lấy `trang_that.html`: gọi service `multiscrape.get_content` (nếu còn) hoặc
`curl -k <URL>` từ máy có mạng, lưu ra file, rồi chạy đoạn trên.

---

## 10. Các kịch bản lỗi thường gặp -> soi ở đâu

| Triệu chứng | Nguyên nhân khả dĩ | Kiểm tra |
|---|---|---|
| Tất cả entity `unavailable` | fetch fail (SSL/timeout/site sập) | Log `custom_components.nchmf`; xác nhận `ssl=False` còn nguyên; thử `curl -k URL` |
| Entity `unknown`, không có lỗi | `.content-news` còn nhưng selector con đổi | So HTML thật với mục 4; sửa selector trong `parser.py` |
| `parser raise ValueError` | `.content-news` biến mất (đổi layout) | Xem HTML thật, tìm container mới |
| Nhiệt độ thấp sai (lấy nhầm °%/gió) | thứ tự `.small-temp` đổi | Đổi `select_one(".small-temp")` sang selector cụ thể hơn |
| Forecast không refresh | `async_update_listeners` không được gọi | Kiểm `_handle_coordinator_update` trong `weather.py` |
| Icon điều kiện sai | map thiếu keyword | Thêm nhánh vào `map_condition` |
| Restart lâu / lỗi import bs4 | requirement chưa cài | Log; bs4 vốn có sẵn trong HA core |
| Lỗi dòng `asyncio.timeout` | HA/Python quá cũ | Đổi sang `async_timeout` (mục 8) |

Bật log chi tiết:
```yaml
logger:
  default: warning
  logs:
    custom_components.nchmf: debug
```

---

## 11. Ý tưởng nâng cấp (chưa làm)

- **Config flow / UI** để chọn tỉnh thay vì sửa code (cần thêm `config_flow.py`,
  `config_flow: true`, và chuyển sang `async_setup_entry` + `async_forward_entry_setups`).
  Khi đó `device_info` dùng lại được vì có config entry.
- **Forecast hourly**: không có sẵn trên trang tỉnh; chỉ có mảng 10 ngày QUA (quá khứ).
- **Icon thật của nchmf**: URL nằm ở `.icon-days-wt img` / `.icon-list-item img`
  (mã như `2301.png`, `1011.png`), có thể map sang entity_picture nếu muốn.
- **% mưa**: trang có ô `°%` nhưng bỏ trống -> không dùng được.

---

## 12. Phiên bản

- v1.0.0 — bản đầu, cố định Đà Nẵng, weather + 3 sensor + past-temps sensor.
  Đã test parser end-to-end trên HTML thật (2026-07): current/today/night/forecast/
  past_temps đều đúng; map điều kiện đúng cho rainy/sunny/lightning-rainy.
