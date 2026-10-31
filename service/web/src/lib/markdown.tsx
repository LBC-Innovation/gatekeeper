import type { ReactNode } from "react";

/**
 * A small markdown renderer for the agent files. It builds React elements directly, so no HTML from the file is ever injected.
 * It covers what those files use: headings, paragraphs, lists (nested), tables, fenced code, quotes, rules and inline code, bold, italics, links.
 */

export function splitFrontmatter(text: string): { meta: Record<string, string>; body: string } {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: text };
  const meta: Record<string, string> = {};
  for (const line of m[1].split("\n")) { const i = line.indexOf(":"); if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim(); }
  return { meta, body: m[2] };
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g;
  let last = 0, n = 0;
  for (const m of text.matchAll(re)) {
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const t = m[0], k = `${key}-${n++}`;
    if (m[1]) out.push(<code key={k} className="rounded bg-sunken px-1 font-mono text-[13px]">{t.slice(1, -1)}</code>);
    else if (m[2]) out.push(<strong key={k} className="font-semibold">{inline(t.slice(2, -2), k)}</strong>);
    else if (m[3]) out.push(<em key={k}>{inline(t.slice(1, -1), k)}</em>);
    else { const mm = t.match(/^\[([^\]]+)\]\((.+)\)$/)!; out.push(<a key={k} href={mm[2]} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2">{mm[1]}</a>); }
    last = at + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

interface Item { text: string; ordered: boolean; children: Item[] }

function list(lines: string[], key: string): ReactNode {
  // Build a tree from indentation, then render it.
  const root: Item = { text: "", ordered: false, children: [] };
  const stack: { indent: number; node: Item }[] = [{ indent: -1, node: root }];
  for (const l of lines) {
    const m = l.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/)!;
    const item: Item = { text: m[3], ordered: /\d/.test(m[2]), children: [] };
    while (stack.length > 1 && stack[stack.length - 1].indent >= m[1].length) stack.pop();
    stack[stack.length - 1].node.children.push(item);
    stack.push({ indent: m[1].length, node: item });
  }
  const render = (items: Item[], k: string): ReactNode => {
    const Tag = items[0]?.ordered ? "ol" : "ul";
    return (
      <Tag key={k} className={`my-2 space-y-1 pl-6 ${Tag === "ol" ? "list-decimal" : "list-disc"}`}>
        {items.map((it, i) => <li key={`${k}-${i}`}>{inline(it.text, `${k}-${i}`)}{it.children.length > 0 && render(it.children, `${k}-${i}c`)}</li>)}
      </Tag>
    );
  };
  return render(root.children, key);
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    const key = `b${k++}`;
    if (!l.trim()) { i++; continue; }
    if (l.startsWith("```")) {
      const buf: string[] = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(<pre key={key} className="my-3 overflow-x-auto rounded border border-rule bg-sunken p-3 font-mono text-[13px] leading-5">{buf.join("\n")}</pre>);
      continue;
    }
    const h = l.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const lvl = h[1].length;
      out.push(<div key={key} className={lvl <= 2 ? "serif mb-1 mt-7 text-lead first:mt-0" : "mb-1 mt-5 font-semibold"}>{inline(h[2], key)}</div>);
      i++; continue;
    }
    if (/^\s*([-*_])\1{2,}\s*$/.test(l)) { out.push(<hr key={key} className="my-5 border-rule" />); i++; continue; }
    if (l.trim().startsWith("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const head = cells(l); i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(cells(lines[i++]));
      out.push(
        <div key={key} className="my-3 overflow-x-auto">
          <table className="w-full border-collapse text-[14px]">
            <thead><tr>{head.map((c, j) => <th key={j} className="border-b border-rule-strong px-2 py-1.5 text-left font-semibold">{inline(c, `${key}h${j}`)}</th>)}</tr></thead>
            <tbody>{rows.map((r, a) => <tr key={a}>{r.map((c, b) => <td key={b} className="border-b border-rule px-2 py-1.5 align-top">{inline(c, `${key}r${a}c${b}`)}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const buf: string[] = [];
      while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && buf.length))) {
        if (/^\s*([-*]|\d+\.)\s+/.test(lines[i])) buf.push(lines[i]); else buf[buf.length - 1] += " " + lines[i].trim();
        i++;
      }
      out.push(list(buf, key)); continue;
    }
    if (l.startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(<blockquote key={key} className="my-3 border-l-2 border-rule-strong pl-4 text-ink-2">{inline(buf.join(" "), key)}</blockquote>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|>|\s*([-*]|\d+\.)\s+|\s*\|)/.test(lines[i])) para.push(lines[i++]);
    if (!para.length) { para.push(lines[i++]); }
    out.push(<p key={key} className="my-2">{inline(para.join(" "), key)}</p>);
  }
  return <div className="text-[15px] leading-6">{out}</div>;
}
