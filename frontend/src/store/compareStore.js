import { create } from "zustand";

const MAX_COMPARE = 5;

export const useCompareStore = create((set, get) => ({
  selected: [], // [{ scheme_code, fund_name, category }]
  add: (fund) => {
    const { selected } = get();
    if (selected.length >= MAX_COMPARE) return false;
    if (selected.find((f) => f.scheme_code === fund.scheme_code)) return false;
    set({ selected: [...selected, fund] });
    return true;
  },
  remove: (schemeCode) =>
    set((s) => ({ selected: s.selected.filter((f) => f.scheme_code !== schemeCode) })),
  clear: () => set({ selected: [] }),
}));
