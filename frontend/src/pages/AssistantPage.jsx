import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Send, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import OliveGuideCard from "../components/guide/OliveGuideCard";
import EmptyStateAssistantCard from "../components/cards/EmptyStateAssistantCard";
import MessageBubble from "../components/MessageBubble";

export default function AssistantPage({ onNavigate }) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "fr";
  const chatLogRef = useRef(null);
  const smartPrompts = useMemo(
    () => [
      t("assistant.summarizeFarmToday"),
      t("assistant.checkHarvest"),
      t("assistant.diseaseReport"),
      t("assistant.showRecentAlerts"),
      t("assistant.weekActions"),
    ],
    [t],
  );

  function makeMessage(role, content) {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      sentAt: new Date().toISOString(),
    };
  }

  const [messages, setMessages] = useState([
    makeMessage("assistant", t("assistant.welcome")),
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const node = chatLogRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, loading]);

  async function send(messageText = input) {
    const text = String(messageText || "").trim();
    if (!text || loading) return;
    setLoading(true);
    setError("");

    const userMessage = makeMessage("user", text);
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      const reply = await api.chat(text, language);
      setMessages((prev) => [
        ...prev,
        makeMessage("assistant", reply.response || t("assistant.noResponse")),
      ]);
    } catch (err) {
      setError(err.message || t("assistant.unavailable"));
    } finally {
      setLoading(false);
    }
  }

  function handleQuickAction(routeId, prompt) {
    if (routeId === "dashboard") {
      onNavigate("dashboard");
      return;
    }
    if (routeId && routeId !== "dashboard") {
      onNavigate(routeId);
    }
    if (prompt) send(prompt);
  }

  return (
    <section className="page-stack">
      <OliveGuideCard
        title={t("assistant.title")}
        message={t("assistant.guideMessage")}
        tip={t("assistant.guideTip")}
        chips={[t("assistant.farmContext"), t("assistant.actionableAnswers"), t("assistant.confidenceAware")]}
      />

      <EmptyStateAssistantCard onSelect={handleQuickAction} />

      <article className="surface-card assistant-shell">
        <div className="assistant-toolbar-title messenger-title">
          <Sparkles size={16} /> {t("assistant.quickActions")}
        </div>
        <div className="chat-presets">
          {smartPrompts.map((prompt) => (
            <button key={prompt} className="quick-chip preset-chip" onClick={() => send(prompt)}>
              {prompt}
            </button>
          ))}
        </div>

        <div className="chat-log messenger-log" ref={chatLogRef}>
          {messages.map((message) => (
            <MessageBubble key={message.id} role={message.role} content={message.content} sentAt={message.sentAt} />
          ))}
          {loading ? (
            <div className="message-row assistant">
              <div className="message-avatar assistant-avatar">
                <Bot size={14} />
              </div>
              <div className="message-bubble assistant typing-bubble">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-text">{t("assistant.thinking")}</span>
              </div>
            </div>
          ) : null}
        </div>

        <div className="chat-input-row messenger-input-row">
          <input
            className="field"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t("assistant.placeholder")}
            onKeyDown={(event) => {
              if (event.key === "Enter") send();
            }}
          />
          <button className="primary-btn messenger-send-btn" onClick={() => send()} disabled={loading || !input.trim()}>
            <Send size={16} />
            <span>{t("assistant.send")}</span>
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </article>
    </section>
  );
}
