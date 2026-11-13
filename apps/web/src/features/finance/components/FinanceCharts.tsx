import type { CashFlowPoint } from "../types";

type CashFlowChartProps = {
  points: CashFlowPoint[];
  title?: string;
  subtitle?: string;
};

type CompositionDonutProps = {
  income: number;
  expense: number;
};

const formatCompactMoney = (value: number) => new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
}).format(value);

const formatMoney = (value: number) => new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
}).format(value);

function buildPolyline(values: number[], width: number, height: number, min: number, max: number) {
  if (!values.length) return "";
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values.map((value, index) => {
    const x = values.length > 1 ? step * index : width / 2;
    const y = height - ((value - min) / range) * height;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

export function CashFlowChart({
  points,
  title = "Evolução do fluxo de caixa",
  subtitle = "Receitas, saídas e saldo projetado no período selecionado.",
}: CashFlowChartProps) {
  const chartWidth = 880;
  const chartHeight = 240;
  const plotTop = 18;
  const plotHeight = 184;
  const plotBottom = plotTop + plotHeight;

  if (!points.length) {
    return <section className="finance-chart finance-chart--empty" aria-label={title}>
      <header><div><span>ANÁLISE VISUAL</span><h3>{title}</h3><p>{subtitle}</p></div></header>
      <div className="finance-chart-empty">Sem dados suficientes para montar o gráfico neste período.</div>
    </section>;
  }

  const allValues = points.flatMap((point) => [point.income, point.expense, point.balance]);
  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(0, ...allValues);
  const paddedMin = minValue < 0 ? minValue * 1.08 : 0;
  const paddedMax = maxValue > 0 ? maxValue * 1.08 : 1;

  const incomeLine = buildPolyline(points.map((point) => point.income), chartWidth, plotHeight, paddedMin, paddedMax);
  const expenseLine = buildPolyline(points.map((point) => point.expense), chartWidth, plotHeight, paddedMin, paddedMax);
  const balanceLine = buildPolyline(points.map((point) => point.balance), chartWidth, plotHeight, paddedMin, paddedMax);
  const zeroY = plotTop + plotHeight - ((0 - paddedMin) / (paddedMax - paddedMin || 1)) * plotHeight;
  const step = points.length > 1 ? chartWidth / (points.length - 1) : 0;
  const gridTicks = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    return {
      y: plotTop + plotHeight * ratio,
      value: paddedMax - (paddedMax - paddedMin) * ratio,
    };
  });

  return <section className="finance-chart" aria-label={title}>
    <header className="finance-chart__header">
      <div><span>ANÁLISE VISUAL</span><h3>{title}</h3><p>{subtitle}</p></div>
      <div className="finance-chart-legend" aria-label="Legenda do gráfico">
        <span className="income"><i/>Receitas</span>
        <span className="expense"><i/>Saídas</span>
        <span className="balance"><i/>Saldo</span>
      </div>
    </header>

    <div className="finance-chart__viewport">
      <svg className="finance-chart__svg" viewBox={`-74 0 ${chartWidth + 92} ${chartHeight}`} role="img" aria-label={`${title}. ${points.length} períodos exibidos.`}>
        {gridTicks.map((tick) => <g key={tick.y} className="finance-chart-axis">
          <line x1="0" x2={chartWidth} y1={tick.y} y2={tick.y}/>
          <text x="-10" y={tick.y + 4} textAnchor="end">{formatCompactMoney(tick.value)}</text>
        </g>)}
        {paddedMin < 0 && <line className="finance-chart-zero" x1="0" x2={chartWidth} y1={zeroY} y2={zeroY}/>} 

        <polyline className="finance-chart-line finance-chart-line--income" points={incomeLine} transform={`translate(0 ${plotTop})`}/>
        <polyline className="finance-chart-line finance-chart-line--expense" points={expenseLine} transform={`translate(0 ${plotTop})`}/>
        <polyline className="finance-chart-line finance-chart-line--balance" points={balanceLine} transform={`translate(0 ${plotTop})`}/>

        {points.map((point, index) => {
          const x = points.length > 1 ? step * index : chartWidth / 2;
          const showLabel = points.length <= 8 || index === 0 || index === points.length - 1 || index % Math.ceil(points.length / 7) === 0;
          return <g key={`${point.label}-${index}`}>
            {showLabel && <text className="finance-chart-label" x={x} y={chartHeight - 8} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}>{point.label}</text>}
          </g>;
        })}
      </svg>
    </div>
  </section>;
}

export function CompositionDonut({ income, expense }: CompositionDonutProps) {
  const safeIncome = Math.max(0, income);
  const safeExpense = Math.max(0, expense);
  const total = safeIncome + safeExpense;
  const incomePercent = total > 0 ? safeIncome / total * 100 : 0;
  const expensePercent = total > 0 ? safeExpense / total * 100 : 0;
  const result = income - expense;

  return <article className="finance-donut">
    <div className="finance-donut__graphic" aria-label={`Composição do período: ${incomePercent.toFixed(1)}% receitas e ${expensePercent.toFixed(1)}% saídas.`}>
      <svg viewBox="0 0 120 120" role="img">
        <circle className="finance-donut__track" cx="60" cy="60" r="46"/>
        {total > 0 && <>
          <circle className="finance-donut__slice finance-donut__slice--income" cx="60" cy="60" r="46" pathLength="100" strokeDasharray={`${incomePercent} ${100 - incomePercent}`}/>
          <circle className="finance-donut__slice finance-donut__slice--expense" cx="60" cy="60" r="46" pathLength="100" strokeDasharray={`${expensePercent} ${100 - expensePercent}`} strokeDashoffset={-incomePercent}/>
        </>}
      </svg>
      <div className="finance-donut__center"><small>Resultado</small><strong className={result >= 0 ? "amount-positive" : "amount-negative"}>{formatCompactMoney(result)}</strong></div>
    </div>
    <div className="finance-donut-legend">
      <div><span className="income"><i/>Receitas</span><strong>{formatMoney(income)}</strong><small>{incomePercent.toFixed(1)}% do movimento</small></div>
      <div><span className="expense"><i/>Saídas</span><strong>{formatMoney(expense)}</strong><small>{expensePercent.toFixed(1)}% do movimento</small></div>
    </div>
  </article>;
}
