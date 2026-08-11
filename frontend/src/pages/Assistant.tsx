import { Bot, Database, Info, Loader2, Send, User } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, CardContent } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { AssistantResponse } from "@/lib/types";

interface Turn {
  question: string;
  answer?: AssistantResponse;
  error?: string;
  loading?: boolean;
}

const SUGGESTIONS = [
  "Which pharmacies are at highest stockout risk?",
  "How is demand distributed by canton?",
  "What's the total forecast demand this week?",
];

export default function Assistant() {
  const { data: who } = useAsync(() => api.whoami(), []);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setQ("");
    setBusy(true);
    const idx = turns.length;
    setTurns((t) => [...t, { question, loading: true }]);
    try {
      const answer = await api.assistant(question);
      setTurns((t) => t.map((x, i) => (i === idx ? { question, answer } : x)));
    } catch (e: unknown) {
      setTurns((t) => t.map((x, i) => (i === idx ? { question, error: String((e as Error).message) } : x)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Ask your data</h1>
        <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
          Natural-language questions over the forecasting data
          <Badge variant="outline">
            <User className="mr-1 h-3 w-3" /> {who?.user ?? "…"}
          </Badge>
        </p>
      </div>

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="rounded-full border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-4">
        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
                {t.question}
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <Bot className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                {t.loading && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
                  </div>
                )}
                {t.error && <div className="text-sm text-critical">Error: {t.error}</div>}
                {t.answer && <AnswerBlock a={t.answer} />}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="sticky bottom-4">
        <div className="flex gap-2 rounded-xl border bg-card p-2 shadow-sm">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(q)}
            placeholder="Ask about demand, stockout risk, cantons…"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none"
          />
          <Button onClick={() => ask(q)} disabled={busy || !q.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function AnswerBlock({ a }: { a: AssistantResponse }) {
  const [showSql, setShowSql] = useState(false);
  return (
    <div className="space-y-2">
      <Card>
        <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap pt-4 text-sm">
          {a.answer}
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button
          onClick={() => setShowSql((s) => !s)}
          className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-muted-foreground hover:bg-muted"
        >
          <Database className="h-3 w-3" /> {showSql ? "Hide" : "Show"} generated SQL
        </button>
        {a.sources.map((s) => (
          <Badge key={s} variant="outline">{s}</Badge>
        ))}
        <span className="ml-auto text-muted-foreground">source: {a.source}</span>
      </div>

      {showSql && (
        <pre className="overflow-x-auto rounded-md border bg-muted/50 p-3 text-xs">
          <code>{a.sql}</code>
        </pre>
      )}

      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Info className="h-3 w-3" /> {a.disclaimer}
      </div>
    </div>
  );
}
