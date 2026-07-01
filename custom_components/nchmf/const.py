"""Constants for the NCHMF weather integration."""

DOMAIN = "nchmf"

# Config entry data keys
CONF_URL = "url"
CONF_NAME = "name"

# URL mặc định: Đà Nẵng (Hải Châu). Người dùng có thể nhập URL tỉnh khác
# ngay trong config flow (lấy trên nchmf.gov.vn, đổi mã "w..").
DEFAULT_URL = "https://www.nchmf.gov.vn/kttv/vi-VN/1/da-nang-w55.html"

ATTRIBUTION = "Dữ liệu từ Trung tâm Dự báo KTTV quốc gia (nchmf.gov.vn)"

SCAN_INTERVAL_MINUTES = 30

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
