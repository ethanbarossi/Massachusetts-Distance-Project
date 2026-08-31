const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector(".main-nav");

menuToggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
});

document.querySelectorAll(".main-nav a").forEach(link => {
  link.addEventListener("click", () => nav.classList.remove("open"));
});

function filterArticles(season) {
  document.querySelectorAll(".filter").forEach(btn => btn.classList.remove("active"));
  const matching = [...document.querySelectorAll(".filter")].find(btn =>
    btn.textContent.toLowerCase().replace(" ", "") === season.toLowerCase()
  );
  if (matching) matching.classList.add("active");

  document.querySelectorAll(".article-card").forEach(card => {
    card.style.display = season === "all" || card.dataset.season === season ? "" : "none";
  });
}
