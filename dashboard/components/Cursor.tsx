"use client";

import { motion, useMotionValue, useSpring } from "framer-motion";
import { useEffect, useState } from "react";

// Custom cursor: a solid dot that tracks the pointer directly, and a
// spring-lagged ring that breathes while idle and expands over links/buttons.
export default function Cursor() {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const ringX = useSpring(x, { stiffness: 260, damping: 24 });
  const ringY = useSpring(y, { stiffness: 260, damping: 24 });
  const [hovering, setHovering] = useState(false);

  useEffect(() => {
    const move = (e: MouseEvent) => {
      x.set(e.clientX);
      y.set(e.clientY);
      setHovering(
        !!(e.target as Element | null)?.closest?.("a, button, .day-chip")
      );
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, [x, y]);

  return (
    <>
      <motion.div
        className="cursor-dot"
        style={{ x, y, translateX: "-50%", translateY: "-50%" }}
      />
      <motion.div
        className="cursor-ring"
        style={{ x: ringX, y: ringY, translateX: "-50%", translateY: "-50%" }}
        animate={
          hovering
            ? { scale: 1.8, opacity: 1 }
            : { scale: [1, 1.18, 1], opacity: 0.8 }
        }
        transition={
          hovering
            ? { duration: 0.25 }
            : { duration: 2.2, repeat: Infinity, ease: "easeInOut" }
        }
      />
    </>
  );
}
