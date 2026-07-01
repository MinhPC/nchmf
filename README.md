# Vietnam Weather (NCHMF) — Home Assistant custom integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Integration lấy dữ liệu thời tiết từ **Trung tâm Dự báo KTTV quốc gia (nchmf.gov.vn)**
bằng cách scrape HTML (site không có API JSON). Cấu hình qua **giao diện UI**, chọn được
nhiều địa điểm; mặc định gợi ý **Hải Châu, Đà Nẵng**.

## Tính năng

- `weather.nchmf_da_nang` — điều kiện hiện tại + dự báo daily (~9 ngày).
- `sensor.nchmf_da_nang_nhiet_do` — nhiệt độ (°C).
- `sensor.nchmf_da_nang_do_am` — độ ẩm (%).
- `sensor.nchmf_da_nang_gio` — tốc độ gió (m/s), kèm `wind_dir`.
- `sensor.nchmf_da_nang_nhiet_do_10_ngay_qua` — mảng nhiệt độ 10 ngày qua (attr `temperatures`, `times`) để vẽ chart apexcharts.

## Cài đặt qua HACS

1. HACS → **Integrations** → menu (⋮) góc phải → **Custom repositories**.
2. Thêm repo `https://github.com/MinhPC/nchmf`, category **Integration**.
3. Tìm **Vietnam Weather (NCHMF)** → **Download**.
4. **Restart** Home Assistant.

### Cài thủ công

Copy thư mục `custom_components/nchmf/` vào `/config/custom_components/` rồi Restart.

## Cấu hình

**Settings → Devices & Services → Add Integration → Vietnam Weather (NCHMF).**

- Nhập **URL trang nchmf** của tỉnh/thành muốn theo dõi (mặc định là Đà Nẵng).
  Lấy URL trên [nchmf.gov.vn](https://www.nchmf.gov.vn) — chọn tỉnh, copy URL (đổi mã `w..`).
- Đặt **Tên** (tuỳ chọn); để trống sẽ tự lấy tên địa điểm từ trang.
- Integration sẽ **fetch thử + parse ngay lúc thêm**; nếu URL sai/không parse được sẽ báo lỗi.

Thêm **nhiều địa điểm** bằng cách Add Integration nhiều lần với URL khác nhau — mỗi cái
là một thiết bị riêng, gom đủ 5 entity.

Đổi URL/tên sau này: vào integration → **⋮ → Reconfigure** (không cần xoá tạo lại).

> **Nếu trước đây bạn dùng bản cấu hình bằng YAML:** integration này cấu hình hoàn toàn
> qua UI. Xoá dòng `nchmf:` khỏi `configuration.yaml`, restart, rồi thêm lại qua UI như trên.

## Ghi chú kỹ thuật

- `iot_class: cloud_polling`, cập nhật mỗi 30 phút.
- Fetch verify SSL bình thường (cert `nchmf.gov.vn` hợp lệ).
- Chi tiết kiến trúc & cách sửa selector khi nchmf đổi giao diện: xem [`CLAUDE.md`](CLAUDE.md).

## Icon

Icon được **nhúng thẳng trong component** tại [`custom_components/nchmf/brand/`](custom_components/nchmf/brand)
(`icon.png` 256×256 + `icon@2x.png` 512×512). Từ **Home Assistant 2026.3**, local brand
images tự hiển thị và được ưu tiên hơn CDN — không cần nộp PR sang `home-assistant/brands`.

Sinh lại icon: `python scripts/make_icon.py` (cần Pillow).

> HA < 2026.3 sẽ hiện icon chữ cái mặc định (không dùng được local brand). Nếu cần hỗ trợ
> bản HA cũ, có thể nộp thêm icon vào repo `home-assistant/brands` (thư mục legacy `custom_integrations/`).

## License

MIT
