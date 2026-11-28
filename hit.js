// 第一方访问计数：GitHub Pages 没有访问日志，仓库 traffic 也不统计 Pages。
// 站点静态托管拿不到任何访问数据，于是用 1x1 图片打到自己的投递服务器（域名从 tunnel-host.txt 动态取，
// 隧道换域名时不用改代码）。记录路径 + 来源站点 origin：
//   - 只取 document.referrer 的站点根（scheme://host），丢掉 path/query ——
//     搜索词等隐私绝不写进日志；同源（站内跳转）不记，只有外部来源才有归因价值。
//   - img 仍用 no-referrer：浏览器不再额外发 referer 头，来源完全走我们显式的 ref 参数。
// 为什么必须记来源：sitemap/IndexNow 只证明「提交受理」，不能证明「搜索真的带来了人」。
// 只有当后端出现 ref=https://www.bing.com 这类搜索引擎来源、且过了 hit_report 的机房/簇降级，
// 才算这条零账号获客道真的进人。
(function () {
  try {
    var p = location.pathname;
    var refOrigin = '';
    try {
      if (document.referrer) {
        var ru = new URL(document.referrer);
        if (ru.origin !== location.origin) refOrigin = ru.origin;  // 仅外部来源
      }
    } catch (e) {}
    fetch('tunnel-host.txt', { cache: 'no-store' })
      .then(function (r) { return r.text(); })
      .then(function (h) {
        h = (h || '').trim();
        if (!h || h.indexOf('.') < 0 || h.indexOf(' ') >= 0) return;
        var img = new Image();
        img.referrerPolicy = 'no-referrer';
        img.src = 'https://' + h + '/hit?p=' + encodeURIComponent(p) +
          '&ref=' + encodeURIComponent(refOrigin) +
          '&t=' + Date.now().toString(36);
      })
      .catch(function () {});
  } catch (e) {}
})();
