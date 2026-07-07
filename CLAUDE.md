# CLAUDE.md — Custom component `nchmf`

Tài liệu ngữ cảnh cho việc sửa lỗi / nâng cấp về sau. Đưa nguyên file này vào đầu
phiên làm việc là đủ context, không cần giải thích lại từ đầu.

---

## 1. Mục đích & nguồn dữ liệu

Custom component lấy dữ liệu thời tiết của **Tổng cục Khí tượng Thuỷ văn** qua
**API JSON chính thức** — dự báo **theo lat/lon, tự resolve về phường/trạm gần nhất**.

- **Forecast:** `https://khituongvietnam.gov.vn/WeatherApiService/api/forecast?lat={lat}&lon={lon}`
  Trả `application/json`: `Station` (tên phường, tỉnh, toạ độ trạm) + `Forecasts`
  (4 điểm trong ngày giờ 1/7/13/19 + 10 bản ghi ngày, `ForecastHour==99`).
- **Quan trắc thời gian thực (v2.2.0):** `.../WeatherApiService/api/wetherlocal?Lat={lat}&Lon={lon}`
  (chú ý `Lat`/`Lon` VIẾT HOA). Trả JSON quan trắc của **TRẠM GẦN NHẤT** (không phải phường —
  vd mọi phường Đà Nẵng ra trạm "Hải Châu"): `Current_Temp`, `Humidity`, `Rainfall`,
  `Wind` ("Gió <hướng> - tốc độ: N m/s"), `Weather_Text`, `Icon`, `Name`, `TimeObservation` (giờ).
  Đây là nguồn cho "hiện tại" (khớp popup trang chủ `bccp/kttv.html`). Chính chủ site cũng
  hiển thị obs trạm gần nhất cho điểm phường.
- `iot_class: cloud_polling` — dữ liệu ở server KTTV, KHÔNG local-only.
- **SSL:** cert `khituongvietnam.gov.vn` hợp lệ → verify SSL bình thường, KHÔNG `ssl=False`.
- **KHÔNG cần beautifulsoup4 nữa** (`requirements: []`). JSON thay cho scrape HTML.

> Lịch sử: bản < 2.0.0 **scrape HTML** trang tỉnh của nchmf.gov.vn (mã `w..`, cố định theo
> tỉnh, selector CSS dễ vỡ). 2.0.0 thay hẳn bằng API JSON này — chính xác tới **phường**,
> có thêm **forecast theo giờ** và **xác suất mưa (PoP)**. Trước đó nữa là bản YAML
> (multiscrape + template), cố định Đà Nẵng — đã bỏ.

---

## 2. Cài đặt & nạp

- Thư mục: `/config/custom_components/nchmf/`
- **Config flow / UI** (2 bước, từ v2.1.0): Settings → Devices & Services → Add Integration.
  **Bước 1** `async_step_user`/`reconfigure`: **bản đồ** (`LocationSelector`), mặc định
  toạ độ nhà HA (`hass.config.latitude/longitude`) + tên tuỳ chọn.
  **Bước 2** `async_step_station`: dropdown **các trạm/phường gần nhất** (tên + khoảng cách),
  người dùng chọn 1 → lưu **toạ độ trạm đó** (ghim đúng phường). Title mặc định = tên trạm.
  Dò trạm bằng `async_discover_stations` (mục 8).
- Nạp qua config entry: `async_setup_entry` → `NchmfCoordinator(hass, entry)` →
  `async_forward_entry_setups(entry, ["weather","sensor"])`. Mỗi entry = một địa điểm,
  coordinator lưu ở `hass.data[DOMAIN][entry.entry_id]`.
- **Đổi/thêm địa điểm**: Add Integration lại (điểm bản đồ khác), hoặc
  Reconfigure để di chuyển điểm. `unique_id = "{lat},{lon}"` (làm tròn 5 chữ số).

**Nếu từng chạy bản < 2.0.0 (scrape URL):** `CONF_URL` không còn. `async_migrate_entry`
(trong `__init__.py`) **tự chuyển entry v1 → v2**: không suy được toạ độ từ URL tỉnh cũ nên
gán **toạ độ nhà HA** làm mặc định (+ log cảnh báo) → entry cũ TỰ nạp được, không crash.
Người dùng chỉ cần **Reconfigure (bản đồ)** để chỉnh đúng phường. `ConfigFlow.VERSION = 2`.

---

## 3. Sơ đồ file

| File | Trách nhiệm |
|------|-------------|
| `__init__.py` | `async_setup_entry`/`async_unload_entry` + `async_migrate_entry` + `NchmfCoordinator` + `async_fetch_json` + `async_fetch_obs` (quan trắc) + `async_discover_stations` + `_check_health`. Gọi forecast+obs SONG SONG, ghép `current`. |
| `config_flow.py` | 2 bước: `_async_center_step` (bản đồ, dùng chung user/reconfigure) → `async_step_station` (dropdown trạm gần) + `NchmfOptionsFlow` (scan interval). |
| `parser.py` | `transform`, `map_condition`, `wind_direction(deg)`, `pick_current`, `parse_obs` (quan trắc), `wind_bearing_vn` + `haversine_km`/`sample_points`/`rank_stations`. **Hàm THUẦN, test ngoài HA.** |
| `weather.py` | Weather entity — condition (+ `clear-night`) + current + forecast **daily & hourly** (hourly LUÔN trả đủ 4 mốc, không lọc → tab Hourly không rỗng/không spinner) + `today_points` + `native_wind_bearing` + device_info. |
| `sensor.py` | 9 sensor: nhiệt độ/độ ẩm/gió/**lượng mưa** (tên theo device_class) + **xác suất mưa/mây/hướng gió/điều kiện** (`translation_key`) + **trạm quan trắc** (diagnostic). Chung device_info. |
| `binary_sensor.py` | 1 binary_sensor **cảnh báo** (`warning`, device_class `safety`): on khi `current["warning"]` (Weather_War) khác rỗng. Chung device_info. |
| `diagnostics.py` | `async_get_config_entry_diagnostics` — xuất coordinator.data + entry (lat/lon). |
| `const.py` | `DOMAIN`, `CONF_LAT/LON/NAME/SCAN_INTERVAL`, `API_URL`, `DEFAULT_LAT/LON`, `ICON_BASE`, `ATTRIBUTION`, `*_SCAN_INTERVAL_MINUTES`, `ISSUE_NO_DATA`, `USER_AGENT`. |
| `manifest.json` | `config_flow: true`, `integration_type: service`, `requirements: []` (không còn bs4), `version: 2.5.0`. |
| `strings.json` + `translations/` | config flow, options, entity (precipitation_probability), issues (no_data) — en/vi. |

Kiến trúc: 1 `DataUpdateCoordinator` gọi API + `transform` 1 lần, mọi entity là
`CoordinatorEntity` đọc chung `coordinator.data`. `transform` là JSON thuần → chạy
inline trong event loop được (không cần executor như bs4 trước đây); chỉ dùng
`dt_util.now().hour` để chọn `current`.

---

## 4. Cấu trúc JSON mà `transform` phụ thuộc (PHẦN DỄ VỠ NHẤT)

Nếu KTTV đổi schema → entity về None/unavailable. Ổn định hơn HTML nhiều, nhưng vẫn
là các khoá cần theo dõi (`parser.transform`):

```
Station.Name          -> tên phường  ("Phường Hòa Xuân")
Station.ProvinceName  -> tỉnh/thành   ("Thành phố Đà Nẵng")
Station.StationID / StationLat / StationLon
Forecasts[]           -> mỗi phần tử:
  ForecastDate  "2026-07-07T00:00:00"  (chỉ phần ngày có ý nghĩa)
  ForecastHour  1 | 7 | 13 | 19        -> điểm TRONG NGÀY (dùng T2m)
                99                      -> bản ghi THEO NGÀY (dùng Tmax/Tmin)  [= DAILY_HOUR]
  T2m           nhiệt độ điểm giờ (°C)         (null khi ForecastHour==99)
  Tmax / Tmin   cao/thấp trong ngày            (null khi ForecastHour!=99)
  Speed         tốc độ gió (m/s)
  Direction     HƯỚNG GIÓ THEO ĐỘ (0-360)  -> wind_bearing trực tiếp, wind_direction() ra nhãn VN
  PoP           xác suất mưa (%)
  Prec          lượng mưa (mm)
  RH            độ ẩm (%)
  Cloud         độ mây (0-1)
  Weather_Text  mô tả VN  ("Nhiều mây, có mưa nhỏ")  -> map_condition()
  Icon          đường dẫn ảnh ("Upload/WeatherSymbol/...")  -> ICON_BASE + Icon
```

Điểm tinh:
- `Direction` đã là **độ** → `native_wind_bearing` khỏi map chữ (khác bản HTML cũ).
- `wind_direction(deg)` chỉ để hiển thị nhãn VN (Bắc/Đông bắc/…) trong attr `wind_dir`.
- Điểm giờ có `T2m`, `Tmax/Tmin=null`; bản ngày (99) ngược lại → `transform` tách 2 nhánh.
- `map_condition("...không mưa")` phải KHÔNG ra rainy (guard `"không mưa"`).

---

## 5. Schema `coordinator.data` (output của `transform` + `current` gắn ở coordinator)

```python
{
  "location": str,           # Station.Name (phường)
  "province": str,           # Station.ProvinceName
  "station_id": str,
  "lat": float, "lon": float,
  "hourly": [ {datetime:isostr, hour:int, temp:int, humidity:int, wind_speed:float,
               wind_bearing:float, wind_dir:str, pop:int, precipitation:float,
               cloud:float, condition:str, condition_text:str, icon:str|None}, ... ],  # 4 điểm
  "daily":  [ {datetime:isostr, temperature:int(Tmax), templow:int(Tmin), ...cùng key phụ}, ... ], # 10 ngày
  # gắn ở coordinator._async_update_data (cần dt_util.now()):
  "current": {...},          # = {**điểm hourly gần giờ, **{k:v của parse_obs nếu v!=None}} khi có obs;
                             #   obs đè temp/humidity/wind/condition/precipitation NHƯNG chỉ field
                             #   có giá trị (field obs None KHÔNG xoá forecast tốt), GIỮ pop từ forecast.
                             #   parse_obs thêm: obs_station, obs_time. {} nếu cả hai rỗng.
  "current_source": str,     # "observation" (có quan trắc) | "forecast" (fallback)
  "update_time": str,        # giờ QUAN TRẮC thật (obs_time trong ngày) nếu có, else datetime điểm dự báo
}
```

`parse_obs` (từ api/wetherlocal): trả {} nếu thiếu `Current_Temp` -> coordinator fallback
sang `pick_current` (điểm dự báo gần giờ). Obs fail KHÔNG làm hỏng update (gather
`return_exceptions=True`, forecast bắt buộc, obs tuỳ chọn).
```
```

Mọi property entity guard `(self.coordinator.data or {})` → data None (fetch fail)
không crash, entity chỉ `unavailable`.

---

## 6. Map điều kiện tiếng Việt -> mã HA  (`parser.map_condition`) — GIỮ NGUYÊN từ bản HTML

Thứ tự ưu tiên (khớp keyword đầu tiên thắng); `"không mưa"` chặn nhánh rainy:

| Keyword | Mã HA |
|---|---|
| có `mưa` + `dông` | `lightning-rainy` |
| có `mưa` (và KHÔNG `không mưa`) | `rainy` |
| `sương mù` / `mù` | `fog` |
| `nhiều mây` | `cloudy` |
| `ít mây` / `nắng` | `sunny` |
| `mây` (còn lại) | `partlycloudy` |
| mặc định | `partlycloudy` |

Mã HA hợp lệ: `clear-night, cloudy, fog, hail, lightning, lightning-rainy, partlycloudy,
pouring, rainy, snowy, snowy-rainy, sunny, windy, windy-variant, exceptional`.

---

## 7. Entity tạo ra

entity_id do HA sinh từ tên device (entry.title = tên phường) + tên entity. 1 device gom hết:

- **Weather entity** — state = mã điều kiện (+ `clear-night` khi sunny & ban đêm theo `sun.sun`).
  `FORECAST_DAILY | FORECAST_HOURLY`: daily 10 ngày, hourly 4 mốc (1/7/13/19h HÔM NAY).
  `async_forecast_hourly` LUÔN trả đủ 4 mốc (kể cả mốc đã qua, KHÔNG lọc) → forecast
  không bao giờ rỗng → tab Hourly không quay vòng (spinner chỉ xảy ra khi forecast rỗng).
  Lỗi 2.6.0/2.7.0: `_future_only` lọc hết mốc cuối ngày → rỗng → spinner (đã bỏ lọc ở 2.8.0).
  Forecast có `native_temperature/templow, humidity, native_wind_speed, wind_bearing,
  precipitation_probability, native_precipitation`. `native_wind_bearing` = Direction (độ).
  Attr phụ: `location, province, condition_text, wind_dir, wind_speed_ms, precipitation_probability,
  precipitation, cloud, icon_url (icon KTTV hiện tại), warning, update_time, current_source,
  observation_station/time`, và `today_points` (4 mốc 1/7/13/19h hôm nay: hour/temp/condition/
  pop/icon — `_unrecorded_attributes`) để CARD tự render "diễn biến hôm nay" mà KHÔNG đẩy vào
  tab Hourly của HA (tránh spinner khi mốc đã qua).
  Card: `type: weather-forecast`, `forecast_type: daily` hoặc `hourly`.
  > **Custom card ĐÃ BỎ** (v2.6.0). Trước đây weather phơi thêm 2 mảng
  > `forecast_daily`/`forecast_hourly` (kèm icon KTTV, `_unrecorded_attributes`) để nuôi
  > `www/nchmf-weather-card.js` — card bị gỡ (hiển thị xấu) nên 2 mảng + helper `_forecast_attr`
  > đã xoá; forecast giờ chỉ qua service chuẩn `async_forecast_*`. `wind_speed_ms`/`icon_url`/`cloud`
  > GIỮ lại (nhẹ, dùng cho template/card mặc định).
- Sensor Nhiệt độ (°C, temperature) — current.temp
- Sensor Độ ẩm (%, humidity)
- Sensor Gió (m/s, wind_speed; attr `wind_dir`, `wind_bearing`)
- Sensor **Xác suất mưa** (%, `translation_key: precipitation_probability`; attr `precipitation`)
- Sensor **Lượng mưa** (mm, device_class precipitation) — current.precipitation
- Sensor **Lượng mây** (%, `translation_key: cloud`) — Cloud (0..1) ×100
- Sensor **Hướng gió** (nhãn VN, `translation_key: wind_direction`; attr `wind_bearing` độ)
- Sensor **Điều kiện** (mô tả VN, `translation_key: condition`; attr `condition` mã HA, `icon_url`)
- Sensor **Trạm quan trắc** (diagnostic, `translation_key: observation_station`; attr
  `observation_time`, `current_source`) — tên trạm gần nhất nguồn 'hiện tại'
- Binary sensor **Cảnh báo** (device_class `safety`, `translation_key: warning`; on khi có
  cảnh báo `Weather_War`; attr `warning` = nội dung cảnh báo)

Tất cả có `attribution` = KTTV. (Sensor "10 ngày qua" của bản HTML đã BỎ — API không có
chuỗi quá khứ; thay bằng sensor xác suất mưa.)

---

## 8. Quyết định thiết kế & lý do (đừng "sửa" lại kẻo hỏng)

- **API JSON thay scrape HTML**: chính xác theo phường + có hourly + PoP + ổn định hơn.
  Bỏ `beautifulsoup4` khỏi requirements.
- **Verify SSL bình thường**: cert khituongvietnam.gov.vn hợp lệ → KHÔNG `ssl=False`.
- **`current` = điểm gần giờ hiện tại** (`pick_current(hourly, dt_util.now().hour)`): API
  không có "quan trắc hiện tại", chỉ 4 điểm dự báo trong ngày → chọn cái gần giờ nhất.
  Tính ở coordinator (nơi có `dt_util.now()`), KHÔNG trong `transform` (giữ `transform` thuần/test được).
- **`transform` là hàm thuần**: chỉ phụ thuộc `dt_util.start_of_local_day`. Chạy inline
  (JSON nhẹ), không cần executor như bs4 trước đây.
- **Chọn trạm gần (v2.1.0)**: API `/api/forecast` chỉ trả **trạm gần nhất** mỗi lat/lon,
  KHÔNG có endpoint danh sách trạm (đã dò: `/api/stations`… đều 404). Nên
  `async_discover_stations` **quét đồng thời** (`asyncio.gather`) 17 điểm quanh tâm
  (`sample_points`: tâm + 2 vòng 2km/4km × 8 hướng), khử trùng theo `StationID`, xếp theo
  `haversine_km` (`rank_stations`, top 5). Ở Đà Nẵng nội thành ra ~5 phường lân cận.
  Lưu **toạ độ TRẠM** người dùng chọn (không phải điểm bản đồ) → fetch sau luôn trúng trạm đó.
  Tên trạm API đôi khi kèm `\n` → `.strip()`.
- **`native_wind_bearing` = Direction (độ) trực tiếp** — không còn map chữ→độ như bản HTML.
- **CÓ `device_info`**: gom 5 entity 1 device (`identifiers={(DOMAIN, entry.entry_id)}`,
  name=entry.title). `has_entity_name=True`: weather `_attr_name=None`, sensor tên ngắn.
- **`async_config_entry_first_refresh`**: fetch fail lần đầu → ConfigEntryNotReady (HA retry).
- **`_handle_coordinator_update`** (trong `weather.py`): gọi `super()` (ghi state) +
  `self.hass.async_create_task(self.async_update_listeners(None))` để đẩy forecast tới card.
  LƯU Ý: `WeatherEntity.async_update_listeners` là **COROUTINE** VÀ **bắt buộc `forecast_types`**
  (không default). `_handle_coordinator_update` là `@callback` không await được → phải bọc
  `async_create_task` + truyền `None`. Gọi thiếu arg = `TypeError`; không await = coroutine bị bỏ.
- **`asyncio.timeout(30)`**: cần Python 3.11+. HA cũ báo lỗi dòng này → đổi `async_timeout`.
- **`unique_id = "{lat},{lon}"` làm tròn 5 chữ số**: ~1m, tránh trùng entry cùng điểm.

---

## 9. Cách test `transform` NGOÀI Home Assistant (không cần HA chạy)

`parser.py` chỉ phụ thuộc `dt_util` + import `.const`. Stub `dt_util`, nạp package tối giản
(`nchmf.const` + `nchmf.parser`) rồi gọi `transform`:

```python
import sys, types, json, importlib.util, os
from datetime import timezone, timedelta
dtm = types.ModuleType("homeassistant.util.dt")
TZ = timezone(timedelta(hours=7))
dtm.start_of_local_day = lambda d: d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=TZ)
sys.modules["homeassistant"] = types.ModuleType("homeassistant")
sys.modules["homeassistant.util"] = types.ModuleType("homeassistant.util")
sys.modules["homeassistant.util.dt"] = dtm
COMP = "custom_components/nchmf"
pkg = types.ModuleType("nchmf"); pkg.__path__ = [COMP]; sys.modules["nchmf"] = pkg
for mod in ("const", "parser"):
    spec = importlib.util.spec_from_file_location(f"nchmf.{mod}", os.path.join(COMP, f"{mod}.py"))
    m = importlib.util.module_from_spec(spec); sys.modules[f"nchmf.{mod}"] = m; spec.loader.exec_module(m)
p = sys.modules["nchmf.parser"]
payload = json.load(open("forecast.json", encoding="utf-8"))
print(p.transform(payload))
print(p.pick_current(p.transform(payload)["hourly"], 14))
```

Lấy JSON thật: `curl "https://khituongvietnam.gov.vn/WeatherApiService/api/forecast?lat=15.995433&lon=108.21152" -o forecast.json`

---

## 10. Các kịch bản lỗi thường gặp -> soi ở đâu

| Triệu chứng | Nguyên nhân khả dĩ | Kiểm tra |
|---|---|---|
| Tất cả entity `unavailable` | API fail (timeout/sập/cert) | Log `custom_components.nchmf`; thử `curl` endpoint |
| Entity `unknown`, không lỗi | schema JSON đổi khoá | So JSON thật với mục 4; sửa khoá trong `transform` |
| `current` rỗng (temp None) | `Forecasts` không có điểm giờ (chỉ 99) | Kiểm `hourly` trong diagnostics; `pick_current` trả `{}` |
| Forecast card **quay vòng mãi** | `daily`/`hourly` rỗng | Kiểm `transform` tách nhánh `ForecastHour==99` đúng chưa |
| Forecast không refresh (30′) | `async_update_listeners` gọi sai | Kiểm `_handle_coordinator_update` (mục 8) |
| Hướng gió sai nhãn | `wind_direction` lệch cung 45° | Direction là độ; nhãn chỉ để hiển thị |
| Icon điều kiện sai | `map_condition` thiếu keyword | Thêm nhánh (mục 6) |
| Entry cũ (bản URL) nạp ở nhà HA, sai phường | migrate gán toạ độ nhà HA | Reconfigure (bản đồ) chọn đúng phường (mục 2) |
| Lỗi dòng `asyncio.timeout` | HA/Python quá cũ | Đổi sang `async_timeout` (mục 8) |

Bật log:
```yaml
logger:
  logs:
    custom_components.nchmf: debug
```

---

## 11. Ý tưởng nâng cấp (chưa làm)

- **Icon thật của KTTV**: `current["icon"]` / forecast `icon` đã có URL đầy đủ
  (`ICON_BASE + Icon`) — có thể map sang `entity_picture` nếu muốn hình gốc thay icon HA.
- **Nhiệt độ/độ ẩm theo giờ ra sensor riêng**: hiện chỉ có `current` + forecast; nếu muốn
  4 điểm giờ thành lịch sử, tự làm template/statistics.
- **Cảnh báo (`Weather_War`)**: ĐÃ LÀM ở v2.4.0 — `binary_sensor.py` (device_class safety).
- **Brand icon**: đã có trong `brand/` (xem lịch sử); từ HA 2026.3 local brand tự hiển thị.

---

## 12. Phiên bản

- **v2.8.1** — **`today_points` đủ field cho card**. Thêm `humidity`, `wind_speed` (m/s thô),
  `wind_dir` (nhãn VN), `wind_bearing` (độ), `cloud` vào mỗi mốc của `today_points` (trước chỉ
  có temp/condition/pop/icon) → card "diễn biến hôm nay" hiện được độ ẩm/xác suất mưa/hướng+tốc
  độ gió cho từng mốc 1/7/13/19h. Chỉ mở rộng attribute, không đổi gì khác.
- **v2.8.0** — **Bật lại tab Hourly (4 mốc, không spinner) + attribute `today_points`**.
  Nhận ra spinner của tab Hourly chỉ do forecast RỖNG (lỗi 2.6.0/2.7.0: `_future_only` lọc hết
  mốc quá khứ cuối ngày → rỗng). Sửa: `async_forecast_hourly` **LUÔN trả đủ 4 mốc 1/7/13/19h**
  (không lọc) → không bao giờ rỗng → tab Hourly hiển thị 4 cột, hết quay vòng. Bật lại
  `FORECAST_HOURLY`. Thêm attribute nhẹ `today_points` (`_unrecorded_attributes`) để card TỰ
  render "diễn biến hôm nay" (icon KTTV, đánh dấu mốc đã qua) — dùng song song với tab Hourly.
  Vẫn thuần KTTV, không đổi nguồn.
- **v2.7.0** — **Bỏ dự báo theo GIỜ (FORECAST_HOURLY)**. API KTTV chỉ trả 4 điểm cố định
  1/7/13/19h của HÔM NAY (không phải hourly thật) → chiều/tối mọi mốc đều quá khứ → tab
  Hourly trong more-info **quay vòng mãi** (frontend spinner khi forecast toàn giờ đã qua).
  Weather entity giờ chỉ quảng bá `FORECAST_DAILY` (10 ngày, đủ dữ liệu). Xoá
  `async_forecast_hourly` + `_future_only` (thêm ở 2.6.0). `hourly` VẪN được `transform`
  tạo và dùng nội bộ cho `pick_current`/`current` — chỉ không phơi ra forecast service nữa.
- **v2.6.0** — **Bỏ custom card + 3 fix nhỏ**. (1) Gỡ hẳn ý tưởng `www/nchmf-weather-card.js`
  (hiển thị xấu, chưa từng commit) → xoá 2 attr nặng `forecast_daily`/`forecast_hourly` +
  helper `_forecast_attr` + `_unrecorded_attributes` khỏi `weather.py` (forecast vẫn qua service
  chuẩn `async_forecast_*`); GIỮ `wind_speed_ms`/`icon_url`/`cloud`/`warning` (nhẹ, dùng được).
  (2) `map_condition`: guard `"mùa"` để `"mù"` không bắt nhầm (vd "chuyển mùa") ra fog.
  (3) `async_forecast_hourly`: bỏ điểm giờ ĐÃ QUA (`_future_only`, fallback giữ nguyên nếu lọc
  hết cuối ngày → card không quay vòng). (4) Sensor **Lượng mưa**: `state_class` MEASUREMENT →
  TOTAL (đúng ngữ nghĩa lượng mưa tích luỹ cho long-term statistics).
- **v2.5.0** — **Thêm 5 sensor** để phơi toàn bộ dữ liệu 'hiện tại' ra entity riêng (không
  chỉ trong custom card): **Lượng mưa** (device_class precipitation), **Lượng mây** (Cloud×100 %),
  **Hướng gió** (nhãn VN + attr độ), **Điều kiện** (mô tả VN + attr mã HA/icon KTTV), và
  **Trạm quan trắc** (diagnostic). Tổng sensor: 4 → 9. Tên qua `translation_key` (en/vi).
- **v2.4.0** — **binary_sensor cảnh báo + 2 fix quan trắc + integration_type**.
  (1) `binary_sensor.py`: entity **Cảnh báo** (device_class `safety`, on khi `Weather_War`
  khác rỗng) → automation bắn thông báo. (2) **Fix merge quan trắc**: chỉ đè field CÓ giá trị
  của obs lên forecast (`{k:v for … if v is not None}`) — trước đây obs field `None` (gió "lặng"
  không parse ra tốc độ, Weather_Text rỗng) **xoá mất** giá trị forecast hợp lệ → gió/điều kiện
  hiện tại về None. (3) **Fix `update_time`**: khi nguồn là quan trắc, dùng **giờ quan trắc thật**
  (`obs_time` trong ngày) thay vì datetime điểm dự báo. (4) `manifest`: thêm `integration_type: service`.
- **v2.3.2** — thêm lượng mưa (`precipitation`/`Prec`) vào mảng `forecast_daily`/`forecast_hourly`.
- **v2.3.1** — thêm attr `wind_speed_ms` (tốc độ gió thô m/s cho hiện tại). HA quy đổi
  `native_wind_speed` sang đơn vị hệ thống (thường km/h) ở attr `wind_speed` → dùng
  `wind_speed_ms` trong custom card để khớp m/s như trang chủ. (Forecast arrays vốn đã là m/s thô.)
- **v2.3.0** — **Phơi thêm dữ liệu cho custom card**: weather attr thêm `cloud`, `icon_url`
  (icon KTTV thật của hiện tại), `warning` (Weather_War), và `forecast_daily`/`forecast_hourly`
  (mảng rút gọn KÈM icon KTTV + PoP/độ ẩm/gió — `_unrecorded_attributes`). parser thêm
  `warning` vào mỗi record. Không đổi nguồn/entity, chỉ bổ sung attribute.
- **v2.2.0** — **'Hiện tại' = QUAN TRẮC thật** (api/wetherlocal, trạm gần nhất) thay vì điểm
  dự báo 6-tiếng. Gọi forecast+obs song song, ghép current (obs đè, giữ pop). Sửa bug
  `map_condition`: "Mây thay đổi" -> partlycloudy (không còn "Nắng đẹp" sai). `wind_bearing_vn`
  parse chuỗi gió VN 16 hướng. Attr weather thêm current_source/observation_station/time.
  Test live (2026-07): Hòa Xuân ra 27°C "Có mưa" ẩm 90% gió nam đông nam 1m/s — khớp trang chủ.
- **v2.1.0** — **Config flow 2 bước + chọn trạm gần**: bước 1 bản đồ (mặc định nhà HA),
  bước 2 dropdown các trạm/phường gần nhất kèm khoảng cách (Cẩm Lệ, Hòa Xuân…). API không
  có list trạm → `async_discover_stations` quét 17 điểm quanh tâm (song song) rồi
  `rank_stations`. Lưu toạ độ trạm đã chọn (ghim đúng phường). `.strip()` tên trạm.
  Test live (2026-07): quanh nhà (16.0097,108.2285) ra Cẩm Lệ 2.2km / Hòa Xuân 2.4km /
  Hòa Cường 3.3km / Ngũ Hành Sơn 3.5km.
- **v2.0.0** — **ĐỔI NGUỒN sang API JSON KTTV** (`khituongvietnam.gov.vn/WeatherApiService`),
  chính xác **theo phường** qua lat/lon. Config flow dùng **bản đồ** (`LocationSelector`,
  mặc định nhà HA). Thêm **forecast theo giờ** (4 điểm) + **xác suất mưa (PoP)**;
  `native_wind_bearing` lấy thẳng `Direction` (độ). Bỏ scrape HTML + `beautifulsoup4`
  + sensor "10 ngày qua" (nguồn không có). `transform` thuần, test end-to-end trên JSON
  thật (2026-07): Đà Nẵng/Hà Nội/TpHCM đều ra phường + 4 hourly + 10 daily + map điều kiện đúng.
  Chưa chạy config flow trên HA thật. ConfigFlow.VERSION=2 + `async_migrate_entry`
  (entry bản URL cũ tự chuyển sang toạ độ nhà HA, Reconfigure để chỉnh phường).
- v1.1.0 — (bản HTML) dropdown tỉnh, clear-night, options flow, diagnostics, repairs.
- v1.0.1 — (bản HTML) fix forecast card quay vòng mãi; `async_update_listeners` coroutine+arg.
- v1.0.0 — (bản HTML) phát hành đầu: scrape nchmf.gov.vn, config flow URL, weather + sensor.
  (Tiền thân: bản YAML multiscrape cố định Đà Nẵng.)
