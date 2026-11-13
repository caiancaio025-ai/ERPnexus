/** Normalize old printed EST barcodes to the current short stock code. */
export function stockIdFromSearch(search: string): number | null {
  const match = /^EST\s*-\s*0*(\d+)\s*$/i.exec(search.trim());
  if (!match) return null;
  const id = Number(match[1]);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
