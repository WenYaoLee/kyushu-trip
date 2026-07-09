# Kyushu Trip v2.0

九州 6 天自駕旅行網站。

## v2.0 更新

- 全站租車資訊由 ORIX 改為 Times Car Rental。
- 更新 Times 預約編號、店鋪、電話、取車 / 還車時間、費用與 Super Safety Package。
- 新增旅行首頁 App 風格入口。
- 新增每日 Google Maps 路線快捷頁。
- 新增旅行工具頁：天氣快捷、日圓換算、油資預估、每日出門檢查。
- 修正伊都物語牛奶圖片路徑為 `images/ito-monogatari-milk.jpg`。

## 使用方式

請用 GitHub Pages 或本機伺服器開啟，例如 VS Code Live Server。
不要直接用 `file://` 開啟，因為本專案會用 `fetch()` 載入 `views/*.html`。

## 主要結構

```text
index.html
assets/css/style.css
assets/js/app.js
assets/js/expense.js
assets/js/firebase-config.js
views/home.html
views/itinerary.html
views/checklist.html
views/concierge.html
views/rental.html
views/lodging.html
views/expense.html
views/maps.html
views/tools.html
images/
```


## v2.3 更新
- 修正「必要花費」Day1～Day6 頁內導覽，避免與 SPA hash 路由衝突。
- 新增 Smooth Scroll、Sticky 快速導覽、目前 Day 高亮。
- 必要花費新增付款狀態標籤，ETC 維持最新預估 ¥13,300。


## v2.3.1 修正
- 修正 itinerary.html 其中一個 SVG polygon points 格式錯誤。
- 補上 images/ito-monogatari-milk.jpg，避免本機預覽圖片 404。
