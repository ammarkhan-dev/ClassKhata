(function () {
  var de = document.documentElement, off = false;
  try { off = localStorage.getItem("ck_motion") === "off"; } catch (e) {}
  var rm = off || (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var SEL = ".sc,.cc,.item,.ci,.fc,.arow,.stu,.grp,.card,.cls,.hero,.sm";
  var bar;

  function $(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }

  function prog(on) {
    if (!bar) { bar = document.createElement("div"); bar.id = "ckp"; document.body.appendChild(bar); }
    bar.style.transition = "none";
    if (on) {
      bar.style.opacity = "1"; bar.style.width = "0";
      void bar.offsetWidth;
      bar.style.transition = "width 7s cubic-bezier(.1,.5,.2,1)";
      bar.style.width = "86%";
    } else { bar.style.opacity = "0"; bar.style.width = "0"; }
  }

  function stagger() {
    var main = document.querySelector("main") || document, n = 0;
    $(SEL, main).forEach(function (el) {
      if (el.parentElement && el.parentElement.closest(SEL)) { el.style.animation = "none"; return; }
      if (n < 12) { el.style.setProperty("--i", n); } else { el.style.animation = "none"; }
      n++;
    });
  }

  function isBack(a) {
    var t = (a.textContent || "").trim();
    if (t.charAt(0) === "\u2039") return true;
    if (a.querySelector && a.querySelector('svg path[d="M15 5l-7 7 7 7"]')) return true;
    try { if (document.referrer && a.href === document.referrer) return true; } catch (e) {}
    return false;
  }

  function count() {
    if (rm) return;
    $(".dn,.cls .n,.big,.pp,.tl b,.tiles b,.tot").forEach(function (el) {
      if (el.children.length) return;
      var orig = (el.textContent || "").trim();
      var m = /^(\u20B9?)([\d,]+)(%?)$/.exec(orig);
      if (!m) return;
      var to = parseInt(m[2].replace(/,/g, ""), 10);
      if (!(to > 0) || to > 1e8) return;
      var dur = Math.min(900, 350 + Math.log10(to + 1) * 120), t0 = null;
      function f(ts) {
        if (t0 === null) t0 = ts;
        var p = Math.min(1, (ts - t0) / dur);
        if (p >= 1) { el.textContent = orig; return; }
        el.textContent = m[1] + Math.round(to * (1 - Math.pow(1 - p, 3))).toLocaleString("en-IN") + m[3];
        requestAnimationFrame(f);
      }
      el.textContent = m[1] + "0" + m[3];
      requestAnimationFrame(f);
    });
  }

  function vib(ms) {
    if (!rm && navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) {} }
  }

  function skipUrl(u) {
    return /^\/(backup\/download|export\/|lang\/)/.test(u.pathname) || /\/photo$/.test(u.pathname);
  }

  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var t = e.target.closest && e.target.closest(".sg3 button,nav a,.mch,.chp,form button:not([type=button])");
    if (t) vib(8);
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var u;
    try { u = new URL(a.href, location.href); } catch (x) { return; }
    if (u.origin !== location.origin || (a.target && a.target !== "_self") || a.hasAttribute("download") ||
        a.hasAttribute("data-noanim") || skipUrl(u)) return;
    if (u.pathname === location.pathname && u.search === location.search) return;
    e.preventDefault();
    var back = isBack(a);
    try { sessionStorage.setItem("ck_dir", back ? "back" : "fwd"); } catch (x) {}
    de.classList.add("leaving");
    if (back) de.classList.add("goback");
    prog(true);
    setTimeout(function () { location.href = u.href; }, rm ? 0 : 130);
  }, true);

  document.addEventListener("submit", function (e) {
    if (!e.defaultPrevented) prog(true);
  }, false);

  window.addEventListener("pageshow", function () {
    de.classList.remove("leaving", "goback");
    prog(false);
  });

  $(".sheet,.csh").forEach(function (el) {
    var closing = false;
    Object.defineProperty(el, "hidden", {
      configurable: true,
      get: function () { return this.hasAttribute("hidden"); },
      set: function (v) {
        var s = this;
        if (v) {
          if (s.hasAttribute("hidden") || closing) return;
          if (rm) { s.setAttribute("hidden", ""); return; }
          closing = true;
          s.classList.add("closing");
          setTimeout(function () { s.setAttribute("hidden", ""); s.classList.remove("closing"); closing = false; }, 210);
        } else {
          closing = false;
          s.classList.remove("closing");
          s.removeAttribute("hidden");
        }
      }
    });
  });

  stagger();
  count();
  requestAnimationFrame(function () { requestAnimationFrame(function () { de.classList.add("ck-ready"); }); });
})();
