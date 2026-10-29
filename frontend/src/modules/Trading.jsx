import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { Meter, RiskBadge, StockRiskDetail } from "../components/RiskParts";
import Select from "../components/Select";
import StockCompare from "../components/StockCompare";
import StockSearch from "../components/StockSearch";
import { formatCurrency, formatMoney, formatPeriodLabel } from "../utils/format";
import { useStockRisk } from "../utils/risk";
import { GRAIN_LABELS, LAPSES, lapseStart, lapseVariation, periodVariations, sliceLapse } from "../utils/variation";

// Cubre el lapso más largo (1 año) más el cierre previo que sirve de base a la primera variación.
const HISTORY_DAYS = 400;
const fetchHistory = (symbol, type) => apiClient.get(`/api/history/${symbol}`, { params: { type, days: HISTORY_DAYS } });

const signed = (value) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
const trendClass = (value) => (value >= 0 ? "datil-up" : "datil-down");

// La sección (Acciones / Bonos y CETES) se elige en el menú lateral; ver moduleRegistry.
export default function Trading({ section }) {
  const tab = section.id;
  const [holdings, setHoldings] = useState([]);
  const [bonds, setBonds] = useState([]);
  const [orders, setOrders] = useState([]);
  const [stockSymbol, setStockSymbol] = useState(null);
  const [bondSymbol, setBondSymbol] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [message, setMessage] = useState(null);
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState("");
  const [lapseId, setLapseId] = useState("1M");
  const [chosenGrain, setChosenGrain] = useState("dia");

  const loadOrders = () => {
    apiClient.get("/api/trading/orders").then(({ data }) => setOrders(data));
  };

  useEffect(() => {
    apiClient.get("/api/portfolio").then(({ data }) => {
      const owned = data.holdings.filter((h) => h.type === "accion");
      setHoldings(owned);
      if (owned[0]) setStockSymbol({ symbol: owned[0].symbol, name: owned[0].name });
    });
    apiClient.get("/api/trading/bonds").then(({ data }) => {
      setBonds(data);
      setBondSymbol(data[0]?.symbol ?? "");
    });
    loadOrders();
  }, []);

  const activeSymbol = tab === "accion" ? stockSymbol?.symbol : bondSymbol;
  const activeBond = bonds.find((b) => b.symbol === bondSymbol);

  useEffect(() => {
    if (!activeSymbol) return;
    setHistoryError("");
    setHistory(null);
    fetchHistory(activeSymbol, tab)
      .then(({ data }) => setHistory(data))
      .catch(() => setHistoryError("No se pudo obtener el histórico de este activo."));
  }, [activeSymbol, tab]);

  const submit = async (action) => {
    const symbol = tab === "accion" ? stockSymbol?.symbol : bondSymbol;
    if (!symbol) {
      setMessage({ type: "error", text: "Selecciona un activo primero." });
      return;
    }

    setMessage(null);
    try {
      const { data } = await apiClient.post(`/api/trading/${action}`, {
        symbol,
        quantity: Number(quantity),
        asset_type: tab,
        name: tab === "accion" ? stockSymbol?.name : undefined,
      });
      const cashInfo = data.cash != null ? ` Efectivo disponible: ${formatCurrency(data.cash)}` : "";
      setMessage({ type: "ok", text: `${data.message}.${cashInfo}` });
      fetchHistory(symbol, tab).then(({ data }) => setHistory(data));
      loadOrders();
    } catch (err) {
      setMessage({ type: "error", text: err.response?.data?.error ?? "Ocurrió un error." });
    }
  };

  const cancelOrder = async (orderId) => {
    try {
      await apiClient.post(`/api/trading/orders/${orderId}/cancel`);
      loadOrders();
    } catch {
      setMessage({ type: "error", text: "No se pudo cancelar la orden." });
    }
  };

  const bondOptions = bonds.map((b) => ({ value: b.symbol, label: `${b.symbol} · ${b.name}` }));
  const isUp = (history?.current?.change_percent ?? 0) >= 0;
  // En bonos, history.current.price es la tasa vigente (%), no un precio. Un CETE se compra con
  // descuento (nominal / (1 + tasa * dias/360)); el Bono M se compra a la par y paga cupones.
  const bondRate = tab === "bono" ? history?.current?.price : null;
  const bondUnitCost =
    activeBond && bondRate != null && activeBond.kind !== "bono_m"
      ? activeBond.nominal_value / (1 + (bondRate / 100) * (activeBond.term_days / 360))
      : activeBond?.nominal_value;
  const unitPrice = tab === "accion" ? history?.current?.price : bondUnitCost;
  const estimatedTotal = unitPrice != null && quantity > 0 ? unitPrice * Number(quantity) : null;
  // Las acciones cotizan en la moneda de su bolsa; el dinero de la cuenta es en pesos.
  const stockCurrency = tab === "accion" ? history?.current?.currency : null;
  const stockInForeignCurrency = stockCurrency != null && stockCurrency !== "MXN";
  const fxMxn = history?.fx_mxn;
  const pendingOrders = orders.filter((o) => o.status === "pending");

  // Lapso elegido: la gráfica y las variaciones salen de los mismos puntos (ver utils/variation.js).
  const points = history?.history ?? [];
  const lapse = LAPSES.find((l) => l.id === lapseId);
  const grain = lapse.grains.includes(chosenGrain) ? chosenGrain : lapse.grains[0];
  const from = points.length ? lapseStart(points.at(-1).date, lapse) : null;
  const chartData = from ? sliceLapse(points, from) : [];
  const rows = from ? periodVariations(points, grain, { from }).reverse() : [];
  const lapseChange = from ? lapseVariation(points, from) : null;
  const risk = useStockRisk(tab === "accion" ? stockSymbol?.symbol : null);
  // En bonos el "precio" es la tasa vigente: sus cambios son puntos porcentuales (pp), no dinero.
  const isBond = tab === "bono";
  const formatLevel = (value) => (isBond ? `${value.toFixed(2)}%` : formatMoney(value, stockCurrency));
  const formatDelta = (value) => `${value > 0 ? "+" : ""}${isBond ? `${value.toFixed(2)} pp` : formatMoney(value, stockCurrency)}`;
  const formatPercent = (value) => (value == null ? "N/D" : `${signed(value)}%`);
  const hasPartialRows = rows.some((r) => r.partialStart || r.partialEnd);

  return (
    <section className="datil-card">
      <h2>Comprar / Vender · {section.name}</h2>

      <div className="datil-form-row">
        <label className="datil-field-wide">
          Activo
          {tab === "accion" ? (
            <StockSearch onSelect={setStockSymbol} placeholder="Ej. Apple, Tesla, tecnología..." />
          ) : (
            <Select value={bondSymbol} options={bondOptions} onChange={setBondSymbol} />
          )}
        </label>
        <label>
          Cantidad
          <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </label>
      </div>

      {estimatedTotal != null && (
        <p className="datil-estimated-total">
          Total estimado:{" "}
          <strong>{stockInForeignCurrency && fxMxn ? formatCurrency(estimatedTotal * fxMxn) : formatCurrency(estimatedTotal)}</strong>
          {stockInForeignCurrency && (
            <span className="datil-period-tag">
              {" "}
              ({formatMoney(estimatedTotal, stockCurrency)}
              {fxMxn ? ` a ${stockCurrency}/MXN ${fxMxn}` : ""})
            </span>
          )}
          {tab === "bono" && activeBond?.kind !== "bono_m" && activeBond && (
            <span className="datil-period-tag">
              {" "}
              (con descuento; al vencer recibes {formatCurrency(activeBond.nominal_value * Number(quantity))})
            </span>
          )}
          {tab === "bono" && activeBond?.kind === "bono_m" && (
            <span className="datil-period-tag"> (a la par; paga cupón cada {activeBond.coupon_days} días)</span>
          )}
        </p>
      )}

      {tab === "bono" && activeBond && (
        <p className="datil-label">
          Este bono solo se subasta los lunes. Si compras otro día, se agenda una orden para el próximo lunes.
          La tasa se fija al comprar. Si lo vendes antes de vencer se paga a precio de mercado: si las tasas
          subieron desde tu compra recibes menos, y si bajaron, más. Si lo mantienes hasta el final, recibes lo
          pactado.
        </p>
      )}

      {tab === "accion" && holdings.length > 0 && (
        <div className="datil-quick-picks">
          <span className="datil-label">En tu cartera</span>
          <div className="datil-quick-pick-list">
            {holdings.map((h) => (
              <button
                key={h.symbol}
                className={h.symbol === stockSymbol?.symbol ? "datil-chip active" : "datil-chip"}
                onClick={() => setStockSymbol({ symbol: h.symbol, name: h.name })}
              >
                {h.symbol}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="datil-actions">
        <button className="datil-btn datil-btn-primary" onClick={() => submit("buy")}>
          Comprar
        </button>
        <button className="datil-btn datil-btn-secondary" onClick={() => submit("sell")}>
          Vender
        </button>
      </div>
      {message && <p className={message.type === "ok" ? "datil-success" : "datil-error"}>{message.text}</p>}

      {historyError && <p className="datil-error">{historyError}</p>}

      {history && (
        <>
          <div className="datil-history-summary">
            <div>
              <span className="datil-label">Precio actual</span>
              <strong>{tab === "accion" ? formatMoney(history.current.price, stockCurrency) : history.current.price}</strong>
            </div>
            <div>
              <span className="datil-label">{formatPeriodLabel(history.current.change_period)}</span>
              <strong className={isUp ? "datil-up" : "datil-down"}>
                {isUp ? "\u25B2" : "\u25BC"} {history.current.change_percent}%
              </strong>
            </div>
            {tab === "accion" && !risk.forbidden && (
              <div>
                <span className="datil-label">Riesgo</span>
                {risk.data ? (
                  <>
                    <strong>
                      <RiskBadge level={risk.data.level} score={risk.data.score} />
                    </strong>
                    <Meter score={risk.data.score} />
                  </>
                ) : (
                  <strong className="datil-period-tag" title={risk.error}>
                    {risk.loading ? "Calculando..." : "No disponible"}
                  </strong>
                )}
              </div>
            )}
          </div>

          <div className="datil-lapse-bar" role="group" aria-label="Lapso">
            {LAPSES.map((l) => (
              <button
                key={l.id}
                className={l.id === lapse.id ? "datil-chip active" : "datil-chip"}
                aria-pressed={l.id === lapse.id}
                onClick={() => setLapseId(l.id)}
              >
                {l.label}
              </button>
            ))}
            {lapseChange && (
              <span className="datil-lapse-change">
                <span className="datil-label">En {lapse.label}</span>{" "}
                <strong className={trendClass(lapseChange.change)}>
                  {lapseChange.change >= 0 ? "\u25B2" : "\u25BC"} {formatPercent(lapseChange.percent)} · {formatDelta(lapseChange.change)}
                </strong>
              </span>
            )}
          </div>

          <div className="datil-chart-wrapper">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={70} />
                <Tooltip />
                <Line type="monotone" dataKey="close" stroke="var(--datil-accent)" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <h3 className="datil-subheading">Variación por periodo</h3>
          <div className="datil-lapse-bar" role="group" aria-label="Periodo">
            {lapse.grains.map((g) => (
              <button
                key={g}
                className={g === grain ? "datil-chip active" : "datil-chip"}
                aria-pressed={g === grain}
                onClick={() => setChosenGrain(g)}
              >
                {GRAIN_LABELS[g]}
              </button>
            ))}
          </div>
          {rows.length === 0 ? (
            <p className="datil-period-tag">Sin datos suficientes en este lapso.</p>
          ) : (
            <div className="datil-table-scroll">
              <table className="datil-table">
                <thead>
                  <tr>
                    <th>Periodo</th>
                    <th className="datil-col-num">Var. %</th>
                    <th className="datil-col-num">{isBond ? "Var. (pp)" : "Var. valor"}</th>
                    <th className="datil-col-num">{isBond ? "Tasa al cierre" : "Cierre"}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.start}>
                      <td>
                        {r.label}
                        {r.partialStart && (
                          <span className="datil-period-tag" title="El periodo empezó antes del lapso: solo cuenta desde el inicio del lapso">
                            {" "}
                            · parcial
                          </span>
                        )}
                        {r.partialEnd && (
                          <span className="datil-period-tag" title="El periodo aún no termina">
                            {" "}
                            · en curso
                          </span>
                        )}
                      </td>
                      <td className={`datil-col-num ${trendClass(r.change)}`}>{formatPercent(r.percent)}</td>
                      <td className={`datil-col-num ${trendClass(r.change)}`}>{formatDelta(r.change)}</td>
                      <td className="datil-col-num">{formatLevel(r.close)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="datil-period-tag">
            Cada variación compara el cierre del periodo contra el cierre del periodo anterior
            {hasPartialRows ? "; en los periodos parciales o en curso solo cuenta la parte que cae dentro del lapso" : ""}.
          </p>

          {tab === "accion" && risk.data && (
            <details className="datil-risk-details">
              <summary>Detalle del riesgo</summary>
              <StockRiskDetail data={risk.data} />
            </details>
          )}

          {tab === "accion" && !risk.forbidden && (
            <details className="datil-risk-details">
              <summary>Comparar con otras acciones</summary>
              <StockCompare key={activeSymbol} initial={[activeSymbol]} />
            </details>
          )}
        </>
      )}

      {pendingOrders.length > 0 && (
        <div className="datil-pending-orders">
          <h3 className="datil-subheading">Órdenes pendientes</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Símbolo</th>
                <th className="datil-col-num">Títulos</th>
                <th>Se ejecuta el</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pendingOrders.map((order) => (
                <tr key={order.id}>
                  <td>{order.symbol}</td>
                  <td className="datil-col-num">{order.quantity}</td>
                  <td>{order.scheduled_date}</td>
                  <td className="datil-col-num">
                    <button className="datil-btn datil-btn-secondary" onClick={() => cancelOrder(order.id)}>
                      Cancelar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
