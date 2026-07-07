# Vietnam Weather (NCHMF) — Home Assistant custom integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Integration lấy dữ liệu thời tiết của **Tổng cục Khí tượng Thuỷ văn** qua **API JSON chính thức**
(`khituongvietnam.gov.vn`) — chính xác **tới phường** theo toạ độ. **Thời tiết hiện tại** dùng
**quan trắc thời gian thực** của trạm gần nhất; **dự báo** theo giờ + 10 ngày. Cấu hình hoàn toàn
qua **giao diện UI** (chọn điểm trên bản đồ → chọn trạm gần nhất).

## Tính năng

- **Weather entity** — *hiện tại lấy từ quan trắc thật* (nhiệt độ/độ ẩm/gió/mưa/điều kiện của
  trạm gần nhất, khớp trang chủ KTTV) + **dự báo theo giờ** (trong ngày) và **10 ngày**;
  `clear-night` ban đêm; `native_wind_bearing` (°); xác suất mưa (PoP).
  Nếu quan trắc tạm lỗi → tự lùi về dự báo (không bao giờ trống).
- **Sensor**: nhiệt độ (°C), độ ẩm (%), tốc độ gió (m/s, kèm `wind_dir`/`wind_bearing`),
  **xác suất mưa** (%).
- **Chọn địa điểm trên bản đồ** — mặc định toạ độ nhà HA, rồi **chọn trạm/phường gần nhất**
  trong danh sách kèm khoảng cách (vd *Cẩm Lệ 2.2 km*, *Hòa Xuân 2.4 km*).
- **Nhiều địa điểm**, mỗi cái là 1 device; **Reconfigure** đổi vị trí/tên; **Options** đổi chu kỳ cập nhật.
- **Diagnostics** + **Repairs** (cảnh báo khi API đổi cấu trúc). Tên entity đa ngôn ngữ (en/vi).
- **Tự chuyển đổi** entry bản cũ (scrape URL) sang toạ độ nhà HA khi cập nhật.

## Cài đặt qua HACS

1. HACS → **Integrations** → menu (⋮) góc phải → **Custom repositories**.
2. Thêm repo `https://github.com/MinhPC/nchmf`, category **Integration**.
3. Tìm **Vietnam Weather (NCHMF)** → **Download** → **Restart** Home Assistant.

> Đã cài rồi mà chưa thấy bản mới: mở repo trong HACS → **⋮ → Update information** để HACS
> tải lại thông tin release, rồi bấm **Update**.

### Cài thủ công

Copy thư mục `custom_components/nchmf/` vào `/config/custom_components/` rồi Restart.

## Cấu hình

**Settings → Devices & Services → Add Integration → Vietnam Weather (NCHMF).**

1. **Bước 1 — Bản đồ:** chọn/di chuyển điểm (mặc định là vị trí nhà Home Assistant).
2. **Bước 2 — Chọn trạm:** danh sách các trạm/phường gần điểm nhất, kèm khoảng cách — chọn 1.
   Toạ độ trạm được lưu để dự báo luôn trúng đúng phường đó.

Thêm **nhiều địa điểm** bằng cách Add Integration nhiều lần — mỗi cái là một thiết bị riêng.

- Đổi vị trí/tên sau này: integration → **⋮ → Reconfigure** (mở lại bản đồ + chọn trạm).
- Đổi **chu kỳ cập nhật** (mặc định 30′): integration → **Configure** (Options).

> **Nâng cấp từ bản < 2.0 (cấu hình bằng URL/YAML):** entry cũ tự chuyển sang toạ độ nhà HA;
> vào **Reconfigure** để chọn đúng trạm/phường trên bản đồ.

## Ghi chú kỹ thuật

- `iot_class: cloud_polling`, mặc định cập nhật mỗi 30 phút. Không cần thư viện ngoài (không bs4).
- Nguồn: `WeatherApiService/api/forecast` (dự báo) + `api/wetherlocal` (quan trắc), verify SSL bình thường.
- Quan trắc "hiện tại" là của **trạm gần nhất** (vd mọi phường Đà Nẵng → trạm Hải Châu) — đúng như
  cách trang chủ KTTV hiển thị.
- Chi tiết kiến trúc & xử lý sự cố: xem [`CLAUDE.md`](CLAUDE.md).

## Icon

Icon nhúng thẳng trong component tại [`custom_components/nchmf/brand/`](custom_components/nchmf/brand)
(`icon.png` 256×256 + `icon@2x.png` 512×512). Từ **Home Assistant 2026.3**, local brand images tự
hiển thị và ưu tiên hơn CDN. Sinh lại: `python scripts/make_icon.py` (cần Pillow).

## License

MIT
