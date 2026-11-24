// Notices page: search box and category buttons that filter the table in the page.
// Without JavaScript the tools stay hidden and every row is shown.
(function () {
  var tools = document.getElementById("notice-tools");
  var input = document.getElementById("notice-search");
  var count = document.getElementById("notice-count");
  var none = document.getElementById("notice-none");
  var rows = Array.prototype.slice.call(document.querySelectorAll(".notices-table tbody tr"));
  var buttons = Array.prototype.slice.call(document.querySelectorAll(".filter"));
  if (!tools || !input) return;
  tools.hidden = false;

  var category = "all";

  function words(text) {
    return text.toLowerCase().split(/\s+/).filter(Boolean);
  }

  function matches(row, terms) {
    if (category !== "all" && row.getAttribute("data-category") !== category) return false;
    var text = row.textContent.toLowerCase();
    return terms.every(function (t) { return text.indexOf(t) !== -1; });
  }

  function apply() {
    var terms = words(input.value);
    var shown = 0;
    rows.forEach(function (row) {
      var ok = matches(row, terms);
      row.hidden = !ok;
      if (ok) shown += 1;
    });
    count.textContent = shown === rows.length ? rows.length + " notices" : shown + " of " + rows.length + " notices";
    none.hidden = shown !== 0;
  }

  function choose(value) {
    category = value;
    buttons.forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-category") === value ? "true" : "false");
    });
    apply();
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () { choose(b.getAttribute("data-category")); });
  });
  input.addEventListener("input", apply);

  var params = new URLSearchParams(window.location.search);
  if (params.get("q")) input.value = params.get("q");
  var wanted = params.get("category");
  var known = buttons.some(function (b) { return b.getAttribute("data-category") === wanted; });
  choose(known ? wanted : "all");
})();
