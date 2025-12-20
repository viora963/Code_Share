document.addEventListener("click", (e) => {
    const open = e.target.closest("[data-open-modal]");
    if (open) {
      const id = open.getAttribute("data-open-modal");
      const modal = document.getElementById(id);
      if (modal) modal.classList.add("open");
    }
  
    const close = e.target.closest("[data-close-modal]");
    if (close) {
      const id = close.getAttribute("data-close-modal");
      const modal = document.getElementById(id);
      if (modal) modal.classList.remove("open");
    }
  
    const modalBg = e.target.classList.contains("modal") ? e.target : null;
    if (modalBg) modalBg.classList.remove("open");
  });
  