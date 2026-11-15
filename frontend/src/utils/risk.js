import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { apiError } from "./errors";
import { pct } from "./format";

// Se siguen exportando desde aquí para no tocar los imports de las pantallas.
export { apiError, pct };

export const SCORE_EXPLANATION =
  "Mide qué tanto suele caer una acción, con datos históricos hasta hoy. En pruebas con 10 años de historia, las " +
  "acciones de riesgo alto tuvieron caídas de 30% o más en el año siguiente casi 3 veces más seguido (60% contra " +
  "21%) que las de riesgo bajo. No predice si va a subir o bajar, y el pasado no garantiza el futuro. No es " +
  "asesoría financiera.";

// Riesgo de una acción (GET /api/risk/stock/<símbolo>), para la pantalla de Comprar / Vender.
// forbidden: el usuario no tiene el módulo de riesgo, así que la pantalla puede omitirlo sin mostrar un error.
export function useStockRisk(symbol) {
  const [state, setState] = useState({ data: null, error: "", forbidden: false });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setState({ data: null, error: "", forbidden: false });
    apiClient
      .get(`/api/risk/stock/${encodeURIComponent(symbol)}`)
      .then(({ data }) => !cancelled && setState({ data, error: "", forbidden: false }))
      .catch(
        (err) =>
          !cancelled &&
          setState({
            data: null,
            error: apiError(err, "No se pudo calcular el riesgo."),
            forbidden: err.response?.status === 403,
          }),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  return { ...state, loading };
}
