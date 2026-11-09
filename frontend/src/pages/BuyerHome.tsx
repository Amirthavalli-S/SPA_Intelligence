import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { json, request, type Citation } from "../api/client";
import { Alert, EmptyState, Skeleton } from "../components/ui";

interface Reply {
  answer: string;
  refused: boolean;
  citations: Citation[];
  disclaimer?: string;
}
interface Turn {
  role: "user" | "assistant";
  content: string;
  refused?: boolean;
  citations?: Citation[];
}

const KEY = "spa.buyerchat";
const STARTERS = ["s1", "s2", "s3", "s4"] as const;
const load = (): Turn[] => {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.slice(-60) : [];
  } catch {
    return [];
  }
};
const save = (t: Turn[]) => {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(t.slice(-60)));
  } catch {
    /* private window: the chat still works, it just is not remembered */
  }
};

/** The buyer's only page: a chat about their own contract. The server decides which contract; nothing here can change that. */
export default function BuyerHome() {
  const { t } = useTranslation();
  const mine = useQuery({ queryKey: ["buyer-me"], queryFn: () => request<{ linked: boolean; contract_name: string | null }>("/buyer/me"), retry: false });
  const [turns, setTurns] = useState<Turn[]>(load);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const ask = useMutation({
    mutationFn: ({ message, history }: { message: string; history: Turn[] }) =>
      request<Reply>("/buyer/chat", json({ message, channel: "web", history: history.slice(-6).map((x) => ({ role: x.role, content: x.content })) })),
    onSuccess: (r) => setTurns((x) => [...x, { role: "assistant", content: r.answer, refused: r.refused, citations: r.citations }]),
  });
  useEffect(() => {
    save(turns);
    end.current?.scrollIntoView?.({ block: "end", behavior: "smooth" });
  }, [turns, ask.isPending]);

  const send = (raw: string) => {
    const m = raw.trim();
    if (!m || ask.isPending) return;
    const history = turns;
    setTurns([...turns, { role: "user", content: m }]);
    setText("");
    ask.mutate({ message: m, history });
    box.current?.focus();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(text);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(text);
    }
  };
  const reset = () => {
    setTurns([]);
    ask.reset();
  };

  if (mine.isLoading) return <div style={{ padding: "6rem 1rem" }}><Skeleton h={240} /></div>;
  if (mine.error) return <div style={{ padding: "6rem 1rem" }}><Alert tone="warn">{(mine.error as Error).message}</Alert></div>;
  if (!mine.data?.linked) {
    return <div style={{ padding: "6rem 1rem", maxWidth: 640, margin: "0 auto" }}><EmptyState title={t("buyerHome.notLinkedTitle")} body={t("buyerHome.notLinkedBody")} /></div>;
  }
  return (
    <div className="data-layer" style={{ maxWidth: 820, margin: "0 auto", padding: "5.2rem 1rem 2rem", display: "grid", gap: "1rem" }} data-testid="buyer-home">
      <section className="card" style={{ padding: "1rem", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("buyerHome.title")}</h1>
          <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>{t("buyerHome.intro", { name: mine.data.contract_name ?? "" })}</p>
        </div>
        {turns.length > 0 && (
          <button className="chip" onClick={reset} data-testid="chat-reset">{t("buyerHome.newChat")}</button>
        )}
      </section>

      <section className="card" role="log" aria-live="polite" aria-label={t("chat.title")} style={{ padding: "1rem", display: "grid", gap: 12, minHeight: 280, alignContent: "start" }}>
        {turns.length === 0 && (
          <div style={{ display: "grid", gap: 10 }} data-testid="chat-starters">
            <p style={{ margin: 0, color: "var(--muted)" }}>{t("buyerHome.examples")}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {STARTERS.map((k) => (
                <button key={k} className="chip" onClick={() => send(t(`buyerHome.${k}`))} disabled={ask.isPending}>{t(`buyerHome.${k}`)}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((m, i) => (
          <div
            key={i}
            data-testid={m.role === "user" ? "msg-user" : m.refused ? "msg-refused" : "msg-assistant"}
            style={{
              justifySelf: m.role === "user" ? "end" : "start",
              maxWidth: "92%",
              padding: "0.6rem 0.9rem",
              borderRadius: m.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              background: m.role === "user" ? "var(--accent-fill)" : "var(--surface-2)",
              color: m.role === "user" ? "var(--on-accent, #fff)" : "inherit",
              border: m.refused ? "1px solid var(--warn)" : "1px solid var(--line)",
              display: "grid",
              gap: 6,
            }}
          >
            <span dir="auto" style={{ whiteSpace: "pre-wrap" }}>{m.content}</span>
            {m.refused && <small style={{ color: "var(--warn)" }}>{t("buyerHome.referred")}</small>}
            {m.citations?.slice(0, 3).map((c, j) => (
              <blockquote key={j} style={{ margin: 0, paddingInlineStart: 10, borderInlineStart: "3px solid var(--line)", color: "var(--muted)" }} dir="auto">
                {c.quote} <span className="num">({t("common.pageShort")} {c.page})</span>
              </blockquote>
            ))}
          </div>
        ))}
        {ask.isPending && (
          <div data-testid="chat-typing" role="status" style={{ justifySelf: "start", padding: "0.5rem 0.9rem", borderRadius: 16, background: "var(--surface-2)", color: "var(--muted)" }}>
            {t("buyerHome.typing")}
          </div>
        )}
        {ask.error && <Alert tone="danger">{(ask.error as Error).message}</Alert>}
        <div ref={end} />
      </section>

      <form onSubmit={submit} style={{ display: "flex", gap: 8, alignItems: "end" }}>
        <textarea
          ref={box}
          aria-label={t("buyerHome.ask")}
          placeholder={t("buyerHome.ask")}
          value={text}
          rows={1}
          maxLength={1000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          dir="auto"
          style={{ flex: 1, minHeight: 48, maxHeight: 140, resize: "vertical", padding: "0.7rem 0.8rem" }}
        />
        <button className="btn" type="submit" disabled={!text.trim() || ask.isPending} style={{ minHeight: 48 }}>{t("buyerHome.send")}</button>
      </form>
      <small style={{ color: "var(--muted)" }}>{t("buyerHome.hint")}</small>
    </div>
  );
}
