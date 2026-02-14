(function () {
  /**
   * Display a toast message using the shared toast container.
   * Exposed globally so page-specific scripts can trigger notifications.
   * @param {string} message
   * @param {number} [duration=3000]
   */
  function showToast(message, duration = 3000) {
    if (!message) {
      return;
    }

    const toast = document.getElementById("toast");
    if (!toast) {
      return;
    }

    toast.textContent = message;
    toast.classList.add("show");

    const timeoutId = Number(toast.dataset.timeoutId);
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    const newTimeoutId = window.setTimeout(() => {
      toast.classList.remove("show");
      toast.dataset.timeoutId = "";
    }, duration);

    toast.dataset.timeoutId = String(newTimeoutId);
  }

  function initFlashToast() {
    const flashSource = document.querySelector("[data-toast-message]");
    if (!flashSource) {
      return;
    }

    const message = flashSource.getAttribute("data-toast-message");
    if (message) {
      showToast(message);
    }

    flashSource.remove();
  }

  function initViewportDebugger() {
    const widthTarget = document.getElementById("width");
    const heightTarget = document.getElementById("height");
    if (!widthTarget || !heightTarget) {
      return;
    }

    const updateViewportSize = () => {
      widthTarget.textContent = window.innerWidth;
      heightTarget.textContent = window.innerHeight;
    };

    updateViewportSize();
    window.addEventListener("resize", updateViewportSize);
  }

  function initDesktopNavOffset() {
    const nav = document.getElementById("desktop-nav");
    if (!nav) {
      return;
    }

    const updateOffset = () => {
      const height = Math.ceil(nav.getBoundingClientRect().height);
      if (height > 0) {
        document.documentElement.style.setProperty("--desktop-nav-offset", `${height}px`);
      }
    };

    updateOffset();
    window.addEventListener("resize", updateOffset);

    if (window.ResizeObserver) {
      const observer = new ResizeObserver(updateOffset);
      observer.observe(nav);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initFlashToast();
    initViewportDebugger();
    initDesktopNavOffset();
  });

  window.showToast = showToast;
})();
