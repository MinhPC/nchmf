"""Constants for the NCHMF weather integration."""

DOMAIN = "nchmf"

# Config entry data keys
CONF_LAT = "latitude"
CONF_LON = "longitude"
CONF_NAME = "name"

# Options
CONF_SCAN_INTERVAL = "scan_interval"

# API JSON của Tổng cục Khí tượng Thuỷ văn (khituongvietnam.gov.vn).
# Nhận lat/lon -> tự resolve về TRẠM/PHƯỜNG gần nhất, trả JSON sạch
# (không còn scrape HTML nchmf.gov.vn). Cert hợp lệ -> verify SSL bình thường.
API_URL = "https://khituongvietnam.gov.vn/WeatherApiService/api/forecast"

# Quan trắc THỜI GIAN THỰC (trạm gần nhất) theo lat/lon — dùng cho "hiện tại".
# Trả JSON: Current_Temp, Humidity, Rainfall, Wind ("Gió <hướng> - tốc độ: N m/s"),
# Weather_Text, Icon, Name (tên trạm), TimeObservation (giờ quan trắc).
# (Chính trang chủ kttv.html gọi endpoint này cho popup "hiện tại".)
OBS_URL = "https://khituongvietnam.gov.vn/WeatherApiService/api/wetherlocal"

# Toạ độ mặc định (Phường Hoà Xuân, TP Đà Nẵng) nếu không lấy được toạ độ nhà HA.
DEFAULT_LAT = 15.995433
DEFAULT_LON = 108.21152

# Trường Icon trong API là đường dẫn tương đối -> prefix này thành URL đầy đủ.
ICON_BASE = "https://kttv.gov.vn/"

ATTRIBUTION = "Dữ liệu từ Tổng cục Khí tượng Thuỷ văn (khituongvietnam.gov.vn)"

# Chu kỳ cập nhật (phút): mặc định + giới hạn cho options flow.
DEFAULT_SCAN_INTERVAL_MINUTES = 30
MIN_SCAN_INTERVAL_MINUTES = 10
MAX_SCAN_INTERVAL_MINUTES = 180

# Repairs: id issue khi gọi API OK nhưng thiếu dữ liệu lõi (API đổi schema).
ISSUE_NO_DATA = "no_data"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
