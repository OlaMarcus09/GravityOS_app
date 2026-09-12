type BudgetAmounts = {
  planned_amount: string;
  actual_amount: string | null;
};

export function budgetProgress(items: BudgetAmounts[]) {
  const totals = items.reduce(
    (sum, item) => ({
      planned: sum.planned + (parseFloat(item.planned_amount) || 0),
      actual: sum.actual + (parseFloat(item.actual_amount ?? "0") || 0),
    }),
    { planned: 0, actual: 0 },
  );

  return {
    ...totals,
    percent: totals.planned > 0
      ? Math.min(100, Math.round((totals.actual / totals.planned) * 100))
      : 0,
    over: totals.actual > totals.planned && totals.planned > 0,
  };
}
