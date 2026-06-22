import katex from "katex";
export default function Math({ tex, display }: { tex: string; display?: boolean }) {
  const html = katex.renderToString(tex, { displayMode: !!display, throwOnError: false });
  return <span className="inline-block" dangerouslySetInnerHTML={{ __html: html }} />;
}
