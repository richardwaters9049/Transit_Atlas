import { animate } from "motion/mini";

const preference = window.matchMedia("(prefers-reduced-motion: reduce)");

export function motionAllowed(): boolean {
  return !preference.matches;
}

export function arrive(elements: Iterable<Element>, distance = 9): void {
  if (!motionAllowed()) return;
  const nodes = Array.from(elements).filter((node) => !node.closest("[hidden], [inert]"));
  nodes.forEach((node, index) => {
    animate(node, {
      opacity: [0, 1],
      transform: [`translateY(${distance}px)`, "translateY(0px)"],
    }, { duration: 0.36, delay: index * 0.045, ease: [0.18, 0.8, 0.32, 1] });
  });
}

export async function fadeOpening(element: HTMLElement, duration: number): Promise<void> {
  if (motionAllowed()) {
    await animate(element, { opacity: [1, 0] }, { duration, ease: "easeOut" });
  }
}
