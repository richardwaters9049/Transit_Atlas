import { fadeOpening, motionAllowed } from "./ui-motion";

const OPENING_DURATION = 5_400;

export function showOpening() {
  const overlay = document.getElementById("opening")!;
  const container = document.getElementById("opening-scene")!;
  const progress = document.getElementById("opening-progress-bar")!;
  const status = document.getElementById("opening-status")!;
  const skip = document.getElementById("skip-opening") as HTMLButtonElement;
  const workbench = document.getElementById("workbench")!;
  const animated = motionAllowed();
  const listeners = new AbortController();
  let stopVisual: (() => void) | undefined;
  let visualActive = animated;
  let skipped = false;

  if (animated) {
    void import("./opening-visual").then((visual) => {
      if (visualActive && motionAllowed()) stopVisual = visual.launchOrbit(container);
    }).catch(() => {
      // The static opening remains available if the visual renderer cannot start.
    });
  }

  const hold = animated ? new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, OPENING_DURATION);
    const leave = () => {
      skipped = true;
      visualActive = false;
      window.clearTimeout(timer);
      skip.hidden = true;
      resolve();
    };
    skip.addEventListener("click", leave, { once: true, signal: listeners.signal });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !skipped) leave();
    }, { signal: listeners.signal });
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    preference.addEventListener("change", (event) => {
      if (event.matches) {
        leave();
        stopVisual?.();
        stopVisual = undefined;
      }
    }, { signal: listeners.signal });
  }) : Promise.resolve();

  function update(message: string, completion: number) {
    status.textContent = message;
    progress.style.setProperty("--loaded", `${completion}%`);
  }

  return {
    update,
    async reveal() {
      if (animated && !skipped) update("Workspace ready", 100);
      await hold;
      listeners.abort();
      visualActive = false;
      update("Opening the workspace…", 100);
      if (motionAllowed()) workbench.dataset.entering = skipped ? "skip" : "full";
      workbench.hidden = false;
      try {
        await fadeOpening(overlay, skipped ? 0.22 : 0.46);
        overlay.hidden = true;
        stopVisual?.();
        stopVisual = undefined;
        const entrances = workbench.getAnimations({ subtree: true })
          .filter((animation) => animation instanceof CSSAnimation && animation.animationName === "workspace-entrance");
        await Promise.allSettled(entrances.map((animation) => animation.finished));
      } finally {
        stopVisual?.();
        overlay.hidden = true;
        workbench.inert = false;
        delete workbench.dataset.entering;
      }
    },
  };
}
