import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { Meter, RiskBadge, StockRiskDetail } from "../components/RiskParts";
import Select from "../components/Select";
import StockCompare from "../components/StockCompare";
import StockSearch from "../components/StockSearch";
import { formatCurrency, formatMoney, formatPeriodLabel } from "../utils/format";
import { REINVEST_LABEL } from "../utils/reinvest";
import { useStockRisk } from "../utils/risk";
import { GRAIN_LABELS, LAPSES, lapseStart, lapseVariation, periodVariations, sliceLapse } from "../utils/variation";

// Cubre el lapso más largo (1 año) más el cierre previo que sirve de base a la primera variación.
const HISTORY_DAYS = 400;
const fetchHistory = (symbol, type) => apiClient.get(`/api/history/${symbol}`, { params: { type, days: HISTORY_DAYS } });

const signed = (value) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
const trendClass = (value) => (value >= 0 ? "datil-up" : "datil-down");

// La sección (Acciones / Bonos y CETES) se elige en el menú lateral; ver moduleRegistry.
// `client`: solo cuando el admin opera en nombre de un cliente (el admin no tiene cartera propia).
export default function Trading({ section, client }) {
  const tab = section.id;
  const params = client ? { client } : undefined;
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
  // Alertas opcionales al comprar (% de pérdida y de ganancia); vacías = no se crea ninguna.
  const [reinvest, setReinvest] = useState("none"); // bonos: qué hacer al vencer
  const [amount, setAmount] = useState(1000); // bonos: se compran por monto, como en cetesdirecto
  const [quote, setQuote] = useState(null); // bonos: lo que se recibiría hoy al vender
  const [alertForm, setAlertForm] = useState({ loss: "", gain: "", indication: "aviso" });

  const loadOrders = () => {
    apiClient.get("/api/trading/orders", { params }).then(({ data }) => setOrders(data));
  };

  useEffect(() => {
    apiClient.get("/api/portfolio", { params }).then(({ data }) => {
      const owned = data.holdings.filter((h) => h.type === "accion");
      setHoldings(owned);
      if (owned[0]) setStockSymbol({ symbol: owned[0].symbol, name: owned[0].name });
    });
    apiClient.get("/api/trading/bonds").then(({ data }) => {
      setBonds(data);
      setBondSymbol(data[0]?.symbol ?? "");
    });
    loadOrders();
  }, [client]);

  const activeSymbol = tab === "accion" ? stockSymbol?.symbol : bondSymbol;

  // Antes de vender un bono se muestra el precio de mercado de hoy (como pide cetesdirecto).
  useEffect(() => {
    setQuote(null);
    if (tab !== "bono" || !bondSymbol || !(Number(quantity) > 0)) return;
    apiClient
      .get(`/api/trading/bonds/${bondSymbol}/quote`, { params: { quantity: Number(quantity), client } })
      .then(({ data }) => setQuote(data))
      .catch(() => setQuote(null));
  }, [tab, bondSymbol, quantity, orders]);
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
        quantity: tab === "bono" && action === "buy" ? undefined : Number(quantity),
        amount_mxn: tab === "bono" && action === "buy" ? Number(amount) : undefined,
        asset_type: tab,
        name: tab === "accion" ? stockSymbol?.name : undefined,
        reinvest: tab === "bono" && action === "buy" ? reinvest : undefined,
        client,
      });
      let alertInfo = "";
      if (action === "buy" && !client) {
        const wanted = [["loss", alertForm.loss], ["gain", alertForm.gain]].filter(([, percent]) => Number(percent) > 0);
        try {
          for (const [kind, percent] of wanted)
            await apiClient.post("/api/plan/alerts", { symbol, kind, percent: Number(percent), indication: alertForm.indication });
          if (wanted.length) alertInfo = " Alerta creada: la ves en Mi plan.";
        } catch {
          alertInfo = " No se pudo crear la alerta; puedes ponerla en Mi plan.";
        }
        setAlertForm({ loss: "", gain: "", indication: "aviso" });
      }
      const cashInfo = data.cash != null ? ` Efectivo disponible: ${formatCurrency(data.cash)}` : "";
      setMessage({ type: "ok", text: `${data.message}.${cashInfo}${alertInfo}` });
      fetchHistory(symbol, tab).then(({ data }) => setHistory(data));
      loadOrders();
    } catch (err) {
      setMessage({ type: "error", text: err.response?.data?.error ?? "Ocurrió un error." });
    }
  };

  const cancelOrder = async (orderId) => {
    try {
      await apiClient.post(`/api/trading/orders/${orderId}/cancel`, null, { params });
      loadOrders();
    } catch (err) {
      setMessage({ type: "error", text: err.response?.data?.error ?? "No se pudo cancelar la orden." });
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
        {tab === "bono" && (
          <label>
            Monto a invertir (mín. $100)
            <input type="number" min="100" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </label>
        )}
        <label>
          {tab === "bono" ? "Títulos a vender" : "Cantidad"}
          <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </label>
      </div>

      {tab === "bono" && bondUnitCost != null && Number(amount) > 0 && (
        <p className="datil-estimated-total">
          Con {formatCurrency(Number(amount))} compras unos <strong>{Math.floor(Number(amount) / bondUnitCost)} títulos</strong>
          <span className="datil-period-tag">
            {" "}
            a la tasa de la última subasta; el precio final es el de la subasta en que entre tu orden y lo que no alcance para un título queda
            en efectivo.
            {activeBond?.kind !== "bono_m" &&
              ` Al vencer recibirías ${formatCurrency(Math.floor(Number(amount) / bondUnitCost) * activeBond.nominal_value)}.`}
          </span>
        </p>
      )}
      {tab === "bono" && quote && (
        <p className="datil-estimated-total">
          {quote.error ? (
            <span className="datil-period-tag">{quote.error}</span>
          ) : (
            <>
              Si vendes {quantity} títulos hoy recibes <strong>{formatCurrency(quote.proceeds)}</strong>
              <span className={quote.realized_pnl_mxn >= 0 ? "datil-up" : "datil-down"}> ({formatCurrency(quote.realized_pnl_mxn)})</span>
              <span className="datil-period-tag"> a precio de mercado. Puedes vender {quote.sellable} títulos.</span>
            </>
          )}
        </p>
      )}

      {tab === "accion" && estimatedTotal != null && (
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
        <p className="datil-period-tag">
          Como en cetesdirecto: Banxico subasta los martes y liquida el jueves. Tu orden entra a la subasta del próximo martes si la
          registras a más tardar el lunes, y la puedes cancelar hasta ese día; necesitas el dinero en tu cuenta el día de la subasta. No
          todos los instrumentos se subastan cada semana: si no sale el tuyo, la orden no se ejecuta. Puedes vender antes a precio de
          mercado hasta 3 días hábiles antes del vencimiento: si las tasas subieron desde tu compra recibes menos, y si bajaron, más. Si lo
          mantienes hasta el final, recibes lo pactado.
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

      {tab === "bono" && (
        <div className="datil-form-row">
          <label className="datil-field-wide">
            Al vencer (solo al comprar)
            <select value={reinvest} onChange={(e) => setReinvest(e.target.value)}>
              {Object.entries(REINVEST_LABEL).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      {tab === "bono" && (
        <p className="datil-period-tag">
          Al vencer, la reinversión compra CETES a 28 días en la subasta de esa semana (mínimo 10 títulos; si no alcanza, queda en
          efectivo). En el Bono M también reinvierte cada cupón si eliges reinvertir todo. La orden aparece en Órdenes pendientes y la
          puedes cancelar o cambiar en tu cartera hasta 3 días hábiles antes del vencimiento.
        </p>
      )}
      {!client && (
        <div className="datil-form-row">
          <label>
            Avisarme si pierdo (%) <span className="datil-period-tag">opcional</span>
            <input type="number" min="0.1" step="0.1" value={alertForm.loss} onChange={(e) => setAlertForm({ ...alertForm, loss: e.target.value })} />
          </label>
          <label>
            Avisarme si gano (%) <span className="datil-period-tag">opcional</span>
            <input type="number" min="0.1" step="0.1" value={alertForm.gain} onChange={(e) => setAlertForm({ ...alertForm, gain: e.target.value })} />
          </label>
          <label>
            Indicación
            <select value={alertForm.indication} onChange={(e) => setAlertForm({ ...alertForm, indication: e.target.value })}>
              <option value="aviso">Solo avisar</option>
              <option value="vender">Considerar vender</option>
              <option value="comprar">Considerar comprar más</option>
            </select>
          </label>
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
                <th className="datil-col-num">Monto o títulos</th>
                <th>Subasta</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pendingOrders.map((order) => (
                <tr key={order.id}>
                  <td>
                    {order.symbol}
                    {order.source === "reinversión" && <span className="datil-period-tag"> · reinversión al vencer</span>}
                  </td>
                  <td className="datil-col-num">{order.amount_mxn != null ? `${formatCurrency(order.amount_mxn)}` : order.quantity}</td>
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
