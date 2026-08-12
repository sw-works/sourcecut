import { notFound } from "next/navigation";
import TextReader from "../../../../components/odyssey/text-reader";

type Props = {
  params: Promise<{ book: string }>;
  searchParams: Promise<{ version?: string; lines?: string }>;
};

export default async function ReadBook({ params, searchParams }: Props) {
  const [{ book: rawBook }, query] = await Promise.all([params, searchParams]);
  const book = Number(rawBook);
  if (!Number.isInteger(book) || book < 1 || book > 24) notFound();
  const lines = /^(\d+)-(\d+)$/.exec(query.lines ?? "");
  const fromLine = lines ? Number(lines[1]) : 1;
  const selectedEnd = lines ? Math.min(Number(lines[2]), fromLine + 199) : 80;
  const contextStart = lines ? Math.max(1, fromLine - Math.min(12, 199 - (selectedEnd - fromLine))) : 1;
  const toLine = lines ? Math.max(selectedEnd, contextStart + 79) : 80;

  return (
    <main id="odyssey-main">
      <TextReader
        initialBook={book}
        initialFromLine={contextStart}
        initialToLine={Math.max(contextStart, Math.min(toLine, contextStart + 199))}
        initialSelection={lines ? { start: fromLine, end: selectedEnd } : null}
        initialVersion={query.version ?? "odyssey-perseus-grc2"}
      />
    </main>
  );
}
