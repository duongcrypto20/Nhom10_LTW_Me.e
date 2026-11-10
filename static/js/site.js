document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".menu-toggle");
  const navigation = document.querySelector(".primary-nav");

  if (!toggle || !navigation) return;

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    navigation.classList.toggle("is-open", !isOpen);
  });

  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      toggle.setAttribute("aria-expanded", "false");
      navigation.classList.remove("is-open");
    }
  });
});
