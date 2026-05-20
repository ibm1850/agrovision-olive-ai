import { Bot, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function MessageBubble({ role, content, sentAt }) {
  const { t } = useTranslation();
  const isUser = role === "user";
  const date = sentAt ? new Date(sentAt) : new Date();
  const timeLabel = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`message-row ${isUser ? "user" : "assistant"}`}>
      {!isUser ? (
        <div className="message-avatar assistant-avatar" aria-hidden="true">
          <Bot size={14} />
        </div>
      ) : null}
      <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
        <p className="message-text">{content}</p>
        <div className="message-meta">
          <span className="message-sender">{isUser ? t("common.user") : t("assistant.title")}</span>
          <span className="message-time">{timeLabel}</span>
        </div>
      </div>
      {isUser ? (
        <div className="message-avatar user-avatar" aria-hidden="true">
          <UserRound size={14} />
        </div>
      ) : null}
    </div>
  );
}
