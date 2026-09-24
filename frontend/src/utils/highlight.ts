/**
 * 文本高亮工具（P3：#10 引用片段原文高亮）
 * 从用户问题中提取关键词，在引用片段中高亮显示
 */

// 转义 HTML，防止脏数据注入
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 从问题文本中提取关键词（2-4字中文窗口 + 英文单词），
 * 只保留确实出现在引用片段中的词，避免高亮无意义内容。
 */
export function extractKeywords(question: string, quote: string, max = 6): string[] {
  const lowQuote = quote.toLowerCase()

  // 去空白与常见标点（保留中英文）
  const q = question
    .replace(/\s+/g, '')
    .replace(/[\u3000-\u303f\uff00-\uffef"'“”‘’《》【】…—·，。；：、？！（）]/g, '')

  if (!q) return []

  const candidates = new Set<string>()

  // 英文单词（≥2字符）整体成为候选词
  const enWords = q.match(/[A-Za-z0-9]{2,}/g) || []
  enWords.forEach(w => candidates.add(w))

  // 中文滑动窗口：4字 → 2字
  const zh = q.replace(/[A-Za-z0-9]+/g, ' ')
  for (let len = 4; len >= 2; len--) {
    for (let i = 0; i + len <= zh.length; i++) {
      const seg = zh.slice(i, i + len)
      if (/^[\u4e00-\u9fa5]+$/.test(seg)) {
        candidates.add(seg)
      }
    }
  }

  // 只保留确实出现在引用片段中的词
  const matched: string[] = []
  for (const kw of candidates) {
    if (kw.length >= 2 && lowQuote.includes(kw.toLowerCase())) {
      matched.push(kw)
    }
  }

  // 长词优先，其次按在引用中的出现位置排序（保证高亮稳定可预期）
  matched.sort((a, b) => b.length - a.length || lowQuote.indexOf(a) - lowQuote.indexOf(b))

  // 剔除被更长关键词包含的词（避免 <mark> 嵌套）
  const result: string[] = []
  for (const kw of matched) {
    if (!result.some(r => r.includes(kw))) {
      result.push(kw)
    }
    if (result.length >= max) break
  }
  return result
}

/**
 * 高亮引用片段，返回 HTML（用 <mark> 包裹关键词）
 */
export function highlightQuote(quote: string, question: string): string {
  const escaped = escapeHtml(quote)
  if (!question) return escaped

  const keywords = extractKeywords(question, quote)
  if (keywords.length === 0) return escaped

  // 关键词转义正则特殊字符，长词优先防止部分覆盖
  const pattern = keywords
    .map(kw => kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .sort((a, b) => b.length - a.length)
    .join('|')

  return escaped.replace(new RegExp(`(${pattern})`, 'gi'), '<mark class="kw-hl">$1</mark>')
}