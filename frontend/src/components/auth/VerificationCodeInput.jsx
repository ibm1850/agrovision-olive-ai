import { useEffect, useRef } from "react";

export default function VerificationCodeInput({ value, onChange, length = 6 }) {
  const refs = useRef([]);

  useEffect(() => {
    refs.current = refs.current.slice(0, length);
  }, [length]);

  const digits = Array.from({ length }, (_, index) => value[index] || "");

  function updateAt(index, char) {
    const normalized = String(char || "").replace(/[^0-9]/g, "").slice(-1);
    const next = value.split("");
    next[index] = normalized;
    const joined = next.join("").slice(0, length);
    onChange(joined);

    if (normalized && index < length - 1) {
      refs.current[index + 1]?.focus();
    }
  }

  return (
    <div className="verification-inputs">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(node) => {
            refs.current[index] = node;
          }}
          className="verification-cell"
          inputMode="numeric"
          maxLength={1}
          value={digit}
          onChange={(event) => updateAt(index, event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Backspace" && !digit && index > 0) {
              refs.current[index - 1]?.focus();
            }
            if (event.key === "ArrowLeft" && index > 0) refs.current[index - 1]?.focus();
            if (event.key === "ArrowRight" && index < length - 1) refs.current[index + 1]?.focus();
          }}
          onPaste={(event) => {
            const pasted = event.clipboardData.getData("text").replace(/[^0-9]/g, "").slice(0, length);
            if (!pasted) return;
            event.preventDefault();
            onChange(pasted);
            refs.current[Math.min(pasted.length, length) - 1]?.focus();
          }}
          aria-label={`Verification digit ${index + 1}`}
        />
      ))}
    </div>
  );
}
