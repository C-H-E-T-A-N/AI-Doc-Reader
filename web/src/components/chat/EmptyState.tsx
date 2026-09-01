import { FileQuestion, Sparkles } from "lucide-react";

const EXAMPLES = [
  "What is this document about?",
  "Summarize the key points",
  "What are the important dates?",
  "What are the main requirements?",
];

interface EmptyStateProps {
  hasDocument: boolean;
  onPick: (q: string) => void;
  onUpload: () => void;
}

export function EmptyState({ hasDocument, onPick, onUpload }: EmptyStateProps) {
  return (
    <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center px-6 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent">
        {hasDocument ? <Sparkles className="h-5 w-5" aria-hidden /> : <FileQuestion className="h-5 w-5" aria-hidden />}
      </span>

      <h2 className="mt-4 text-lg font-semibold tracking-tight text-content">
        Ask questions about your documents
      </h2>
      <p className="mt-1.5 text-sm text-muted">
        Upload a document and use AI to understand, summarize, and explore it. Answers are grounded in
        the source text, with citations.
      </p>

      {hasDocument ? (
        <div className="mt-6 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              onClick={() => onPick(q)}
              className="rounded-lg border border-border bg-elevated px-3.5 py-3 text-left text-[13px] text-content transition-colors hover:border-accent/50 hover:bg-surface-hover"
            >
              {q}
            </button>
          ))}
        </div>
      ) : (
        <button onClick={onUpload} className="btn btn-primary btn-md mt-6">
          Upload your first document
        </button>
      )}
    </div>
  );
}
