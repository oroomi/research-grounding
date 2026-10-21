/*! based-on.js: renders "Based on: Author (Year)" with a link and a hover/tap card. No dependencies, ~120 lines.
 *
 * Declarative:
 *   <span class="based-on" data-author="Unkel et al." data-year="2012" data-url="https://doi.org/..."
 *         data-title="Paper title" data-authors="Full author list (optional)"
 *         data-method="One line: what we compute from it."
 *         data-level="implements"            <!-- or "validated" -->
 *         data-sample="n=3,412 isolates, ward 7, 2024"></span>     <!-- shown when level=validated -->
 *   <script src="based-on.js" defer></script>
 *
 * Imperative:  BasedOn.mount(root?)  BasedOn.render(el, opts)  BasedOn.create(opts) -> element
 * Text is always set with textContent and links must be http(s): safe for strings that come from a paper or a user.
 * Honesty: level "validated" REQUIRES a sample; without one the badge falls back to "implements".
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.BasedOn = api;
  if (typeof document !== "undefined") {
    var go = function () { api.mount(document); };
    document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", go) : go();
  }
})(typeof window !== "undefined" ? window : this, function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg", uid = 0, current = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function svg(path, cls) {
    var s = document.createElementNS(SVGNS, "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "2"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
    s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false"); if (cls) s.setAttribute("class", cls);
    var p = document.createElementNS(SVGNS, "path"); p.setAttribute("d", path); s.appendChild(p);
    return s;
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }
  function fromData(node) {
    var d = node.dataset;
    return { author: d.author, year: d.year, url: d.url, title: d.title, authors: d.authors, method: d.method, level: d.level, sample: d.sample, theme: d.theme };
  }

  function render(node, o) {
    o = o || fromData(node);
    var validated = o.level === "validated" && !!(o.sample && String(o.sample).trim());
    var url = safeUrl(o.url), id = "bo-card-" + (++uid), ref = (o.author || "Unknown author") + (o.year ? " (" + o.year + ")" : "");
    node.textContent = "";
    node.classList.add("based-on");
    node.setAttribute("data-level", validated ? "validated" : "implements");
    node.setAttribute("data-js", "");
    if (o.theme) node.setAttribute("data-theme", o.theme);

    var link = el(url ? "a" : "span", "based-on__link");
    if (url) { link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; }
    link.appendChild(svg("M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16zM4 21.5A2.5 2.5 0 0 1 6.5 19H20M9 8h6M9 12h6", "based-on__icon"));
    link.appendChild(el("span", "based-on__label", "Based on:"));
    link.appendChild(el("span", "based-on__ref", ref));

    var btn = el("button", "based-on__info");
    btn.type = "button"; btn.setAttribute("aria-expanded", "false"); btn.setAttribute("aria-controls", id);
    btn.setAttribute("aria-label", "How we use " + ref + ": " + (validated ? "validated" : "implements, not yet validated"));
    btn.appendChild(el("span", "based-on__dot")); btn.appendChild(svg("M12 16v-4M12 8h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z", "based-on__i"));

    var card = el("span", "based-on__card"); card.id = id; card.setAttribute("role", "group"); card.setAttribute("aria-label", "About " + ref);
    card.appendChild(el("span", "based-on__kicker", "Method we follow"));
    if (o.title) card.appendChild(el("span", "based-on__title", o.title));
    if (o.authors) card.appendChild(el("span", "based-on__authors", o.authors + (o.year ? ", " + o.year : "")));
    if (o.method) card.appendChild(el("span", "based-on__method", o.method));
    card.appendChild(el("span", "based-on__level", validated ? "Validated on " + o.sample : "Implements the method. Not yet validated on our data."));
    if (url) { var more = el("a", "based-on__more", "Read the paper ↗"); more.href = url; more.target = "_blank"; more.rel = "noopener noreferrer"; card.appendChild(more); }

    node.appendChild(link); node.appendChild(btn); node.appendChild(card);

    var timer;
    function place() {
      var r = node.getBoundingClientRect(), cw = card.offsetWidth, ch = card.offsetHeight, vw = document.documentElement.clientWidth, vh = window.innerHeight, m = 8;
      var left = Math.max(m, Math.min(r.left, vw - cw - m));
      var below = r.bottom + 8, top = (below + ch + m <= vh || r.top - ch - 8 < m) ? below : r.top - ch - 8;
      card.style.left = left + "px"; card.style.top = Math.max(m, top) + "px";
    }
    function open() { if (current && current !== close) current(); node.setAttribute("data-open", ""); btn.setAttribute("aria-expanded", "true"); place(); current = close; }
    function close() { node.removeAttribute("data-open"); btn.setAttribute("aria-expanded", "false"); if (current === close) current = null; }
    btn.addEventListener("click", function (e) { e.stopPropagation(); node.hasAttribute("data-open") ? close() : open(); });
    var hover = window.matchMedia && window.matchMedia("(hover: hover)").matches;
    if (hover) {
      node.addEventListener("mouseenter", function () { clearTimeout(timer); timer = setTimeout(open, 90); });
      node.addEventListener("mouseleave", function () { clearTimeout(timer); timer = setTimeout(close, 160); });
    }
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && node.hasAttribute("data-open")) { close(); if (node.contains(document.activeElement)) btn.focus(); } });
    document.addEventListener("click", function (e) { if (!node.contains(e.target)) close(); });
    window.addEventListener("scroll", function () { if (node.hasAttribute("data-open")) place(); }, { passive: true, capture: true });
    window.addEventListener("resize", function () { if (node.hasAttribute("data-open")) place(); });
    return node;
  }

  function create(o) { return render(el("span"), o); }
  function mount(scope) {
    var nodes = (scope || document).querySelectorAll(".based-on[data-author]:not([data-js])");
    for (var i = 0; i < nodes.length; i++) render(nodes[i]);
    return nodes.length;
  }
  return { render: render, create: create, mount: mount };
});
