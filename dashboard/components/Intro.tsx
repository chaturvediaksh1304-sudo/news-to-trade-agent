"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

// Opening sequence: letters rise in, a rule sweeps across, the tagline
// stamps in, then the whole black panel lifts to reveal the dashboard.
const NAME = "NEWSTOTRADE";

export default function Intro() {
  const [done, setDone] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDone(true), 3200);
    return () => clearTimeout(t);
  }, []);

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          className="intro"
          exit={{ y: "-100%" }}
          transition={{ duration: 0.9, ease: [0.76, 0, 0.24, 1] }}
        >
          <div className="word" aria-label="News-to-Trade">
            {NAME.split("").map((ch, i) => (
              <motion.span
                key={i}
                initial={{ y: "110%", opacity: 0 }}
                animate={{ y: "0%", opacity: 1 }}
                transition={{
                  duration: 0.7,
                  delay: 0.06 * i,
                  ease: [0.22, 1, 0.36, 1],
                }}
                style={{ display: "inline-block" }}
              >
                {ch}
              </motion.span>
            ))}
          </div>
          <motion.div
            className="rule"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.9, delay: 1.0, ease: [0.22, 1, 0.36, 1] }}
          />
          <motion.div
            className="tag"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 1.5 }}
          >
            S&amp;P 500 · Agent Swarm · On the Record
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
