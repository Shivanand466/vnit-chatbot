// Main menu: the hamburger below 900 px, and dropdowns that open on click or Enter
// as well as on hover (hover is done in site.css).
(function () {
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.querySelector(".main-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var buttons = document.querySelectorAll(".menu-button");
  function closeAll(except) {
    buttons.forEach(function (b) {
      if (b !== except) {
        b.parentNode.classList.remove("open");
        b.setAttribute("aria-expanded", "false");
      }
    });
  }
  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      var item = button.parentNode;
      var open = !item.classList.contains("open");
      closeAll(button);
      item.classList.toggle("open", open);
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
  document.addEventListener("click", function (event) {
    if (!event.target.closest(".menu")) closeAll(null);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      var openItem = document.querySelector(".menu > li.open");
      closeAll(null);
      if (openItem) openItem.querySelector(".menu-button").focus();
    }
  });
})();
