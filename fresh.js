// 全站「最新数据」统一渲染：任何页面写死行数/日期都会在第二天变成假话。
// 用法：在页面里写 <span data-m="mRows">100,821</span>，并引入本文件（data-meta 指向 meta.json 相对路径）。
(function () {
  var s = document.currentScript || {};
  var path = s.getAttribute ? (s.getAttribute("data-meta") || "live/meta.json") : "live/meta.json";
  fetch(path, { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (m) {
    var f = m.latest || {};
    var map = {
      mRows: m.rows.toLocaleString(),
      mDays: String(m.trading_days),
      mDate: m.last_trade_date,
      mAvg: (m.rows / m.trading_days).toFixed(1),
      mZt: String(f.limit_up),
      mStreak2: String(f.streak2plus),
      mOneWord: String(f.one_word),
      mMaxStreak: String(f.max_streak),
      mSampleDate: (m.sample && m.sample.last_date) || m.last_trade_date
    };
    document.querySelectorAll("[data-m]").forEach(function (el) {
      var k = el.getAttribute("data-m");
      if (k in map) el.textContent = map[k];
    });
  }).catch(function () { /* 保留静态兜底值 */ });
})();
