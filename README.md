# NCHMF Weather (Đà Nẵng) — Home Assistant custom integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Integration lấy dữ liệu thời tiết từ **Trung tâm Dự báo KTTV quốc gia (nchmf.gov.vn)**
bằng cách scrape HTML (site không có API JSON). Mặc định cố định **Hải Châu, Đà Nẵng**.

## Tính năng

- `weather.nchmf_da_nang` — điều kiện hiện tại + dự báo daily (~9 ngày).
- `sensor.nchmf_da_nang_nhiet_do` — nhiệt độ (°C).
- `sensor.nchmf_da_nang_do_am` — độ ẩm (%).
- `sensor.nchmf_da_nang_gio` — tốc độ gió (m/s), kèm `wind_dir`.
- `sensor.nchmf_da_nang_nhiet_do_10_ngay_qua` — mảng nhiệt độ 10 ngày qua (attr `temperatures`, `times`) để vẽ chart apexcharts.

## Cài đặt qua HACS

1. HACS → **Integrations** → menu (⋮) góc phải → **Custom repositories**.
2. Thêm repo `https://github.com/MinhPC/nchmf`, category **Integration**.
3. Tìm **NCHMF Weather (Da Nang)** → **Download**.
4. **Restart** Home Assistant.

### Cài thủ công

Copy thư mục `custom_components/nchmf/` vào `/config/custom_components/` rồi Restart.

## Cấu hình

Không có UI config flow. Thêm vào `configuration.yaml`:

```yaml
nchmf:
```

Rồi **Restart**.

### Đổi địa điểm

Sửa `URL` trong `custom_components/nchmf/const.py` (lấy URL tỉnh khác trên nchmf,
đổi mã `w..`) rồi Restart. Selector/parser giữ nguyên vì mọi trang tỉnh dùng chung template HTML.

## Ghi chú kỹ thuật

- `iot_class: cloud_polling`, cập nhật mỗi 30 phút.
- Site .gov.vn lỗi chuỗi chứng chỉ SSL → fetch với `ssl=False` (bắt buộc, đừng bỏ).
- Chi tiết kiến trúc & cách sửa selector khi nchmf đổi giao diện: xem [`CLAUDE.md`](CLAUDE.md).

## License

MIT
