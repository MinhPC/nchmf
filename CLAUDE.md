# CLAUDE.md — Custom component `nchmf`

Tài liệu ngữ cảnh cho việc sửa lỗi / nâng cấp về sau. Đưa nguyên file này vào đầu
phiên làm việc là đủ context, không cần giải thích lại từ đầu.

---

## 1. Mục đích & nguồn dữ liệu

Custom component lấy dữ liệu thời tiết từ **Trung tâm Dự báo KTTV quốc gia (nchmf)**
bằng cách **scrape HTML** (site không có API JSON; RSS `homerss.html` trả 404).

- URL nguồn: `https://www.nchmf.gov.vn/kttv/vi-VN/1/da-nang-w55.html` (Hải Châu, Đà Nẵng).
- `iot_class: cloud_polling` — dữ liệu ở server nchmf, KHÔNG local-only.
- **SSL:** cert của `*.nchmf.gov.vn` hợp lệ (DigiCert/RapidSSL) → fetch verify SSL bình thường,
  KHÔNG dùng `ssl=False`. (Kiểm 2026-07: `curl` verify OK, HTTP 200.)

Thay thế cho giải pháp cũ (multiscrape + template weather YAML) — khi bản này chạy
ổn thì đã xoá 2 block đó khỏi `configuration.yaml`.

---

## 2. Cài đặt & nạp

- Thư mục: `/config/custom_components/nchmf/`
- **Config flow / UI**: Settings → Devices & Services → Add Integration → Vietnam Weather (NCHMF).
  Người dùng nhập **URL trang nchmf** (mặc định Đà Nẵng) + tên tuỳ chọn.
- Nạp qua config entry: `async_setup_entry` → tạo `NchmfCoordinator(hass, url)` →
  `async_forward_entry_setups(entry, ["weather","sensor"])`. Mỗi entry = một địa điểm,
  coordinator lưu ở `hass.data[DOMAIN][entry.entry_id]`.
- Platform dùng `async_setup_entry(hass, entry, async_add_entities)` (KHÔNG còn
  `async_setup_platform` + discovery).

Đổi/thêm địa điểm: Add Integration lại với URL tỉnh khác (đổi mã `w..` trên nchmf.gov.vn).
Selector/parser giữ nguyên vì mọi trang tỉnh dùng chung template HTML.

**Nếu từng chạy bản YAML cũ:** bỏ `nchmf:` khỏi `configuration.yaml`. unique_id & entity_id
theo `entry.entry_id` + `has_entity_name`, dashboard trỏ theo entity_id cũ có thể phải chỉnh.

---

## 3. Sơ đồ file

| File | Trách nhiệm |
|------|-------------|
| `__init__.py` | `async_setup_entry`/`async_unload_entry` + `NchmfCoordinator(hass, url)` + `async_fetch_raw`. Update mỗi 30'. |
| `config_flow.py` | `async_step_user` + `async_step_reconfigure`: form nhập URL → validate bằng `async_fetch_raw` + `parse_html`; title = tên địa điểm; unique_id = url. |
| `parser.py` | `parse_html(raw)` → dict có cấu trúc + `wind_bearing()`. **Toàn bộ logic scrape nằm ở đây.** |
| `weather.py` | Weather entity — condition + current + `async_forecast_daily` (9 ngày) + `native_wind_bearing` + device_info. |
| `sensor.py` | 4 sensor: nhiệt độ, độ ẩm, gió (hiện tại) + mảng nhiệt độ 10 ngày qua. Chung device_info. |
| `const.py` | `DOMAIN`, `CONF_URL`, `CONF_NAME`, `DEFAULT_URL`, `ATTRIBUTION`, `SCAN_INTERVAL_MINUTES`, `USER_AGENT`. |
| `manifest.json` | `config_flow: true`, `requirements: ["beautifulsoup4"]` (đã có sẵn trong HA core). |
| `strings.json` + `translations/` | Chuỗi config flow (en, vi). |

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
              wind_bearing:int|None, condition_text:str, condition:str|None, update_time:str},
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

entity_id nay do HA sinh từ tên device (entry.title) + tên entity (`has_entity_name`),
nên tuỳ tên địa điểm; ví dụ device "NCHMF Đà Nẵng":

- Weather entity — state = mã điều kiện; forecast daily 9 ngày; `native_wind_bearing` (độ).
  Card: `type: weather-forecast`, `forecast_type: daily`.
  Attributes phụ: `condition_text` (chữ Việt gốc), `wind_dir`, `location`, `update_time`.
- Sensor Nhiệt độ (°C, device_class temperature)
- Sensor Độ ẩm (%, humidity)
- Sensor Gió (m/s, wind_speed; attr `wind_dir`, `wind_bearing`)
- Sensor Nhiệt độ 10 ngày qua (attr `temperatures`, `times` cho apexcharts)

Tất cả gom trong 1 device, có `attribution` = nguồn nchmf.gov.vn.

---

## 8. Quyết định thiết kế & lý do (đừng "sửa" lại kẻo hỏng)

- **Verify SSL bình thường**: cert nchmf hợp lệ nên KHÔNG truyền `ssl=False` (tắt verify là
  hạ an toàn không cần thiết). Nếu về sau site để cert hết hạn/sai chuỗi mà fetch fail SSL,
  mới cân nhắc `ssl=False` như giải pháp tạm.
- **CÓ `device_info`**: có config entry nên gom 5 entity vào 1 device
  (`identifiers={(DOMAIN, entry.entry_id)}`, name=entry.title). `has_entity_name=True`:
  weather entity `_attr_name=None` (lấy tên device), sensor tên ngắn ("Nhiệt độ"...).
  (Bản YAML cũ KHÔNG có config entry nên phải bỏ device_info — nay dùng lại được.)
- **`native_wind_bearing`**: map hướng gió tiếng Việt → độ qua `parser.wind_bearing`
  ("Gió đông"→90, "Gió đông bắc"→45...). Tổ hợp 2 chữ phải xét trước 1 chữ.
- **`async_config_entry_first_refresh`**: fetch fail lần đầu → raise ConfigEntryNotReady
  (HA tự retry), thay cho `async_refresh` cũ.
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

Lấy `trang_that.html`: `curl <URL> -o trang_that.html` từ máy có mạng, rồi chạy đoạn trên.

---

## 10. Các kịch bản lỗi thường gặp -> soi ở đâu

| Triệu chứng | Nguyên nhân khả dĩ | Kiểm tra |
|---|---|---|
| Tất cả entity `unavailable` | fetch fail (timeout/site sập/cert hết hạn) | Log `custom_components.nchmf`; thử `curl URL` (verify) — nếu chỉ fail do SSL mới thử `curl -k URL` |
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

- **Config flow / UI**: ✅ ĐÃ LÀM (nhập URL, nhiều địa điểm, device_info).
  Có thể cải tiến thêm: dropdown danh sách tỉnh sẵn thay vì nhập URL thủ công
  (cần bảng mã `w..` cho 63 tỉnh — hiện chưa có, nên vẫn dùng URL cho chắc).
- **Reconfigure flow**: ✅ ĐÃ LÀM — `async_step_reconfigure` đổi URL/tên tại chỗ
  (`async_update_reload_and_abort`, cần HA ≥ 2024.11).
- **Brand icon**: ✅ ĐÃ CÓ, nhúng thẳng trong `custom_components/nchmf/brand/icon.png` (256)
  + `icon@2x.png` (512), sinh bởi `scripts/make_icon.py` (Pillow). Từ HA 2026.3 local brand
  images tự hiển thị (ưu tiên hơn CDN) — KHÔNG cần PR sang `home-assistant/brands`.
  HA < 2026.3 sẽ hiện icon chữ cái mặc định. Tên file hỗ trợ: `icon.png`, `dark_icon.png`,
  `logo.png`, `dark_logo.png` (+ `@2x`). Đơn sắc đọc rõ nền sáng/tối nên không cần `dark_`.
- **Forecast hourly**: không có sẵn trên trang tỉnh; chỉ có mảng 10 ngày QUA (quá khứ).
- **Icon thật của nchmf**: URL nằm ở `.icon-days-wt img` / `.icon-list-item img`
  (mã như `2301.png`, `1011.png`), có thể map sang entity_picture nếu muốn.
- **% mưa**: trang có ô `°%` nhưng bỏ trống -> không dùng được.

---

## 12. Phiên bản

- v1.0.0 — bản phát hành đầu. Config flow (UI), chọn URL/nhiều địa điểm, weather +
  3 sensor + past-temps sensor, device_info gom entity, `native_wind_bearing`,
  `attribution`, translations en/vi, brand icon nhúng trong component. Cấu trúc chuẩn HACS.
  Parser đã test end-to-end trên HTML thật (2026-07): current/today/night/forecast/
  past_temps đúng; map điều kiện đúng cho rainy/sunny/lightning-rainy; `wind_bearing`
  đã test unit (8 case). Chưa chạy config flow trên HA thật.
  (Tiền thân: một bản scrape cấu hình bằng YAML, cố định Đà Nẵng — đã thay thế.)
