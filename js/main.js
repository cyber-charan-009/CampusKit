(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem("campuskit-theme");
  if (saved) root.dataset.theme = saved;

  const motionOk = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      const paint = () => {
        const dark = root.dataset.theme === "dark";
        toggle.textContent = dark ? "Light" : "Dark";
        toggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      };
      paint();
      toggle.addEventListener("click", () => {
        root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
        localStorage.setItem("campuskit-theme", root.dataset.theme);
        paint();
      });
    }

    const search = document.querySelector("#tool-search");
    const cards = [...document.querySelectorAll(".tool-card")];
    const empty = document.querySelector("#tool-empty");
    let category = "all";
    const apply = () => {
      const q = (search?.value || "").trim().toLowerCase();
      cards.forEach((card) => {
        const okCat = category === "all" || card.dataset.category === category;
        const okText = !q || card.textContent.toLowerCase().includes(q);
        card.hidden = !(okCat && okText);
      });
      if (empty) empty.hidden = cards.some((card) => !card.hidden);
    };
    search?.addEventListener("input", apply);
    document.querySelectorAll("[data-category-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        category = button.dataset.categoryFilter;
        document.querySelectorAll("[data-category-filter]").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        apply();
      });
    });

    document.querySelectorAll("[data-year]").forEach((node) => {
      node.textContent = new Date().getFullYear();
    });
    document.querySelectorAll("[data-print]").forEach((node) => {
      node.addEventListener("click", () => window.print());
    });

    const bar = document.createElement("div");
    bar.className = "scroll-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.prepend(bar);

    const rig = document.querySelector(".orbit-rig");
    const glow = document.querySelector(".pointer-glow");
    let scrollTick = false;

    const paintScroll = () => {
      scrollTick = false;
      const height = document.documentElement.scrollHeight - window.innerHeight;
      const progress = height > 0 ? window.scrollY / height : 0;
      bar.style.transform = `scaleX(${progress})`;
      if (rig) {
        const hero = document.querySelector(".hero");
        const limit = hero ? hero.offsetHeight : window.innerHeight;
        const local = Math.max(0, Math.min(1, window.scrollY / limit));
        rig.style.setProperty("--scroll", local.toFixed(3));
      }
    };

    const queueScroll = () => {
      if (scrollTick) return;
      scrollTick = true;
      requestAnimationFrame(paintScroll);
    };
    paintScroll();
    window.addEventListener("scroll", queueScroll, { passive: true });
    window.addEventListener("resize", queueScroll);

    if (motionOk && finePointer) {
      window.addEventListener("pointermove", (event) => {
        const x = event.clientX / window.innerWidth - 0.5;
        const y = event.clientY / window.innerHeight - 0.5;
        if (rig) {
          rig.style.setProperty("--ry", `${x * 22}deg`);
          rig.style.setProperty("--rx", `${12 - y * 14}deg`);
        }
        if (glow) {
          glow.style.setProperty("--gx", `${event.clientX}px`);
          glow.style.setProperty("--gy", `${event.clientY}px`);
        }
      });

      cards.forEach((card) => {
        card.addEventListener("pointermove", (event) => {
          const rect = card.getBoundingClientRect();
          const x = (event.clientX - rect.left) / rect.width - 0.5;
          const y = (event.clientY - rect.top) / rect.height - 0.5;
          card.style.transform = `rotateX(${(-y * 7).toFixed(2)}deg) rotateY(${(x * 9).toFixed(2)}deg) translateY(-6px)`;
        });
        card.addEventListener("pointerleave", () => {
          card.style.transform = "";
        });
      });
    }
  });
})();
