#!/usr/bin/env node
// Ports the approved design (design/canvas/*.dc.html) to React components so the markup and styles match the design
// exactly. The design stays the source of truth: re-run this script (npm run port) whenever design/canvas changes.
//
// Each .dc.html has plain HTML with inline styles plus a small template syntax:
//   {{expr}}                      -> {v.expr}              (v = the screen's values object)
//   <sc-if value="{{x}}">         -> {v.x && (...)}
//   <sc-for list="{{xs}}" as="d"> -> {v.xs.map((d) => ...)}
//   style="{{d.style}}"           -> style={css(v.d.style)} (the design's renderVals returns CSS strings)
// Static placeholder text in the design (for example "1,240 pts" or "[name]") is replaced by values from real data
// through the BINDINGS below. Nothing else is changed. Output: src/design/generated/*.tsx and src/design/design.css.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { parseDocument } from 'htmlparser2';

const root = path.resolve(import.meta.dirname, '..');
const canvas = path.resolve(root, '..', 'design', 'canvas');
const outDir = path.join(root, 'src', 'design', 'generated');
mkdirSync(outDir, { recursive: true });

const SCREENS = { Loading: 'Loading', Main: 'Home', Traveled: 'Traveled', Explore: 'Explore', Faves: 'Faves', Profile: 'Profile' };
const ROUTES = { 'Loading.dc.html': '#/loading', 'Main.dc.html': '#/home', 'Traveled.dc.html': '#/traveled', 'Explore.dc.html': '#/explore', 'Faves.dc.html': '#/faves', 'Profile.dc.html': '#/profile' };

// Static placeholder text/attributes in the design that must come from real data. Expressions use v.<name>.
const BINDINGS = {
  Explore: {
    wrapIf: [['{{p.promo}}', 'p.promo'], ['{{p.why}}', 'p.why']],
  },
  Main: {
    text: [['[your', '{{avatarInitial}}'], ['avatar]', ''], ['hey [name]!', 'hey {{name}}!'], ['1,240 pts · 260 to Patriot', '{{pointsLine}}'], ['Boston Lobstah', '{{rankName}}']],
    attrs: [['d', 'M8 9H200', '`M8 9H${v.barX}`'], ['cx', '200', 'v.barX'], ['href', '#', 'v.learnHref']],
  },
  Traveled: {
    exact: [['16', '{{totalMiles}}'], ['10', '{{milesGreen}}'], ['5', '{{milesRed}}'], ['1', '{{milesBlue}}'], ['0', '{{milesOrange}}']],
    text: [['7 unlocked!', '{{unlockedCount}} unlocked!'], ['unlocked · {{spot.facts}} facts · near {{spot.stop}}', '{{spotLine}}']],
  },
  Profile: {
    text: [['[Rank avatar: your Boston Lobstah drawing]', '{{rankName}}'], ['@[username] · Boston Lobstah', '@{{username}} · {{rankName}}'], ['@[username]', '@{{username}}'],
      ['[#0042]', ''], ['· 260 to Patriot!', '{{toNext}}'], ['Your Boston Lobstah perks', 'Your {{rankName}} perks'], ['Boston Lobstah', '{{rankName}}']],
    exact: [['1,240', '{{pointsText}}']],
  },
};

const VOID = new Set(['br', 'hr', 'img', 'input']);
const camel = (n) => (n.startsWith('aria-') || n.startsWith('data-') ? n : n.replace(/-([a-z])/g, (_, c) => c.toUpperCase()));
const ATTR = { class: 'className', for: 'htmlFor' };

function expr(raw, loopVars) {
  const e = raw.trim();
  const root = e.split(/[.[]/)[0];
  return loopVars.includes(root) ? e : `v.${e}`;
}

// "text {{a}} more {{b.c}}" -> JS template literal or single expression
function template(str, loopVars) {
  const parts = str.split(/(\{\{[^}]*\}\})/).filter((p) => p !== '');
  if (parts.length === 1 && parts[0].startsWith('{{')) return expr(parts[0].slice(2, -2), loopVars);
  return '`' + parts.map((p) => (p.startsWith('{{') ? '${' + expr(p.slice(2, -2), loopVars) + '}' : p.replace(/[`\\$]/g, '\\$&'))).join('') + '`';
}

function styleObject(s) {
  const decls = s.split(';').map((d) => d.trim()).filter(Boolean).map((d) => {
    const i = d.indexOf(':');
    return `${JSON.stringify(camel(d.slice(0, i).trim()))}: ${JSON.stringify(d.slice(i + 1).trim())}`;
  });
  return `{{ ${decls.join(', ')} }}`;
}

function convert(node, ctx) {
  if (node.type === 'text') return text(node.data, ctx);
  if (node.type === 'comment') return '';
  if (node.type !== 'tag') return '';
  const name = node.name;
  const loop = ctx.loop;
  if (name === 'sc-if') {
    const cond = template(node.attribs.value, loop);
    return `{${cond} && (<>${kids(node, ctx)}</>)}`;
  }
  if (name === 'sc-for') {
    const list = template(node.attribs.list, loop);
    const as = node.attribs.as;
    return `{(${list} as any[]).map((${as}: any, __i${loop.length}) => (<Fragment key={__i${loop.length}}>${kids(node, { ...ctx, loop: [...loop, as] })}</Fragment>))}`;
  }
  if (name === 'helmet' || name === 'script' || name === 'style' || name === 'link') return '';
  const attrs = [];
  for (const [k, val] of Object.entries(node.attribs)) {
    if (k.startsWith('hint-')) continue;
    const bound = (ctx.bind.attrs || []).find((b) => b[0] === k && b[1] === val);
    const key = ATTR[k] || camel(k);
    if (bound) { attrs.push(`${key}={${bound[2]}}`); continue; }
    if (k === 'style') {
      attrs.push(val.includes('{{') ? `style={css(${template(val, loop)})}` : `style=${styleObject(val)}`);
    } else if (k === 'href' && ROUTES[val]) {
      attrs.push(`href="${ROUTES[val]}"`);
    } else if (k === 'href' && val === '#') {
      attrs.push('href="#" onClick={(e) => e.preventDefault()}');
    } else if (val.includes('{{')) {
      attrs.push(`${key}={${template(val, loop)}}`);
    } else if (k === 'onClick') {
      attrs.push(`${key}={${val}}`);
    } else {
      attrs.push(`${key}=${JSON.stringify(val)}`);
    }
  }
  const open = `<${name}${attrs.length ? ' ' + attrs.join(' ') : ''}`;
  if (VOID.has(name)) return `${open} />`;
  const inner = kids(node, ctx);
  const jsx = inner ? `${open}>${inner}</${name}>` : `${open} />`;
  // hide an element whose own text is an empty placeholder (see WRAP_IF)
  const w = (ctx.bind.wrapIf || []).find((b) => (node.children || []).some((c) => c.type === 'text' && c.data.includes(b[0])));
  return w ? `{${expr(w[1], loop)} && (${jsx})}` : jsx;
}

function kids(node, ctx) {
  return (node.children || []).map((c) => convert(c, ctx)).join('');
}

function text(data, ctx) {
  let t = data;
  if (!t.trim() && /\n/.test(t)) return '';
  const ex = (ctx.bind.exact || []).findIndex((b) => !b[2] && b[0] === t.trim());
  if (ex >= 0) { const b = ctx.bind.exact[ex]; b[2] = true; return finishText(b[1], ctx); }
  for (const [find, repl] of ctx.bind.text || []) if (t.includes(find)) { t = t.split(find).join(repl); }
  t = t.replace(/\s+/g, ' ');
  if (/\n/.test(data)) t = t.trim();
  return finishText(t, ctx);
}

function finishText(t, ctx) {
  if (!t) return '';
  const parts = t.split(/(\{\{[^}]*\}\})/).filter((p) => p !== '');
  return parts.map((p) => (p.startsWith('{{') ? `{${expr(p.slice(2, -2), ctx.loop)}}` : `{${JSON.stringify(p)}}`)).join('');
}

const cssSeen = new Set();
const cssOut = [];
for (const [file, comp] of Object.entries(SCREENS)) {
  const src = readFileSync(path.join(canvas, `${file}.dc.html`), 'utf8');
  const m = src.match(/<x-dc>([\s\S]*?)<\/x-dc>/);
  if (!m) throw new Error(`no <x-dc> in ${file}`);
  const doc = parseDocument(m[1], { lowerCaseTags: false, lowerCaseAttributeNames: false, recognizeSelfClosing: true });
  const styleText = (m[1].match(/<style>([\s\S]*?)<\/style>/) || [])[1] || '';
  for (const line of styleText.split('\n').map((l) => l.trim()).filter(Boolean)) if (!cssSeen.has(line)) { cssSeen.add(line); cssOut.push(line); }
  const bindSrc = BINDINGS[file] || {};
  const bind = { text: bindSrc.text || [], attrs: bindSrc.attrs || [], wrapIf: bindSrc.wrapIf || [], exact: (bindSrc.exact || []).map((b) => [b[0], b[1], false]) };
  const body = (doc.children || []).map((c) => convert(c, { loop: [], bind })).join('');
  const unused = bind.exact.filter((b) => !b[2]).map((b) => b[0]);
  if (unused.length) throw new Error(`${file}: exact bindings not found: ${unused.join(', ')}`);
  const tsx = `// GENERATED by scripts/port-design.mjs from design/canvas/${file}.dc.html. Do not edit by hand.
// @ts-nocheck
/* eslint-disable */
import { Fragment } from 'react';
import { css } from '../../css';

export default function ${comp}Markup({ v }: { v: any }) {
  return (<>${body}</>);
}
`;
  writeFileSync(path.join(outDir, `${comp}Markup.tsx`), tsx);
  console.log(`ported ${file}.dc.html -> ${comp}Markup.tsx`);
}
writeFileSync(path.join(root, 'src', 'design', 'design.css'), `/* GENERATED from the helmet styles in design/canvas/*.dc.html */\n${cssOut.join('\n')}\n`);
