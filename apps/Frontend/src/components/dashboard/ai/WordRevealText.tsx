import React, { useEffect, useState, useRef } from "react";

interface WordRevealTextProps {
  text: string;
  speed?: number; // Speed in ms per word
  className?: string;
}

export const WordRevealText: React.FC<WordRevealTextProps> = ({
  text,
  speed = 40,
  className = "",
}) => {
  const [displayedWordsCount, setDisplayedWordsCount] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const wordsRef = useRef<string[]>([]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);
  }, []);

  useEffect(() => {
    wordsRef.current = text.split(" ");
    if (prefersReducedMotion) {
      setDisplayedWordsCount(wordsRef.current.length);
      return;
    }

    setDisplayedWordsCount(0);
    let currentCount = 0;
    const interval = setInterval(() => {
      currentCount += 1;
      if (currentCount <= wordsRef.current.length) {
        setDisplayedWordsCount(currentCount);
      } else {
        clearInterval(interval);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed, prefersReducedMotion]);

  const visibleText = wordsRef.current.slice(0, displayedWordsCount).join(" ");

  return (
    <div className={className}>
      {/* Screen reader receives the full text immediately for accessibility */}
      <span className="sr-only">{text}</span>
      
      {/* Visual display with word-by-word reveal */}
      <span aria-hidden="true">
        {visibleText}
        {displayedWordsCount < wordsRef.current.length && (
          <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-current animate-pulse opacity-50" />
        )}
      </span>
    </div>
  );
};
