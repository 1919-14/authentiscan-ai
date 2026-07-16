// ---------------------------------------------------------------------
// Scroll-reveal animations (IntersectionObserver — no external library)
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => observer.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }

  // Animate score bars / meters once visible
  document.querySelectorAll("[data-fill-width]").forEach((el) => {
    const target = el.getAttribute("data-fill-width");
    requestAnimationFrame(() => {
      setTimeout(() => { el.style.width = target + "%"; }, 150);
    });
  });

  // Mobile nav toggle
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => navLinks.classList.toggle("open"));
  }

  // Init Lucide icons if the library is present
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // ---------------------------------------------------------------------
  // Dropzone (upload page)
  // ---------------------------------------------------------------------
  const dropzone = document.querySelector("[data-dropzone]");
  if (dropzone) {
    const input = dropzone.querySelector("input[type=file]");
    const filenameEl = dropzone.querySelector(".dz-filename");

    dropzone.addEventListener("click", () => input.click());

    ["dragenter", "dragover"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        updateFilename();
      }
    });
    input.addEventListener("change", updateFilename);

    function updateFilename() {
      if (input.files.length) {
        filenameEl.textContent = "Selected: " + input.files[0].name;
        filenameEl.style.display = "block";
      }
    }
  }
});
