import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import Select from "../components/Select";
import StockSearch from "../components/StockSearch";
import { formatCurrency, formatPeriodLabel } from "../utils/format";

const TABS = [
  { id: "accion", label: "Acciones" },
  { id: "bono", label: "Bonos y CETES" },
];

export default function Trading() {
  const [tab, setTab] = useState("accion");
  const [holdings, setHoldings] = useState([]);
  const [bonds, setBonds] = useState([]);
  const [orders, setOrders] = useState([]);
  const [stockSymbol, setStockSymbol] = useState(null);
  const [bondSymbol, setBondSymbol] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [message, setMessage] = useState(null);
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState("");

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
    apiClient
      .get(`/api/history/${activeSymbol}`, { params: { type: tab } })
      .then(({ data }) => setHistory(data))
      .catch(() => setHistoryError("No se pudo obtener el historico de este activo."));
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
      apiClient.get(`/api/history/${symbol}`, { params: { type: tab } }).then(({ data }) => setHistory(data));
      loadOrders();
    } catch (err) {
      setMessage({ type: "error", text: err.response?.data?.error ?? "Ocurrio un error." });
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
  const chartData = useMemo(() => history?.history ?? [], [history]);
  const isUp = (history?.current?.change_percent ?? 0) >= 0;
  const unitPrice = tab === "accion" ? history?.current?.price : activeBond?.nominal_value;
  const estimatedTotal = unitPrice != null && quantity > 0 ? unitPrice * Number(quantity) : null;
  const pendingOrders = orders.filter((o) => o.status === "pending");

  return (
    <section className="datil-card">
      <h2>Comprar / Vender</h2>
      <div className="datil-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "datil-tab active" : "datil-tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="datil-form-row">
        <label className="datil-field-wide">
          Activo
          {tab === "accion" ? (
            <StockSearch onSelect={setStockSymbol} placeholder="Ej. Apple, Tesla, tecnologia..." />
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
          Total estimado: <strong>{formatCurrency(estimatedTotal)}</strong>
          {tab === "bono" && <span className="datil-period-tag"> (valor nominal, no incluye rendimiento)</span>}
        </p>
      )}

      {tab === "bono" && activeBond && (
        <p className="datil-label">
          Este bono solo se subasta los lunes. Si compras otro dia, se agenda una orden para el proximo lunes.
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

      {historyError && <p className="datil-error">{historyError}</p>}

      {history && (
        <>
          <div className="datil-history-summary">
            <div>
              <span className="datil-label">Precio actual</span>
              <strong>{history.current.price}</strong>
            </div>
            <div>
              <span className="datil-label">{formatPeriodLabel(history.current.change_period)}</span>
              <strong className={isUp ? "datil-up" : "datil-down"}>
                {isUp ? "\u25B2" : "\u25BC"} {history.current.change_percent}%
              </strong>
            </div>
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
        </>
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

      {pendingOrders.length > 0 && (
        <div className="datil-pending-orders">
          <h3 className="datil-subheading">Ordenes pendientes</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Simbolo</th>
                <th className="datil-col-num">Titulos</th>
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
