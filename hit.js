// 第一方访问计数：GitHub Pages 没有访问日志，仓库 traffic 也不统计 Pages。
// 站点静态托管拿不到任何访问数据，于是用 1x1 图片打到自己的投递服务器（域名从 tunnel-host.txt 动态取，
// 隧道换域名时不用改代码）。只记录路径，不写 cookie、不存个人标识。
(function () {
  try {
    var p = location.pathname;
    fetch('tunnel-host.txt', { cache: 'no-store' })
      .then(function (r) { return r.text(); })
      .then(function (h) {
        h = (h || '').trim();
        if (!h || h.indexOf('.') < 0 || h.indexOf(' ') >= 0) return;
        var img = new Image();
        img.referrerPolicy = 'no-referrer';
        img.src = 'https://' + h + '/hit?p=' + encodeURIComponent(p) + '&t=' + Date.now().toString(36);
      })
      .catch(function () {});
  } catch (e) {}
})();
