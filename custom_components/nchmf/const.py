"""Constants for the NCHMF weather integration."""

DOMAIN = "nchmf"

# Config entry data keys
CONF_URL = "url"
CONF_NAME = "name"

# Options
CONF_SCAN_INTERVAL = "scan_interval"

# URL mặc định: Đà Nẵng (Hải Châu). Người dùng có thể chọn tỉnh khác trong
# config flow (dropdown lấy từ INDEX_URL) hoặc dán URL thủ công.
DEFAULT_URL = "https://www.nchmf.gov.vn/kttv/vi-VN/1/hai-chau-tp-da-nang-w55.html"

# Trang liệt kê ~62 điểm/tỉnh -> dùng dựng dropdown chọn tỉnh.
INDEX_URL = "https://www.nchmf.gov.vn/kttv/vi-VN/1/index.html"

ATTRIBUTION = "Dữ liệu từ Trung tâm Dự báo KTTV quốc gia (nchmf.gov.vn)"

# Chu kỳ cập nhật (phút): mặc định + giới hạn cho options flow.
DEFAULT_SCAN_INTERVAL_MINUTES = 30
MIN_SCAN_INTERVAL_MINUTES = 10
MAX_SCAN_INTERVAL_MINUTES = 180

# Repairs: id issue khi parse được nhưng thiếu dữ liệu lõi (site đổi layout).
ISSUE_NO_DATA = "no_data"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
