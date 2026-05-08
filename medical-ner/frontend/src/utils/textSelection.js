/**
 * Expand text selection to include complete words
 * Ví dụ: Nếu bôi đen "Ch" trong "chào", sẽ mở rộng ra "chào"
 * @param {string} text - Full text content
 * @param {number} start - Start offset of selection
 * @param {number} end - End offset of selection
 * @returns {Object} - {newStart, newEnd} expanded to word boundaries
 */
export function expandToWordBoundaries(text, start, end) {
  if (!text || start < 0 || end > text.length || start > end) {
    return { newStart: start, newEnd: end };
  }

  // Characters that can be word separators
  // Bao gồm: whitespace, dấu câu, dấu đặc biệt (không bao gồm dấu tiếng Việt)
  const isSeparator = (char) => {
    if (!char) return true;
    // Whitespace
    if (/\s/.test(char)) return true;
    // Common punctuation (các dấu này không phải là phần của từ)
    if (/[.,!?;:()[\]{}<>\/\-–—*+=#&@$%^~`|\\"]/.test(char)) return true;
    return false;
  };

  // Expand left to word boundary
  let newStart = start;
  while (newStart > 0 && !isSeparator(text[newStart - 1])) {
    newStart--;
  }

  // Expand right to word boundary
  let newEnd = end;
  while (newEnd < text.length && !isSeparator(text[newEnd])) {
    newEnd++;
  }

  return { newStart, newEnd };
}

/**
 * Calculate offset from text container
 * Tính toán vị trí offset chính xác từ DOM selection
 * @param {HTMLElement} container - Text container element
 * @param {Range} range - DOM Range object
 * @returns {number} - Character offset from container start
 */
export function getOffsetFromContainer(container, range) {
  if (!container || !range) return 0;

  const beforeRange = document.createRange();
  beforeRange.setStart(container, 0);
  beforeRange.setEnd(range.startContainer, range.startOffset);

  return beforeRange.toString().length;
}

/**
 * Get expanded text selection with word boundaries
 * Lấy selection đã mở rộng với word boundaries
 * @param {HTMLElement} textRef - Reference to text container
 * @param {Range} range - DOM Range from selection
 * @param {string} fullText - Full text content
 * @returns {Object} - {rawText, expandedText, start, end} hoặc null nếu invalid
 */
export function getExpandedSelection(textRef, range, fullText) {
  if (!textRef || !range || !fullText) return null;

  const rawText = range.toString();
  if (!rawText) return null;

  // Calculate raw position
  const beforeRange = document.createRange();
  beforeRange.setStart(textRef, 0);
  beforeRange.setEnd(range.startContainer, range.startOffset);

  const rawStart = beforeRange.toString().length;
  const rawEnd = rawStart + rawText.length;

  // Trim and calculate trim offsets
  const trimmed = rawText.trim();
  if (!trimmed) return null;

  const leadingSpaces = rawText.length - rawText.trimStart().length;
  const trimmedStart = rawStart + leadingSpaces;
  const trimmedEnd = trimmedStart + trimmed.length;

  // Expand to word boundaries
  const { newStart, newEnd } = expandToWordBoundaries(fullText, trimmedStart, trimmedEnd);

  return {
    rawText,
    expandedText: fullText.slice(newStart, newEnd),
    start: newStart,
    end: newEnd,
    trimmedStart,
    trimmedEnd,
  };
}
