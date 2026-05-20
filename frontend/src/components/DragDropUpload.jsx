import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export default function DragDropUpload({
  label,
  accept = "image/*",
  multiple = false,
  onFilesSelected,
  hint,
}) {
  const { t } = useTranslation();
  const inputRef = useRef(null);
  const [isOver, setIsOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [files, setFiles] = useState([]);

  const previewUrl = useMemo(() => {
    if (!files.length) return "";
    return URL.createObjectURL(files[0]);
  }, [files]);

  function triggerSelect() {
    if (inputRef.current) inputRef.current.click();
  }

  function commit(newFiles) {
    const asArray = Array.from(newFiles || []).filter((f) => f && String(f.type).startsWith("image/"));
    setFiles(asArray);
    if (typeof onFilesSelected === "function") {
      onFilesSelected(asArray);
    }

    setProgress(0);
    let tick = 0;
    const timer = setInterval(() => {
      tick += 12;
      if (tick >= 100) {
        setProgress(100);
        clearInterval(timer);
        return;
      }
      setProgress(tick);
    }, 35);
  }

  return (
    <div
      className={`dropzone ${isOver ? "over" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setIsOver(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setIsOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setIsOver(false);
        commit(event.dataTransfer.files);
      }}
      onClick={triggerSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          triggerSelect();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={(event) => commit(event.target.files)}
      />

      <div className="dropzone-top">
        <p className="dropzone-label">{label || t("common.uploadImage")}</p>
        <p className="dropzone-hint">{hint || t("common.dragAndDropImage")}</p>
      </div>

      {!!previewUrl && (
        <div className="dropzone-preview-wrap">
          <img src={previewUrl} alt={t("common.uploadPreview")} className="dropzone-preview" />
          <div className="dropzone-overlay">{t("common.previewReady")}</div>
        </div>
      )}

      <div className="dropzone-progress">
        <span style={{ width: `${progress}%` }} />
      </div>

      {!!files.length && (
        <p className="dropzone-count">
          {t("common.fileSelected", { count: files.length })}
        </p>
      )}
    </div>
  );
}
